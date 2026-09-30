# 设置 Windows 系统代理并广播刷新 (WinINET)
# 用法: powershell -File set-system-proxy.ps1 [-Server "127.0.0.1:8080"] [-Enable $true/$false]
param(
    [string]$Server = "127.0.0.1:8080",
    [bool]$Enable = $true
)

$reg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
if ($Enable) {
    Set-ItemProperty $reg ProxyServer $Server
    Set-ItemProperty $reg ProxyEnable 1
} else {
    Set-ItemProperty $reg ProxyEnable 0
}

# 广播设置变更, 让运行中的浏览器立即生效
$sig = @"
using System;
using System.Runtime.InteropServices;
public class WinINET {
    [DllImport("wininet.dll", SetLastError=true)]
    public static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
}
"@
Add-Type -TypeDefinition $sig -Language CSharp
[WinINET]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null  # INTERNET_OPTION_SETTINGS_CHANGED
[WinINET]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null  # INTERNET_OPTION_REFRESH

$now = Get-ItemProperty $reg
Write-Host ("[set-system-proxy] ProxyEnable={0} ProxyServer={1}" -f $now.ProxyEnable, $now.ProxyServer)
