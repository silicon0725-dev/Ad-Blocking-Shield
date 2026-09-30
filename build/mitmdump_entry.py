# mitmdump.exe 入口 — 独立打包的 mitmproxy 拦截引擎
import sys

from mitmproxy.tools.main import mitmdump

if __name__ == "__main__":
    sys.exit(mitmdump())
