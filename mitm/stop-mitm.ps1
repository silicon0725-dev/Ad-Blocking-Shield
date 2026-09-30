# 停止 mitmproxy
$conns = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if (-not $conns) {
    Write-Host "[stop-mitm] 8080 未在监听, 无需停止"
    exit 0
}
foreach ($c in $conns) {
    $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($p -and $p.ProcessName -match "python|mitmdump|mitmproxy") {
        Stop-Process -Id $p.Id -Force
        Write-Host "[stop-mitm] 已停止 $($p.ProcessName) PID=$($p.Id)"
    }
}
