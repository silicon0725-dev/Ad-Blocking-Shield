# 启动 mitmproxy (upstream 模式 -> Mihomo 127.0.0.1:7897)
# 用法: powershell -File start-mitm.ps1
$ErrorActionPreference = "Stop"
$base = Split-Path -Parent $MyInvocation.MyCommand.Path

$existing = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[start-mitm] 8080 已被监听 (PID $($existing[0].OwningProcess)), 跳过启动"
    exit 0
}

$log = Join-Path $base "logs\mitmdump.log"
$proc = Start-Process -FilePath "mitmdump" -ArgumentList @(
    "-s", (Join-Path $base "adblock.py"),
    "-p", "8080",
    "--set", "block_global=false",
    "--set", "stream_large_bodies=100k",
    "--set", "connection_strategy=lazy"
    # 如需对 certificate-pinning 应用直通, 取消下行注释并按需修改:
    # "--set", "ignore_hosts=.*\.banking-example\.com"
) -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.err" -PassThru

Start-Sleep -Seconds 6
$ok = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if ($ok) {
    Write-Host "[start-mitm] mitmdump 已启动 PID=$($proc.Id), 8080 (常规模式, 出站经 TUN→Mihomo)"
} else {
    Write-Host "[start-mitm] 启动失败, 查看日志: $log / $log.err"
    Get-Content "$log.err" -Tail 20 -ErrorAction SilentlyContinue
    exit 1
}
