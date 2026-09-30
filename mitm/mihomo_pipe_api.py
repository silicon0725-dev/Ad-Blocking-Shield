# -*- coding: utf-8 -*-
"""通过命名管道查询 mihomo external-controller API (GET /connections 等用法)
用法: python mihomo_pipe_api.py /connections [过滤关键字]
"""
import json
import os
import re
import sys
import time

CONFIG = os.path.expandvars(r"%APPDATA%\io.github.clash-verge-rev.clash-verge-rev\clash-verge.yaml")


def find_pipe():
    # 动态枚举: 核心重启后管道名中的模式会变(production/sidecar等)
    for p in os.listdir(r"\\.\pipe\\"):
        if p.startswith("verge-mihomo-"):
            return "\\\\.\\pipe\\" + p
    return None


def http_over_pipe(pipe, path, timeout=8):
    # 打开命名管道为文件流, 手写 HTTP/1.1 请求
    req = ("GET %s HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n" % path).encode()
    fh = open(pipe, "r+b", buffering=0)
    try:
        fh.write(req)
        time.sleep(0.3)
        chunks = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data = fh.read(262144)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
            if b"\r\n\r\n" in b"".join(chunks):
                head, _, body = b"".join(chunks).partition(b"\r\n\r\n")
                cl = re.search(rb"Content-Length:\s*(\d+)", head, re.I)
                if cl and len(body) >= int(cl.group(1)):
                    break
        raw = b"".join(chunks)
    finally:
        fh.close()
    head, _, body = raw.partition(b"\r\n\r\n")
    if b"chunked" in head.lower():
        body = dechunk(body)
    status = head.split(b"\r\n")[0].decode(errors="replace")
    return status, body


def dechunk(body):
    out = b""
    while True:
        nl = body.find(b"\r\n")
        if nl < 0:
            break
        try:
            size = int(body[:nl].split(b";")[0], 16)
        except ValueError:
            out += body[:nl]  # 非 chunk 行, 原样保留
            body = body[nl + 2:]
            continue
        if size == 0:
            break
        out += body[nl + 2: nl + 2 + size]
        body = body[nl + 2 + size + 2:]
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/version"
    # Git Bash(MSYS) 会把 /xxx 参数改写成 Windows 路径, 取末段还原
    if not path.startswith("/") or len(path) > 40 or " " in path:
        tail = path.replace("\\", "/").split("/")[-1]
        path = "/" + tail
    keyword = sys.argv[2].lower() if len(sys.argv) > 2 else None
    pipe = find_pipe()
    if not pipe:
        print("no external-controller-pipe found in config")
        sys.exit(1)
    status, body = http_over_pipe(pipe, path)
    print("STATUS:", status)
    try:
        data = json.loads(body)
    except Exception:
        print(body[:2000].decode(errors="replace"))
        return
    if path == "/connections" and keyword:
        conns = data.get("connections") or []
        for c in conns:
            m = c.get("metadata", {})
            line = json.dumps({
                "id": c.get("id", "")[:8],
                "network": m.get("network"),
                "host": m.get("host") or m.get("destinationIP"),
                "dst": m.get("destinationPort"),
                "src": "%s:%s" % (m.get("sourceIP"), m.get("sourcePort")),
                "proc": m.get("process"),
                "chains": c.get("chains"),
                "rule": c.get("rule"),
            }, ensure_ascii=False)
            if keyword in line.lower():
                print(line)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=1)[:2000000])


if __name__ == "__main__":
    main()
