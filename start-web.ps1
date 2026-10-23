<#
    social-auto-upload Web 控制台启动脚本
    用法：右键「使用 PowerShell 运行」，或双击 start-win.bat
#>
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "=================================================="
Write-Host "  social-auto-upload  Web 控制台"
Write-Host "=================================================="
Write-Host ""

$Python = Join-Path $Root ".venv/Scripts/python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "[错误] 没找到虚拟环境：$Python" -ForegroundColor Red
    Write-Host "       请先按 docs/install.md 安装依赖。"
    Read-Host "按回车退出"
    exit 1
}

# ---- 1. 按需构建前端 ----
$Dist = Join-Path $Root "sau_frontend/dist/index.html"
if (-not (Test-Path $Dist)) {
    Write-Host "[1/3] 首次运行，正在构建前端 ..." -ForegroundColor Cyan
    Push-Location (Join-Path $Root "sau_frontend")
    if (-not (Test-Path "node_modules")) {
        & npm install --no-audit --no-fund
    }
    & npm run build
    $buildOk = ($LASTEXITCODE -eq 0)
    Pop-Location
    if (-not $buildOk) {
        Write-Host "[错误] 前端构建失败，请检查 Node.js 版本（需要 18+）。" -ForegroundColor Red
        Read-Host "按回车退出"
        exit 1
    }
    Write-Host "      前端构建完成。" -ForegroundColor Green
} else {
    Write-Host "[1/3] 前端已构建，跳过。（需要重建时执行：cd sau_frontend; npm run build）"
}

# ---- 2. 启动后端 ----
$Port = 5409
$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[2/3] 端口 $Port 已被占用，直接复用现有服务。" -ForegroundColor Yellow
} else {
    Write-Host "[2/3] 启动后端 http://127.0.0.1:$Port ..."
    $env:PYTHONIOENCODING = "utf-8"
    $env:SAU_WEB_PORT = "$Port"
    $logDir = Join-Path $Root "logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    Start-Process -FilePath $Python `
        -ArgumentList "-u", "sau_server.py" `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "_web_out.log") `
        -RedirectStandardError (Join-Path $logDir "_web_err.log")
}

# ---- 3. 等待就绪 ----
Write-Host "[3/3] 等待服务就绪 ..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($resp.code -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

Write-Host ""
if ($ready) {
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host "  已启动： http://127.0.0.1:$Port" -ForegroundColor Green
    Write-Host "  停止服务：双击 stop-win.bat"
    Write-Host "==================================================" -ForegroundColor Green
    Start-Process "http://127.0.0.1:$Port"
} else {
    Write-Host "[警告] 30 秒内没等到服务就绪。" -ForegroundColor Yellow
    Write-Host "       请查看 logs/_web_err.log 排查。"
}

Write-Host ""
Read-Host "按回车关闭本窗口（服务会继续在后台运行）"
