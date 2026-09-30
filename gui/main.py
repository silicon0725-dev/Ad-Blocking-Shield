# -*- coding: utf-8 -*-
"""
广告拦截控制台 — PySide6/QML 后端
链路: 应用 -> 127.0.0.1:8080 (mitmproxy MITM+EasyList) -> TUN -> Mihomo -> Internet
"""
import os
import re
import sys
import json
import socket
import subprocess
import threading
import time
import ctypes
import winreg
from collections import Counter
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")

from PySide6.QtCore import (QObject, Property, Signal, Slot, QTimer, QUrl, Qt,
                            QAbstractNativeEventFilter)
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

# ---- 冻结(exe)与开发(python)双模式路径 ----
# exe 布局: F:\广告拦截\bin\{广告拦截控制台.exe, mitmdump.exe}
#           BASE 仍为项目根, 与开发模式共用 mitm/lists/logs/gui/settings.json
if getattr(sys, "frozen", False):
    BIN_DIR = Path(sys.executable).resolve().parent
    BASE = BIN_DIR.parent
    RESOURCE = Path(getattr(sys, "_MEIPASS", BIN_DIR))  # onefile 运行时解包目录(QML/图标)
else:
    BASE = Path(__file__).resolve().parent.parent
    RESOURCE = Path(__file__).resolve().parent

MITM = BASE / "mitm"
LISTS = MITM / "lists"
LOGS = MITM / "logs"
BLOCKED = LOGS / "blocked.log"
MITMDUMP_LOG = LOGS / "mitmdump.log"
CA_CERT = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.cer"
SETTINGS_FILE = BASE / "gui" / "settings.json"
USER_WHITE = LISTS / "user-whitelist.txt"
USER_BLACK = LISTS / "user-blacklist.txt"
USER_BYPASS = LISTS / "user-bypass.txt"

MITM_PORT = 8080
CLASH_PORT = 7897
NO_WINDOW = 0x08000000
SINGLETON_KEY = "adblock-console-gui-singleton"
RUN_KEY_NAME = "AdblockConsole"


DEFAULT_SOURCES = [
    {"name": "easylist", "url": "https://easylist.to/easylist/easylist.txt",
     "enabled": True, "builtin": True},
    {"name": "easylistchina",
     "url": "https://easylist-downloads.adblockplus.org/easylistchina.txt",
     "enabled": True, "builtin": True},
]

# ---------------- 设置持久化 ----------------


def load_settings():
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
    except Exception:
        data = {}
    data.setdefault("domain_only", False)
    data.setdefault("autostart", False)
    data.setdefault("last_enabled", True)
    if not isinstance(data.get("sources"), list) or not data["sources"]:
        data["sources"] = [dict(s) for s in DEFAULT_SOURCES]
    return data


def save_settings(s):
    try:
        SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    except OSError:
        pass


SETTINGS = load_settings()

# ---------------- Windows API (ctypes, 免 PowerShell) ----------------
wininet = ctypes.windll.wininet
kernel32 = ctypes.windll.kernel32
iphlpapi = ctypes.windll.iphlpapi


def _refresh_proxy_settings():
    wininet.InternetSetOptionW(None, 39, None, 0)  # INTERNET_OPTION_SETTINGS_CHANGED
    wininet.InternetSetOptionW(None, 37, None, 0)  # INTERNET_OPTION_REFRESH


def get_system_proxy():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
        server, _ = winreg.QueryValueEx(k, "ProxyServer")
        winreg.CloseKey(k)
        return bool(enable), str(server or "")
    except OSError:
        return False, ""


def set_system_proxy(server):
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                       r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                       0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ, server)
    winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, 1)
    winreg.CloseKey(k)
    _refresh_proxy_settings()


def listener_pid(port):
    """监听指定端口的 PID (IPv4 TCP), 无则 None — 只读查询, 无副作用"""
    class ROW(ctypes.Structure):
        _fields_ = [("State", wintypes.DWORD), ("LocalAddr", wintypes.DWORD),
                    ("LocalPort", wintypes.DWORD), ("RemoteAddr", wintypes.DWORD),
                    ("RemotePort", wintypes.DWORD), ("Pid", wintypes.DWORD)]
    size = wintypes.ULONG(0)
    iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), False, 2, 5, 0)
    buf = ctypes.create_string_buffer(size.value)
    if iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(size), False, 2, 5, 0) != 0:
        return None
    n = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value
    rows = ctypes.cast(ctypes.byref(buf, 4), ctypes.POINTER(ROW * max(n, 1))).contents
    for row in rows[:n]:
        if row.State == 2 and socket.ntohs(row.LocalPort & 0xFFFF) == port:  # LISTEN
            return row.Pid
    return None


def kill_pid(pid):
    h = kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
    if h:
        kernel32.TerminateProcess(h, 1)
        kernel32.CloseHandle(h)
        return True
    return False


def tun_adapter_up():
    """Mihomo TUN 适配器是否 Up — GetAdaptersAddresses"""
    class AA(ctypes.Structure):
        _fields_ = [("Length", wintypes.ULONG), ("IfIndex", wintypes.ULONG),
                    ("Next", ctypes.c_void_p), ("AdapterName", ctypes.c_char_p),
                    ("FirstUnicast", ctypes.c_void_p), ("FirstAnycast", ctypes.c_void_p),
                    ("FirstMulticast", ctypes.c_void_p), ("FirstDns", ctypes.c_void_p),
                    ("DnsSuffix", ctypes.c_wchar_p), ("Description", ctypes.c_wchar_p),
                    ("FriendlyName", ctypes.c_wchar_p)]
    size = wintypes.ULONG(0)
    iphlpapi.GetAdaptersAddresses(2, 0x100, None, None, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if iphlpapi.GetAdaptersAddresses(2, 0x100, None, buf, ctypes.byref(size)) != 0:
        return False
    p = ctypes.cast(buf, ctypes.POINTER(AA))
    while p:
        a = p.contents
        try:
            if a.FriendlyName and "mihomo" in a.FriendlyName.lower():
                return True
        except Exception:
            pass
        p = ctypes.cast(a.Next, ctypes.POINTER(AA)) if a.Next else None
    return False


def mihomo_core_up():
    try:
        for p in os.listdir("\\\\.\\pipe\\"):
            if p.lower().startswith("verge-mihomo-"):
                return True
    except OSError:
        pass
    return False


def _certutil(args):
    # certutil 输出为系统 ANSI(GBK), 用字节捕获避免解码问题
    return subprocess.run(["certutil", "-user"] + args, capture_output=True,
                          timeout=15, creationflags=NO_WINDOW)


def ca_installed():
    r = _certutil(["-store", "Root", "mitmproxy"])
    return b"mitmproxy" in (r.stdout or b"").lower()


def ca_install():
    r = _certutil(["-addstore", "-f", "Root", str(CA_CERT)])
    return r.returncode == 0


def ca_remove():
    return _certutil(["-delstore", "Root", "mitmproxy"]).returncode == 0


def find_mitmdump():
    if getattr(sys, "frozen", False):
        cand = Path(sys.executable).resolve().parent / "mitmdump.exe"
        if cand.is_file():
            return str(cand)
    cand = Path(sys.executable).parent / "Scripts" / "mitmdump.exe"
    if cand.is_file():
        return str(cand)
    import shutil
    return shutil.which("mitmdump")


def start_mitmdump(domain_only=None):
    """启动 mitmproxy; domain_only=True 时全部流量不解密, 仅按域名在 CONNECT 阶段拦截"""
    if domain_only is None:
        domain_only = SETTINGS.get("domain_only", False)
    md = find_mitmdump()
    if not md:
        return False, "找不到 mitmdump (pip install mitmproxy)"
    if listener_pid(MITM_PORT):
        return True, "mitmproxy 已在运行"
    LOGS.mkdir(parents=True, exist_ok=True)
    args = [md, "-s", str(MITM / "adblock.py"), "-p", str(MITM_PORT),
            "--set", "block_global=false",
            "--set", "stream_large_bodies=100k",
            "--set", "connection_strategy=lazy"]
    if domain_only:
        args += ["--set", "ignore_hosts=."]
    env = dict(os.environ)
    if domain_only:
        env["ADBLOCK_DOMAIN_ONLY"] = "1"
    with open(MITMDUMP_LOG, "ab") as out:
        # 注意: DETACHED_PROCESS 与 CREATE_NO_WINDOW 互斥, 同时传会导致控制台窗口出现
        subprocess.Popen(args, cwd=str(MITM), stdout=out, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, env=env,
                         creationflags=NO_WINDOW)
    for _ in range(20):
        time.sleep(0.5)
        if listener_pid(MITM_PORT):
            return True, "mitmproxy 已启动 (%s)" % ("仅域名拦截" if domain_only else "完整模式")
    return False, "mitmproxy 启动超时, 详见 mitm/logs/mitmdump.log"


def stop_mitmdump():
    pid = listener_pid(MITM_PORT)
    if not pid:
        return True, "mitmproxy 未在运行"
    kill_pid(pid)
    for _ in range(10):
        time.sleep(0.3)
        if listener_pid(MITM_PORT) is None:
            return True, "已停止 mitmproxy"
    return False, "停止 mitmproxy 失败 (PID %d)" % pid


def restart_mitmdump():
    stop_mitmdump()
    return start_mitmdump()


def rule_count():
    """解析 mitmdump 日志尾部最近一次 [adblock] loaded 行的规则数"""
    try:
        size = MITMDUMP_LOG.stat().st_size
        with open(MITMDUMP_LOG, "rb") as f:
            f.seek(max(0, size - 65536))
            data = f.read()
        hits = re.findall(rb"\[adblock\] mode=.*?host=(\d+)", data)
        if hits:
            return int(hits[-1])
    except OSError:
        pass
    return 0


def read_user_list(path):
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        d = line.strip().lower().lstrip(".")
        if d and not d.startswith("#"):
            out.append(d)
    return out


def write_user_list(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sorted(set(i.strip().lower() for i in items if i.strip()))) + "\n",
                    encoding="utf-8")


def read_recent_blocks(n=150):
    """blocked.log 尾部 n 条: [时间, 来源, 域名, 路径, 规则]"""
    try:
        with open(BLOCKED, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 128 * 1024))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
        out = []
        for ln in lines[-n:]:
            p = ln.split("\t")
            if len(p) >= 5:
                out.append({"time": p[0][11:19] if len(p[0]) > 11 else p[0],
                            "src": p[1], "host": p[2],
                            "path": p[3][:70], "rule": p[4][:70]})
        return out
    except OSError:
        return []


def set_autostart_reg(on):
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                       r"Software\Microsoft\Windows\CurrentVersion\Run",
                       0, winreg.KEY_SET_VALUE)
    try:
        if on:
            pyw = sys.executable.replace("python.exe", "pythonw.exe")
            cmd = '"%s" "%s" --hidden' % (pyw, Path(__file__).resolve())
            winreg.SetValueEx(k, RUN_KEY_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, RUN_KEY_NAME)
            except OSError:
                pass
    finally:
        winreg.CloseKey(k)


def autostart_reg_on():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Run")
        v, _ = winreg.QueryValueEx(k, RUN_KEY_NAME)
        winreg.CloseKey(k)
        return bool(v)
    except OSError:
        return False


# ---------------- 拖动暂停动画 ----------------
class MoveFilter(QAbstractNativeEventFilter):
    """检测窗口进入/退出拖动(系统菜单移动循环), 用于暂停动画避免拖动卡顿"""
    WM_ENTERSIZEMOVE = 0x0231
    WM_EXITSIZEMOVE = 0x0232

    def __init__(self, backend):
        super().__init__()
        self._backend = backend

    def nativeEventFilter(self, eventType, message):
        if eventType == "windows_generic_MSG":
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == self.WM_ENTERSIZEMOVE:
                    self._backend.set_moving(True)
                elif msg.message == self.WM_EXITSIZEMOVE:
                    self._backend.set_moving(False)
            except (TypeError, ValueError):
                pass
        return False


# ---------------- 暴露给 QML 的后端 ----------------
class Backend(QObject):
    changed = Signal()
    message = Signal(str)

    def __init__(self):
        super().__init__()
        self._state = {}
        self._offset = 0
        self._hosts = Counter()
        self._total_cnt = 0
        self._today_str = ""
        self._today_cnt = 0
        self._moving = False
        self._blocks_mtime = 0
        self._restarting = False   # 重启互斥: 防止看门狗在 stop/start 间隙抢跑
        self._guard_at = 0.0       # 代理守护节流
        # CA 状态仅在启动与用户操作后检查(不轮询, 避免高频 spawn 进程消耗桌面堆)
        self._ca_cache = (ca_installed(), time.time())
        self._heal_at = 0.0
        timer = QTimer(self)
        timer.timeout.connect(self._refresh)
        timer.start(2000)
        self._refresh()

    # ---- 状态采集 ----
    def _parse_blocked(self):
        if not BLOCKED.is_file():
            self._offset, self._total_cnt, self._hosts = 0, 0, Counter()
            return
        size = BLOCKED.stat().st_size
        if size < self._offset:
            self._offset, self._total_cnt, self._hosts = 0, 0, Counter()
        today = datetime.now().strftime("%Y-%m-%d")
        if self._today_str != today:
            self._today_str = today
            self._today_cnt = 0
        with open(BLOCKED, "r", encoding="utf-8", errors="replace") as f:
            f.seek(self._offset)
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 3:
                    if parts[0].startswith(today):
                        self._today_cnt += 1
                    self._hosts[parts[2]] += 1
                    self._total_cnt += 1
            self._offset = f.tell()

    def _refresh(self):
        proxy_on, server = get_system_proxy()
        now = time.time()
        try:
            lm = MITMDUMP_LOG.stat().st_mtime if MITMDUMP_LOG.is_file() else 0
        except OSError:
            lm = 0
        if lm != getattr(self, "_lm", -1):
            self._lm = lm
            self._rules = rule_count()
        self._parse_blocked()
        try:
            bm = BLOCKED.stat().st_mtime if BLOCKED.is_file() else 0
        except OSError:
            bm = 0
        recent = read_recent_blocks() if bm != self._blocks_mtime else \
            self._state.get("recent", [])
        self._blocks_mtime = bm
        proxy_ours = proxy_on and str(MITM_PORT) in (server or "")
        mitm_on = listener_pid(MITM_PORT) is not None
        new_state = dict(
            mitm=mitm_on,
            proxy=proxy_ours,
            server=server or "",
            tun=tun_adapter_up(),
            core=mihomo_core_up(),
            ca=self._ca_cache[0],
            today=self._today_cnt,
            total=self._total_cnt,
            top=[{"host": h, "count": c} for h, c in self._hosts.most_common(6)],
            rules=getattr(self, "_rules", 0),
            recent=recent,
            user_white=read_user_list(USER_WHITE),
            user_black=read_user_list(USER_BLACK),
            user_bypass=read_user_list(USER_BYPASS),
            domain_only=bool(SETTINGS.get("domain_only")),
            autostart=autostart_reg_on(),
            sources=SETTINGS.get("sources", []),
        )
        # 仅在状态真实变化时通知 QML, 避免周期性模型重建造成拖动卡顿
        if new_state != self._state:
            self._state = new_state
            self.changed.emit()
        # 代理守护: 拦截应为启用状态, 但系统代理被外部改回 7897 或被整个关闭
        # (Verge 关闭托管后启动时会清空代理), 且 MITM 在线 → 自动恢复 8080
        if (SETTINGS.get("last_enabled") and mitm_on and not self._restarting
                and (not proxy_on or server == "127.0.0.1:%d" % CLASH_PORT)
                and now - self._guard_at > 15):
            self._guard_at = now
            set_system_proxy("127.0.0.1:%d" % MITM_PORT)
            self.message.emit("🛡 系统代理被外部关闭/修改，已自动恢复 → 127.0.0.1:8080")
            self._refresh()
        # 自愈看门狗: 系统代理指向 8080 而 MITM 掉线 → 自动拉起, 防止浏览器断网
        if (proxy_ours and not mitm_on and now - self._heal_at > 30
                and not self._restarting):
            self._heal_at = now
            def heal():
                ok, msg = start_mitmdump()
                self.message.emit(("🔧 检测到 MITM 掉线, 已自动恢复" if ok
                                   else "⚠️ MITM 掉线且自动恢复失败: ") + msg)
                self._refresh()
            threading.Thread(target=heal, daemon=True).start()

    def _st(self, k):
        return self._state.get(k)

    # ---- QML 属性 ----
    def _g_enabled(self):
        return bool(self._st("mitm") and self._st("proxy"))
    enabled = Property(bool, _g_enabled, notify=changed)

    def _g_mitm(self):
        return bool(self._st("mitm"))
    mitmRunning = Property(bool, _g_mitm, notify=changed)

    def _g_proxy(self):
        return bool(self._st("proxy"))
    proxyOurs = Property(bool, _g_proxy, notify=changed)

    def _g_server(self):
        return str(self._st("server") or "—")
    proxyServer = Property(str, _g_server, notify=changed)

    def _g_tun(self):
        return bool(self._st("tun"))
    tunUp = Property(bool, _g_tun, notify=changed)

    def _g_core(self):
        return bool(self._st("core"))
    coreUp = Property(bool, _g_core, notify=changed)

    def _g_ca(self):
        return bool(self._st("ca"))
    caOk = Property(bool, _g_ca, notify=changed)

    def _g_today(self):
        return int(self._st("today") or 0)
    blockedToday = Property(int, _g_today, notify=changed)

    def _g_total(self):
        return int(self._st("total") or 0)
    blockedTotal = Property(int, _g_total, notify=changed)

    def _g_rules(self):
        return int(self._st("rules") or 0)
    ruleCount = Property(int, _g_rules, notify=changed)

    def _g_top(self):
        return self._state.get("top") or []
    topDomains = Property("QVariantList", _g_top, notify=changed)

    def _g_recent(self):
        return self._state.get("recent") or []
    recentBlocks = Property("QVariantList", _g_recent, notify=changed)

    def _g_uw(self):
        return self._state.get("user_white") or []
    userWhitelist = Property("QVariantList", _g_uw, notify=changed)

    def _g_ub(self):
        return self._state.get("user_black") or []
    userBlacklist = Property("QVariantList", _g_ub, notify=changed)

    def _g_bp(self):
        return self._state.get("user_bypass") or []
    userBypass = Property("QVariantList", _g_bp, notify=changed)

    def _g_do(self):
        return bool(self._st("domain_only"))
    domainOnly = Property(bool, _g_do, notify=changed)

    def _g_as(self):
        return bool(self._st("autostart"))
    autoStart = Property(bool, _g_as, notify=changed)

    def _g_sources(self):
        return self._state.get("sources") or []
    sources = Property("QVariantList", _g_sources, notify=changed)

    # ---- 拖动状态(供 QML 暂停动画) ----
    def set_moving(self, v):
        if v != self._moving:
            self._moving = v
            self.changed.emit()

    def _g_moving(self):
        return self._moving
    moving = Property(bool, _g_moving, notify=changed)

    # ---- 操作 ----
    @Slot()
    def enable(self):
        def work():
            ok, msg = start_mitmdump()
            if not ok:
                self.message.emit("❌ " + msg)
                return
            if not self._ca_cache[0]:
                if CA_CERT.is_file():
                    if ca_install():
                        self._ca_cache = (True, time.time())
                        self.message.emit("🔐 已安装 mitmproxy CA 到用户 Root 存储")
                else:
                    self.message.emit("⚠️ CA 将在首次 HTTPS 后生成, 稍后重新启用一次即可安装")
            set_system_proxy("127.0.0.1:%d" % MITM_PORT)
            SETTINGS["last_enabled"] = True
            save_settings(SETTINGS)
            self.message.emit("✅ 广告拦截已启用 (系统代理 → 127.0.0.1:8080)")
            self._refresh()
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def disable(self):
        def work():
            # 先落 last_enabled 再改代理, 保证守护不会把停用操作改回去
            SETTINGS["last_enabled"] = False
            save_settings(SETTINGS)
            stop_mitmdump()
            set_system_proxy("127.0.0.1:%d" % CLASH_PORT)
            self.message.emit("⏹ 已停用, 系统代理恢复 → 127.0.0.1:7897 (Clash)")
            self._refresh()
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def toggle(self):
        self.disable() if self._g_enabled() else self.enable()

    @Slot()
    def rollback(self):
        """彻底回滚: 停 MITM + 代理还原 + 删除 CA"""
        def work():
            SETTINGS["last_enabled"] = False
            save_settings(SETTINGS)
            stop_mitmdump()
            set_system_proxy("127.0.0.1:%d" % CLASH_PORT)
            ca_remove()
            self._ca_cache = (False, time.time())
            self.message.emit("↩ 已彻底回滚 (含删除 mitmproxy CA)")
            self._refresh()
        threading.Thread(target=work, daemon=True).start()

    # ---- 用户白/黑名单 ----
    @Slot(str)
    def addWhitelist(self, domain):
        d = domain.strip().lower().lstrip(".")
        if not d:
            return
        lst = read_user_list(USER_WHITE)
        if d not in lst:
            lst.append(d)
            write_user_list(USER_WHITE, lst)
            self.message.emit("✅ 已加入白名单: %s (≤10秒内生效)" % d)
        self._refresh()

    @Slot(str)
    def removeWhitelist(self, domain):
        lst = [x for x in read_user_list(USER_WHITE)
               if x != domain.strip().lower().lstrip(".")]
        write_user_list(USER_WHITE, lst)
        self.message.emit("已从白名单移除: %s" % domain)
        self._refresh()

    @Slot(str)
    def addBlacklist(self, domain):
        d = domain.strip().lower().lstrip(".")
        if not d:
            return
        lst = read_user_list(USER_BLACK)
        if d not in lst:
            lst.append(d)
            write_user_list(USER_BLACK, lst)
            self.message.emit("⛔ 已加入黑名单: %s (≤10秒内生效)" % d)
        self._refresh()

    @Slot(str)
    def removeBlacklist(self, domain):
        lst = [x for x in read_user_list(USER_BLACK)
               if x != domain.strip().lower().lstrip(".")]
        write_user_list(USER_BLACK, lst)
        self.message.emit("已从黑名单移除: %s" % domain)
        self._refresh()

    # ---- MITM 直通名单(不解密: 修复TLS指纹被拒502/证书校验应用) ----
    @Slot(str)
    def addBypass(self, domain):
        d = domain.strip().lower().lstrip(".")
        if not d:
            return
        lst = read_user_list(USER_BYPASS)
        if d not in lst:
            lst.append(d)
            write_user_list(USER_BYPASS, lst)
            self.message.emit("🔀 已加入 MITM 直通: %s (≤10秒生效, 该域名不再解密/过滤)" % d)
        self._refresh()

    @Slot(str)
    def removeBypass(self, domain):
        lst = [x for x in read_user_list(USER_BYPASS)
               if x != domain.strip().lower().lstrip(".")]
        write_user_list(USER_BYPASS, lst)
        self.message.emit("已从直通名单移除: %s" % domain)
        self._refresh()

    # ---- 模式与自启 ----
    @Slot(bool)
    def setDomainOnly(self, on):
        SETTINGS["domain_only"] = bool(on)
        save_settings(SETTINGS)
        self._restarting = True
        def work():
            try:
                if listener_pid(MITM_PORT):
                    ok, msg = restart_mitmdump()
                    self.message.emit(("🌿 已切换为仅域名拦截(不解密, 低功耗) " if on
                                       else "🔍 已切换为完整拦截(域名+路径) ")
                                      + ("，mitmproxy 已重启" if ok else "，但重启失败: " + msg))
                else:
                    self.message.emit("🌿 仅域名拦截模式已保存, 下次启动生效" if on
                                      else "🔍 完整拦截模式已保存, 下次启动生效")
            finally:
                self._restarting = False
            self._refresh()
        threading.Thread(target=work, daemon=True).start()

    @Slot(bool)
    def setAutoStart(self, on):
        try:
            set_autostart_reg(bool(on))
            SETTINGS["autostart"] = bool(on)
            save_settings(SETTINGS)
            self.message.emit("✅ 开机自启已开启" if on else "开机自启已关闭")
        except OSError as e:
            self.message.emit("❌ 设置开机自启失败: %s" % e)
        self._refresh()

    # ---- 规则源管理 ----
    @Slot(str, str)
    def addSource(self, name, url):
        name = re.sub(r"[^a-zA-Z0-9_-]", "", name.strip())[:40]
        url = url.strip()
        if not name or not url.startswith(("http://", "https://")):
            self.message.emit("❌ 名称或 URL 无效")
            return
        srcs = SETTINGS["sources"]
        for s in srcs:
            if s["name"] == name:
                s["url"] = url
                break
        else:
            srcs.append({"name": name, "url": url, "enabled": True, "builtin": False})
        save_settings(SETTINGS)
        self.message.emit("✅ 已添加规则源 %s, 点击\"更新规则\"下载" % name)
        self._refresh()

    @Slot(str)
    def removeSource(self, name):
        SETTINGS["sources"] = [s for s in SETTINGS["sources"]
                               if not (s["name"] == name and not s.get("builtin"))]
        save_settings(SETTINGS)
        f = LISTS / (name + ".txt")
        if f.is_file():
            f.unlink()
        self.message.emit("已移除规则源 %s (重启拦截后生效)" % name)
        self._refresh()

    @Slot(str)
    def toggleSource(self, name):
        for s in SETTINGS["sources"]:
            if s["name"] == name:
                s["enabled"] = not s.get("enabled")
                break
        save_settings(SETTINGS)
        self._refresh()

    @Slot()
    def updateLists(self):
        def work():
            import urllib.request
            self.message.emit("⏳ 正在更新规则…")
            ok_all = True
            for s in SETTINGS["sources"]:
                if not s.get("enabled"):
                    continue
                try:
                    req = urllib.request.Request(s["url"],
                                                 headers={"User-Agent": "Mozilla/5.0"})
                    data = urllib.request.urlopen(req, timeout=60).read()
                    (LISTS / (s["name"] + ".txt")).write_bytes(data)
                    self.message.emit("  ✅ %s (%d KB)" % (s["name"], len(data) // 1024))
                except Exception as e:
                    ok_all = False
                    self.message.emit("  ❌ %s: %s" % (s["name"], e))
            # 禁用的源删除其文件
            for s in SETTINGS["sources"]:
                if not s.get("enabled"):
                    f = LISTS / (s["name"] + ".txt")
                    if f.is_file():
                        f.unlink()
            if ok_all and listener_pid(MITM_PORT):
                self._restarting = True
                try:
                    stop_mitmdump()
                    ok, msg = start_mitmdump()
                finally:
                    self._restarting = False
                self.message.emit("🔄 规则已更新" + ("，mitmproxy 已重启生效" if ok
                                                    else "，但重启失败: " + msg))
            self._refresh()
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def openBlockedLog(self):
        if BLOCKED.is_file():
            os.startfile(str(BLOCKED))

    @Slot()
    def openFolder(self):
        os.startfile(str(BASE))


def make_icon(enabled=True):
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#22c55e" if enabled else "#64748b"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    p.setPen(QColor("white"))
    f = p.font()
    f.setBold(True)
    f.setPixelSize(34)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "盾")
    p.end()
    return QIcon(pm)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("广告拦截控制台")
    app.setQuitOnLastWindowClosed(False)      # 关窗缩到托盘
    hidden = "--hidden" in sys.argv           # 开机自启的静默模式

    # ---- 单实例检测: 已有实例在运行则提示并唤醒它, 本进程退出 ----
    probe = QLocalSocket()
    probe.connectToServer(SINGLETON_KEY)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.waitForBytesWritten(500)
        probe.disconnectFromServer()
        ctypes.windll.user32.MessageBoxW(
            0, "广告拦截控制台已经在运行了。\n\n已将其窗口调到前台（也可从系统托盘找回）。",
            "广告拦截控制台", 0x40)
        return 0
    QLocalServer.removeServer(SINGLETON_KEY)   # 清理上次崩溃残留

    svg_icon_path = RESOURCE / "icons" / "shield-check.svg"
    svg_icon = QIcon(str(svg_icon_path)) if svg_icon_path.is_file() else QIcon()
    app.setWindowIcon(svg_icon)

    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("Backend", backend)
    qml = RESOURCE / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        print("QML 加载失败")
        return 1
    win = engine.rootObjects()[0]
    if hidden:
        win.hide()

    # 原生消息过滤: 拖动期间通知 QML 暂停动画, 保证移动流畅
    move_filter = MoveFilter(backend)
    app.installNativeEventFilter(move_filter)

    tray = QSystemTrayIcon(svg_icon if not svg_icon.isNull() else make_icon(True), app)
    menu = QMenu()
    act_show = menu.addAction("显示控制台")
    act_toggle = menu.addAction("停用广告拦截")
    menu.addSeparator()
    act_quit = menu.addAction("退出")
    tray.setContextMenu(menu)
    tray.setToolTip("广告拦截控制台")
    tray.show()

    def sync_tray():
        act_toggle.setText("停用广告拦截" if backend.enabled else "启用广告拦截")
        tray.setIcon(svg_icon if (backend.enabled and not svg_icon.isNull())
                     else make_icon(backend.enabled))
    backend.changed.connect(sync_tray)

    def on_show():
        win.showNormal()
        win.raise_()
        win.requestActivate()
    act_show.triggered.connect(on_show)
    act_toggle.triggered.connect(backend.toggle)
    tray.activated.connect(lambda reason: on_show()
                           if reason == QSystemTrayIcon.Trigger else None)

    # ---- 单实例服务: 后续启动的实例通过本地套接字发来唤醒请求 ----
    server = QLocalServer(app)
    ok = server.listen(SINGLETON_KEY)

    def _dbg(msg):
        with open(LOGS / "singleton.log", "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")

    _dbg("listen=%s name=%s" % (ok, server.serverName()))

    def _on_new_conn():
        _dbg("newConnection fired, pending=%s" % server.hasPendingConnections())
        while server.hasPendingConnections():
            conn = server.nextPendingConnection()
            got = conn.waitForReadyRead(500)
            data = bytes(conn.readAll())
            _dbg("conn read ok=%s data=%r" % (got, data))
            if data == b"show":
                _dbg("calling on_show, win visible=%s" % win.isVisible())
                on_show()
                _dbg("after on_show, win visible=%s" % win.isVisible())
            conn.disconnectFromServer()
            conn.deleteLater()
    server.newConnection.connect(_on_new_conn)

    def on_quit():
        # 一致性保障: 退出时若 MITM 未运行而系统代理仍指向 8080, 恢复为 7897 防止断网
        p_on, server_addr = get_system_proxy()
        if p_on and str(MITM_PORT) in (server_addr or "") and listener_pid(MITM_PORT) is None:
            set_system_proxy("127.0.0.1:%d" % CLASH_PORT)
        app.quit()
    act_quit.triggered.connect(on_quit)

    def on_message(text):
        tray.showMessage("广告拦截控制台", text, QSystemTrayIcon.Information, 2500)
    backend.message.connect(on_message)

    # ---- 开机自启静默模式: 等 Clash 就绪后恢复上次启用状态 ----
    if hidden and SETTINGS.get("last_enabled"):
        def boot():
            for _ in range(40):                 # 最多等 120s
                if tun_adapter_up() and mihomo_core_up():
                    break
                time.sleep(3)
            if not (get_system_proxy()[1] or "").endswith(str(MITM_PORT)):
                ok, _ = start_mitmdump()
                if ok:
                    set_system_proxy("127.0.0.1:%d" % MITM_PORT)
                    backend.message.emit("✅ 开机自启: 广告拦截已恢复")
                    backend._refresh()
        threading.Thread(target=boot, daemon=True).start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
