# ============================================================
# enable.ps1 — 一键启用广告拦截 (启动 mitmproxy + 系统代理指向 8080)
# 前提: Clash Verge / TUN / Mihomo 正常运行
# 链路: 应用 -> 127.0.0.1:8080 (MITM+EasyList) -> TUN -> Mihomo 分流 -> Internet
# 用法: powershell -ExecutionPolicy Bypass -File enable.ps1
# ============================================================
$base = Split-Path -Parent $MyInvocation.MyCommand.Path

$tun = Get-NetAdapter -Name "Mihomo" -ErrorAction SilentlyContinue
if (-not ($tun -and $tun.Status -eq "Up")) {
    Write-Host "[enable] 警告: Mihomo TUN 适配器未运行, 请先启动 Clash Verge TUN 模式"
    exit 1
}

Write-Host "== 1/3 启动 mitmproxy =="
& (Join-Path $base "mitm\start-mitm.ps1")

Write-Host "== 2/3 检查 CA 证书 =="
$ca = certutil -user -store Root mitmproxy 2>$null | Select-String "mitmproxy"
if (-not $ca) {
    Write-Host "[enable] mitmproxy CA 未安装, 正在安装到当前用户 Root 存储..."
    certutil -user -addstore -f Root "$env:USERPROFILE\.mitmproxy\mitmproxy-ca-cert.cer" | Out-Null
    Write-Host "[enable] CA 已安装"
} else {
    Write-Host "[enable] mitmproxy CA 已在用户 Root 存储"
}

Write-Host "== 3/3 系统代理 -> 127.0.0.1:8080 =="
& (Join-Path $base "set-system-proxy.ps1") -Server "127.0.0.1:8080"
Write-Host "== 完成: 广告拦截已启用 (回滚: restore.ps1) =="
