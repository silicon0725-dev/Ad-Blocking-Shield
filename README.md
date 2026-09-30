# Ad-Blocking-Shield

**System-wide ad & tracker blocking for Windows, layered on top of your existing Clash (Mihomo) TUN setup — no browser extension required.** (Chinese UI name: 广告拦截控制台)

AdBlock Console inserts a filtering HTTPS proxy between your apps and your Clash tunnel. Browsers and any app that honors the system proxy get EasyList-grade ad/tracker filtering; everything else (games, CLI tools, anything that ignores the proxy) keeps flowing through Clash exactly as before. Your Clash config, rules, and nodes are never modified.

```
 Apps honoring system proxy        Apps ignoring the proxy
        │                                   │
        ▼                                   ▼
 mitmproxy 127.0.0.1:8080          Mihomo TUN (unchanged)
 (EasyList filtering,                │
  selective TLS decryption)          │
        │ outbound to fake-ip         │
        ▼                            ▼
 ┌──────────── Mihomo TUN ─────────────┐
 │  domain/GeoIP/process rules         │
 │  → proxy node / DIRECT              │
 └─────────────────────────────────────┘
                    ▼
                Internet
```

## Highlights

- **Selective TLS decryption.** Only connections whose SNI matches an ad/tracker candidate derived from the rule set are decrypted and inspected. Everything else is tunneled untouched, so the origin server sees the browser's real TLS fingerprint — no more `502` / "peer closed connection" breakage on Cloudflare-protected or certificate-pinning sites.
- **~60,000 rules out of the box** — EasyList + EasyList China, plus optional third-party rule subscriptions you can add from the GUI.
- **Personal lists with hot reload** (no restart, effective within seconds):
  - `whitelist` — never filter a site
  - `blacklist` — always block a domain
  - `bypass` — never decrypt a domain (for pinning apps or fussy CDNs)
- **Low-power domain-only mode.** One toggle switches to CONNECT-stage blocking by domain only — zero TLS decryption, lower CPU, maximum stability.
- **One-click GUI** (PySide6/QML): power button, live block log with one-click "unblock this site", stats, log viewer, settings — with tray icon and silent autostart.
- **Self-healing.** A watchdog restarts the engine if it dies; a proxy guard restores the system proxy if another app (e.g. Clash Verge itself) tampers with it.
- **Fully reversible.** One click (or one script) removes the proxy setting and restores everything.

## How It Works

1. The GUI starts a bundled `mitmdump` engine listening on `127.0.0.1:8080` and points the Windows system proxy at it.
2. A mitmproxy addon (`mitm/adblock.py`) loads EasyList-style rules and classifies every connection:
   - **Ad candidate domains** → decrypted, each request matched against URL/domain rules; ads get an empty `204` response.
   - **Everything else** → tunneled as-is (real TLS end-to-end).
3. The engine's own outbound traffic resolves to Clash's fake-IP range and enters the Mihomo TUN interface, so Clash rules and node selection keep working — no proxy loops, no extra hop.
4. Blocked requests are logged to `mitm/logs/blocked.log`, which feeds the GUI's live log view.

### Modes

| Mode | Decryption | What gets blocked | Best for |
|---|---|---|---|
| **Full** (default) | Ad/tracker candidates only | Domain + full URL path rules | Maximum coverage |
| **Domain-only** | None | Domain rules, at CONNECT time | Lowest power, max stability |

## Requirements

- Windows 10/11
- [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev) (or any Mihomo core) running with **TUN mode enabled** — AdBlock Console layers on top of it and does not manage Clash itself
- The bundled mitmproxy root CA must be trusted (the GUI checks and guides you through installing it into the Windows certificate store)

## Getting Started

### From a release (recommended)

1. Download [`AdShield-v1.0.0.zip`](https://github.com/silicon0725-dev/Ad-Blocking-Shield/releases/download/v1.0.0/AdShield-v1.0.0.zip) (~275 MiB) from the [latest release](https://github.com/silicon0725-dev/Ad-Blocking-Shield/releases/latest) and unzip it — it contains both the GUI (`广告拦截控制台.exe`) and the engine (`mitmdump.exe`).
2. Run the GUI, click the power button.
3. If prompted, install the root CA (current-user store is enough for browsers).

### From source

```bash
git clone https://github.com/silicon0725-dev/Ad-Blocking-Shield.git
cd Ad-Blocking-Shield
pip install PySide6 mitmproxy pyinstaller

# Run in dev mode
pythonw gui/main.py

# Or build the standalone executables (scripts and specs in build/)
pyinstaller --noconfirm build/广告拦截控制台.spec
pyinstaller --noconfirm build/mitmdump.spec
```

## Project Layout

```
gui/        PySide6 backend (main.py) + QML UI (Main.qml)
mitm/       adblock.py  — EasyList engine addon
            lists/      — rule sources + user whitelist/blacklist/bypass
            logs/       — mitmdump.log, blocked.log
bin/        Standalone executables (GUI + engine)
build/      PyInstaller specs, icon generator, build logs
enable.ps1 / restore.ps1   — one-shot enable / full rollback
```

## Security & Privacy

- The mitmproxy root CA is generated **locally on your machine** and installed only into the current user's certificate store. The private key never leaves your machine — **do not commit or share it**.
- Only rule-matched ad/tracker candidates are decrypted; banking sites, pinned apps, and everything else keep their original end-to-end TLS.
- The proxy binds to `127.0.0.1` only; remote hosts are rejected (`block_global=false`).
- Logs (`mitm/logs/`) contain the domains you visit. They stay local — keep them out of any public repo.

> **Note:** HTTPS interception should only run on machines you own and for lawful personal use (filtering your own traffic). Don't use it to inspect other people's connections.

## Limitations

- "Global" means *system-proxy global*: apps that ignore the system proxy are filtered only by Clash's DNS/domain rules, not by HTTPS content inspection.
- Certificate-pinning apps (some banking/AV clients) must be added to the **bypass** list.
- QUIC/HTTP3: browser traffic is forced through the proxy as HTTP/1.1+HTTP/2; QUIC bypasses the proxy but is not broken.

## License

MIT (or pick your own — the code here is yours).
