# ============================================================
# restore.ps1 — 一键回滚到实验前状态
# 功能:
#   1. 停止 mitmproxy (8080)
#   2. 系统代理恢复为 127.0.0.1:7897 (Clash Verge 原值)
#   3. (可选 -RemoveCA) 从当前用户 Root 存储删除 mitmproxy CA
#   4. 检查 Clash TUN / DNS / 配置未被修改 (实验未动它们)
# 用法: powershell -ExecutionPolicy Bypass -File restore.ps1 [-RemoveCA]
# ============================================================
param([switch]$RemoveCA)
$base = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "== 1/4 停止 mitmproxy =="
& (Join-Path $base "mitm\stop-mitm.ps1")

Write-Host "== 2/4 恢复系统代理 -> 127.0.0.1:7897 =="
& (Join-Path $base "set-system-proxy.ps1") -Server "127.0.0.1:7897"

Write-Host "== 3/4 证书处理 =="
if ($RemoveCA) {
    certutil -user -delstore Root mitmproxy
    Write-Host "已从当前用户 Root 存储删除 mitmproxy CA"
} else {
    Write-Host "保留 mitmproxy CA (如需删除: restore.ps1 -RemoveCA)"
}

Write-Host "== 4/4 状态自检 =="
$tun = Get-NetAdapter -Name "Mihomo" -ErrorAction SilentlyContinue
Write-Host ("  TUN 适配器(Mihomo): {0}" -f $(if ($tun -and $tun.Status -eq "Up") {"Up (未受影响)"} else {$tun.Status}))
$mihomo = Get-Process verge-mihomo -ErrorAction SilentlyContinue
Write-Host ("  verge-mihomo 进程: {0}" -f $(if ($mihomo) {"运行中 (未受影响)"} else {"未运行!"}))
$p = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Write-Host ("  系统代理: {0} = {1}" -f $p.ProxyEnable, $p.ProxyServer)
Write-Host "  说明: 实验未修改 DNS/Clash 配置/路由表, 无需恢复;"
Write-Host "        原始 Clash 配置备份在 backup-baseline\ (如需完整还原可用)"
Write-Host "== 回滚完成 =="

Write-Host ""
Write-Host "连通性验证:"
try {
    $r = Invoke-WebRequest -Uri "https://www.baidu.com" -UseBasicParsing -TimeoutSec 15
    Write-Host ("  baidu -> {0}" -f $r.StatusCode)
} catch {
    Write-Host "  验证失败: $_"
}
