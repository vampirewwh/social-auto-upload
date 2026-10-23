# 停止 social-auto-upload Web 服务
$ErrorActionPreference = "SilentlyContinue"
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'sau_server\.py|sau_backend\.py' }
if (-not $procs) {
    Write-Host "没有正在运行的 Web 服务。" -ForegroundColor Yellow
    exit 0
}
foreach ($p in $procs) {
    Write-Host ("停止 PID " + $p.ProcessId) -ForegroundColor Cyan
    Stop-Process -Id $p.ProcessId -Force
}
Start-Sleep -Seconds 1
$still = Get-NetTCPConnection -LocalPort 5409 -State Listen -ErrorAction SilentlyContinue
if ($still) { Write-Host "端口 5409 仍被占用。" -ForegroundColor Yellow } else { Write-Host "已停止。" -ForegroundColor Green }
