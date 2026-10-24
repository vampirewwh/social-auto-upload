#Requires -Version 5.1
<#
    social-auto-upload 开机自启 + 每日备份 一键配置
    用法（右键「使用 PowerShell 运行」，或在终端执行）：
        powershell -ExecutionPolicy Bypass -File setup-autostart.ps1
        powershell -ExecutionPolicy Bypass -File setup-autostart.ps1 -Remove   # 卸载
#>
param(
    [switch]$Remove,
    [string]$BackupTime = "03:00"
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskStart = "SAU-WebConsole"
$TaskBackup = "SAU-DataBackup"
$startScript = Join-Path $Root "start-web.ps1"
$backupScript = Join-Path $Root "backup-data.ps1"
$powershell = (Get-Command powershell.exe).Source

if ($Remove) {
    foreach ($name in @($TaskStart, $TaskBackup)) {
        $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($existing) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Host "已移除计划任务：$name" -ForegroundColor Yellow
        }
    }
    Write-Host "[完成] 开机自启与定时备份已关闭。" -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $startScript)) {
    Write-Host "[错误] 找不到 $startScript" -ForegroundColor Red
    exit 1
}

# ---- 1. 开机自启：登录后静默启动 Web 服务 ----
$startAction = New-ScheduledTaskAction `
    -Execute $powershell `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$startScript`" -Quiet" `
    -WorkingDirectory $Root
$startTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$startSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskStart `
    -Action $startAction -Trigger $startTrigger -Settings $startSettings `
    -Description "SAU 自媒体自动化 - 登录后自动启动 Web 控制台" `
    -Force | Out-Null
Write-Host "[1/2] 已设置开机自启：$TaskStart" -ForegroundColor Green

# ---- 2. 每日备份 ----
if (Test-Path $backupScript) {
    $backupAction = New-ScheduledTaskAction `
        -Execute $powershell `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$backupScript`"" `
        -WorkingDirectory $Root
    $backupTrigger = New-ScheduledTaskTrigger -Daily -At $BackupTime
    $backupSettings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable

    Register-ScheduledTask -TaskName $TaskBackup `
        -Action $backupAction -Trigger $backupTrigger -Settings $backupSettings `
        -Description "SAU 自媒体自动化 - 每日备份 cookies 与数据库" `
        -Force | Out-Null
    Write-Host "[2/2] 已设置每日备份：$TaskBackup（每天 $BackupTime）" -ForegroundColor Green
} else {
    Write-Host "[2/2] 跳过：未找到 backup-data.ps1" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  配置完成" -ForegroundColor Green
Write-Host "  下次登录 Windows 时会自动启动 Web 服务"
Write-Host "  卸载：powershell -ExecutionPolicy Bypass -File setup-autostart.ps1 -Remove"
Write-Host "==================================================" -ForegroundColor Cyan
