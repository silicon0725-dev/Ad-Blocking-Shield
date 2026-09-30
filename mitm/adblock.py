# -*- coding: utf-8 -*-
"""
mitmproxy ad-block addon — EasyList 语法实用子集实现
支持: ||domain^ 域名锚点 / |url 开头锚点 / 普通子串 / * 与 ^ 通配
      @@ 白名单 / $important / $third-party,~third-party / $domain=a|~b
      用户白/黑名单(lists/user-*.txt, 热重载) / 仅域名拦截模式(不解密)
拦截方式: 常规模式 204 空响应; 域名模式 CONNECT 阶段 403(不解密)
"""
import os
import re
import time
import datetime

from mitmproxy import ctx, http

BASE = os.path.dirname(os.path.abspath(__file__))
LISTS_DIR = os.path.join(BASE, "lists")
USER_WHITE = os.path.join(LISTS_DIR, "user-whitelist.txt")
USER_BLACK = os.path.join(LISTS_DIR, "user-blacklist.txt")
USER_BYPASS = os.path.join(LISTS_DIR, "user-bypass.txt")   # MITM 直通名单(不解密)
BLOCK_LOG = os.path.join(BASE, "logs", "blocked.log")

# 仅域名拦截模式: 忽略路径级规则, 全部流量不解密(隧道直通), CONNECT 阶段拦截
DOMAIN_ONLY = os.environ.get("ADBLOCK_DOMAIN_ONLY") == "1"

LISTS_ENV = os.environ.get("ADBLOCK_LISTS")
RELOAD_GATE = 10.0  # 秒, 规则文件热重载检查间隔

SKIP_OPTIONS = {"generichide", "elemhide", "specifichide", "ghide", "inline-script",
                "inline-font", "ping", "websocket", "webrtc"}
SEP = r"[^a-zA-Z0-9._%-]"


def parse_options(raw):
    opts, important, skip = {}, False, False
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        neg = tok.startswith("~")
        name = tok[1:] if neg else tok
        if name == "important":
            important = True
        elif name in ("third-party", "3p"):
            opts["third_party"] = not neg
        elif name.startswith("domain="):
            doms = {}
            for d in name[7:].split("|"):
                if d.startswith("~"):
                    doms[d[1:]] = False
                elif d:
                    doms[d] = True
            opts["domain"] = doms
        elif name in SKIP_OPTIONS:
            skip = True
    return opts, skip, important


def pattern_to_regex(pat):
    out = []
    for ch in pat:
        if ch == "*":
            out.append(".*")
        elif ch == "^":
            out.append(SEP)
        else:
            out.append(re.escape(ch))
    return re.compile("".join(out), re.IGNORECASE)


def host_matches(req_host, rule_host):
    return req_host == rule_host or req_host.endswith("." + rule_host)


class Rule:
    __slots__ = ("raw", "regex", "substr", "host_anchor", "host_exact",
                 "tail_pure", "opts", "whitelist", "important", "src")

    def __init__(self, raw, whitelist, opts, important, src):
        self.raw = raw
        self.opts = opts
        self.whitelist = whitelist
        self.important = important
        self.src = src
        self.host_anchor = False
        self.host_exact = None
        self.regex = None
        self.substr = None
        if raw.startswith("||"):
            self.host_anchor = True
            rest = raw[2:]
            m = re.match(r"[^^/]+", rest)
            host = m.group(0) if m else rest
            self.host_exact = host.lower().strip(".")
            tail = rest[len(host):]
            # 尾部仅由分隔符/通配组成(^ * ^*^ 等)时, 等价于纯域名规则
            # (URL 必然含有 : / 等分隔符), 域名拦截模式可直接使用
            self.tail_pure = tail == "" or set(tail) <= {"^", "*"}
            if tail:
                if "*" in tail or "^" in tail:
                    self.regex = pattern_to_regex(tail)
                else:
                    self.substr = tail
        elif raw.startswith("|"):
            self.regex = re.compile(
                "^(?:" + pattern_to_regex(raw[1:]).pattern + ")", re.IGNORECASE)
            self.tail_pure = False
        else:
            if "*" in raw or "^" in raw:
                self.regex = pattern_to_regex(raw)
            else:
                self.substr = raw
            self.tail_pure = False

    @property
    def domain_only_usable(self):
        """纯域名规则(尾部无实质限定), 域名模式可用"""
        return self.host_anchor and self.tail_pure

    def match(self, url, host, doc_host):
        if self.host_anchor:
            if not host_matches(host, self.host_exact):
                return False
            if self.substr is not None:
                return self.substr in url
            if self.regex is not None:
                return self.regex.search(url) is not None
            return True
        if self.substr is not None:
            return self.substr in url
        return self.regex.search(url) is not None


class AdBlock:
    def __init__(self):
        self.block_host = {}
        self.block_url = []
        self.url_hosts = set()      # 路径级规则涉及的域名(需要解密才能匹配路径)
        self.white_host = {}
        self.white_url = []
        self.user_white = set()
        self.user_black = set()
        self.user_bypass = set()
        self._tunnel_logged = set()  # 已记录过的直通域名(避免日志刷屏)
        self.stats = {"checked": 0, "blocked": 0, "whitelisted": 0}
        self._logfh = None
        self._etld_cache = {}
        self._mtimes = {}
        self._next_check = 0.0

    # ---------- 生命周期 ----------
    def running(self):
        os.makedirs(os.path.dirname(BLOCK_LOG), exist_ok=True)
        self._logfh = open(BLOCK_LOG, "a", encoding="utf-8")
        self._load_all()
        mode = "仅域名拦截(不解密)" if DOMAIN_ONLY else "精准解密(规则命中才解密)"
        ctx.log.info("[adblock] mode=%s, user_white=%d, user_black=%d, user_bypass=%d, "
                     "host=%d url=%d whitelist=%d skipped=%d"
                     % (mode, len(self.user_white), len(self.user_black),
                        len(self.user_bypass),
                        self._n_host, self._n_url, self._n_white, self._n_skip))

    def done(self):
        ctx.log.info("[adblock] stats: %r" % self.stats)
        if self._logfh:
            self._logfh.close()

    def _list_files(self):
        if LISTS_ENV:
            return [p for p in LISTS_ENV.split(";") if os.path.isfile(p)]
        files = []
        if os.path.isdir(LISTS_DIR):
            for n in sorted(os.listdir(LISTS_DIR)):
                if n.endswith(".txt") and not n.startswith("user-"):
                    files.append(os.path.join(LISTS_DIR, n))
        return files

    def _load_all(self):
        self.block_host = {}
        self.block_url = []
        self.url_hosts = set()
        self.white_host = {}
        self.white_url = []
        self.user_white = set()
        self.user_black = set()
        self.user_bypass = set()
        n_host = n_url = n_white = n_skip = 0
        for path in self._list_files():
            src = os.path.basename(path)
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(("!", "[", "# ")):
                        continue
                    if "##" in line or "#@#" in line or "#?#" in line:
                        continue
                    wl = line.startswith("@@")
                    body = line[2:] if wl else line
                    if "$" in body:
                        idx = body.rindex("$")
                        pattern, raw_opts = body[:idx], body[idx + 1:]
                    else:
                        pattern, raw_opts = body, ""
                    if not pattern:
                        continue
                    opts, skip, important = parse_options(raw_opts)
                    if skip:
                        n_skip += 1
                        continue
                    r = Rule(pattern, wl, opts, important, src)
                    if wl:
                        n_white += 1
                        if r.host_anchor and r.host_exact:
                            self.white_host.setdefault(r.host_exact, []).append(r)
                        else:
                            self.white_url.append(r)
                    elif r.host_anchor and r.host_exact:
                        n_host += 1
                        self.block_host.setdefault(r.host_exact, []).append(r)
                    else:
                        n_url += 1
                        self.block_url.append(r)
                        # 路径级规则涉及域名 → 解密候选集
                        if r.host_anchor and r.host_exact:
                            self.url_hosts.add(r.host_exact)
            self._mtimes[path] = os.path.getmtime(path)
        # 用户白/黑/直通名单: 一行一个域名(后缀匹配), # 为注释
        for path, target in ((USER_WHITE, self.user_white),
                             (USER_BLACK, self.user_black),
                             (USER_BYPASS, self.user_bypass)):
            if os.path.isfile(path):
                with open(path, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        d = line.strip().lower().lstrip(".")
                        if d and not d.startswith("#"):
                            target.add(d)
                self._mtimes[path] = os.path.getmtime(path)
        self._n_host, self._n_url, self._n_white, self._n_skip = \
            n_host, n_url, n_white, n_skip

    def _maybe_reload(self):
        """规则/用户名单文件变更时热重载(10s 节流)"""
        now = time.monotonic()
        if now < self._next_check:
            return
        self._next_check = now + RELOAD_GATE
        try:
            for path, mt in list(self._mtimes.items()):
                if not os.path.isfile(path) or os.path.getmtime(path) != mt:
                    self._load_all()
                    ctx.log.info("[adblock] 规则文件变更, 已热重载 "
                                 "(user_white=%d user_black=%d)" %
                                 (len(self.user_white), len(self.user_black)))
                    return
            for path in self._list_files() + [USER_WHITE, USER_BLACK, USER_BYPASS]:
                if os.path.isfile(path) and path not in self._mtimes:
                    self._load_all()
                    ctx.log.info("[adblock] 新规则文件, 已热重载: %s" % path)
                    return
        except OSError:
            pass

    # ---------- 工具 ----------
    def _host_rules(self, host, table):
        parts = host.split(".")
        for i in range(len(parts) - 1):
            rs = table.get(".".join(parts[i:]))
            if rs:
                yield from rs

    def _etld1(self, host):
        if host in self._etld_cache:
            return self._etld_cache[host]
        try:
            from publicsuffix2 import get_sld
            v = get_sld(host) or host
        except Exception:
            v = host
        self._etld_cache[host] = v
        return v

    def _opts_ok(self, rule, host, doc_host):
        o = rule.opts
        if not o:
            return True
        if "third_party" in o:
            if doc_host is None:
                if o["third_party"]:
                    return False
            else:
                tp = self._etld1(doc_host) != self._etld1(host)
                if o["third_party"] != tp:
                    return False
        if "domain" in o:
            doms = o["domain"]
            ref = doc_host or host
            ok = False
            for d, want in doms.items():
                hit = host_matches(ref, d)
                if hit and not want:
                    return False
                if hit and want:
                    ok = True
            if not ok:
                return False
        return True

    def _find(self, url, host, doc_host, rules_iter, important_only):
        for r in rules_iter:
            if important_only and not r.important:
                continue
            if r.match(url, host, doc_host) and self._opts_ok(r, host, doc_host):
                return r
        return None

    def _log_block(self, src, host, path, rule):
        if self._logfh:
            ts = datetime.datetime.now().isoformat(timespec="seconds")
            self._logfh.write("%s\t%s\t%s\t%s\t%s\n"
                              % (ts, src, host, (path or "")[:180], rule[:180]))
            self._logfh.flush()

    # ---------- 按规则精准解密 ----------
    # 默认隧道直通(不解密): 大厂主站不在广告规则中, 浏览器原始TLS直达源站,
    # 从根上规避 Cloudflare 等对 mitmproxy TLS 指纹的拒绝(502 peer closed)。
    # 仅当域名命中广告规则(或用户黑名单)时才解密过滤。
    def tls_clienthello(self, data):
        if DOMAIN_ONLY:
            return                      # 域名模式已由 ignore_hosts 全量直通
        try:
            sni = (data.client_hello.sni or "").lower()
        except Exception:
            return
        self._maybe_reload()
        if not sni or sni.startswith("127."):
            data.ignore_connection = True   # 无 SNI 无法按域名决策 → 直通
            return
        # 1. 用户直通名单: 显式不解密
        for d in self.user_bypass:
            if host_matches(sni, d):
                data.ignore_connection = True
                return
        # 2. 用户白名单: 无需过滤 → 也不必解密
        for d in self.user_white:
            if host_matches(sni, d):
                data.ignore_connection = True
                return
        # 3. 解密候选: 用户黑名单 / 域名级规则 / 路径级规则涉及域名
        if (any(host_matches(sni, d) for d in self.user_black)
                or any(True for _ in self._host_rules(sni, self.block_host))
                or any(host_matches(sni, d) for d in self.url_hosts)):
            return                      # 命中 → 正常解密过滤
        # 4. 其余一律隧道直通
        data.ignore_connection = True
        if sni not in self._tunnel_logged:
            self._tunnel_logged.add(sni)
            ctx.log.info("[adblock] TUNNEL(未命中规则,直通不解密) %s" % sni)

    # ---------- 域名模式: CONNECT 阶段拦截(不解密) ----------
    def http_connect(self, flow: http.HTTPFlow):
        if not DOMAIN_ONLY:
            return
        host = flow.request.host.lower()
        if not host or host.startswith("127."):
            return
        self._maybe_reload()
        # 用户白名单最优先(高于一切)
        for d in self.user_white:
            if host_matches(host, d):
                return
        # 用户黑名单 / 纯域名规则命中 → 拒绝隧道
        # 注意: 带 $third-party/$domain= 等限定的规则在 CONNECT 阶段无法评估,
        # 域名模式下跳过它们(宁可漏拦不可误杀)
        hit = any(host_matches(host, d) for d in self.user_black)
        if not hit:
            for r in self._host_rules(host, self.block_host):
                if r.domain_only_usable and not r.opts:
                    hit = r
                    break
        if hit:
            self.stats["blocked"] += 1
            src = "user-blacklist" if hit is True else hit.src
            rule = "用户黑名单" if hit is True else hit.raw
            ctx.log.info("[adblock] BLOCK(connect) %s  <-  %s" % (host, rule))
            self._log_block(src, host, "", rule)
            flow.response = http.Response.make(
                403, b"blocked by domain rule\n",
                {"Content-Type": "text/plain", "X-Adblock": "domain-only"})

    # ---------- 常规模式: 解密后按完整规则拦截 ----------
    def request(self, flow: http.HTTPFlow):
        if DOMAIN_ONLY:
            return  # 域名模式下其余流量已被 ignore_hosts 直通
        req = flow.request
        host = req.host.lower()
        if not host or host == "localhost" or host.startswith("127."):
            return
        url = req.pretty_url
        self.stats["checked"] += 1
        self._maybe_reload()

        ref = req.headers.get("Referer") or req.headers.get("referrer")
        doc_host = None
        if ref:
            m = re.match(r"https?://([^/?#]+)", ref)
            if m:
                doc_host = m.group(1).lower().split("@")[-1].split(":")[0]

        # 用户白名单最优先(高于一切)
        for d in self.user_white:
            if host_matches(host, d):
                self.stats["whitelisted"] += 1
                return
        # 用户黑名单次优先(高于 EasyList 白名单)
        for d in self.user_black:
            if host_matches(host, d):
                self.stats["blocked"] += 1
                flow.response = http.Response.make(
                    204, b"", {"Content-Type": "text/plain",
                               "X-Adblock": "user-blacklist"})
                self._log_block("user-blacklist", host, req.path, "用户黑名单")
                ctx.log.info("[adblock] BLOCK(user) %s" % host)
                return

        wl_iter = list(self._host_rules(host, self.white_host)) + self.white_url
        hit = self._find(url, host, doc_host, wl_iter, important_only=False)

        block = None
        if hit is None:
            bh = list(self._host_rules(host, self.block_host))
            block = self._find(url, host, doc_host, bh, important_only=True)
            if block is None:
                block = self._find(url, host, doc_host, bh + self.block_url,
                                   important_only=False)

        if hit is not None:
            self.stats["whitelisted"] += 1
            flow.metadata["adblock_whitelist"] = hit.raw
            return
        if block is not None:
            self.stats["blocked"] += 1
            flow.response = http.Response.make(
                204, b"",
                {"Content-Type": "text/plain", "X-Adblock": block.raw[:200]})
            self._log_block(block.src, host, req.path, block.raw)
            ctx.log.info("[adblock] BLOCK %s%s  <-  %s" % (host, req.path[:80], block.raw[:100]))


addons = [AdBlock()]
