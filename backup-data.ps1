#Requires -Version 5.1
<#
    social-auto-upload 数据备份脚本
    备份内容：cookies/、db/、videos/（可配置）、conf.py
    用法：powershell -ExecutionPolicy Bypass -File backup-data.ps1
          -KeepDays 30        保留最近 30 份
          -BackupDir D:\bak   指定备份目录（默认 <数据目录>\backups）
          -IncludeVideos      额外备份视频素材（体积大，默认不备份）
#>
param(
    [int]$KeepDays = 30,
    [string]$BackupDir = "",
    [switch]$IncludeVideos
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# ---- 解析数据目录（与 conf.py 的优先级一致：环境变量 > data_dir.txt > 项目根）----
function Resolve-DataDir {
    if ($env:SAU_DATA_DIR) { return $env:SAU_DATA_DIR }
    $marker = Join-Path $Root "data_dir.txt"
    if (Test-Path $marker) {
        $raw = (Get-Content $marker -Raw -Encoding UTF8).Trim()
        if ($raw) { return $raw }
    }
    return $Root
}

$DataDir = Resolve-DataDir
if (-not (Test-Path $DataDir)) {
    Write-Host "[错误] 数据目录不存在：$DataDir" -ForegroundColor Red
    exit 1
}

if (-not $BackupDir) {
    $BackupDir = Join-Path $DataDir "backups"
}
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

# ---- 打包 ----
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipPath = Join-Path $BackupDir "sau-backup-$stamp.zip"

$items = @()
foreach ($name in @("cookies", "db")) {
    $p = Join-Path $DataDir $name
    if (Test-Path $p) { $items += $p }
}
if ($IncludeVideos) {
    $p = Join-Path $DataDir "videos"
    if (Test-Path $p) { $items += $p }
}
# 配置也一起备份，换机器时能还原数据目录设置
$confFile = Join-Path $Root "conf.py"
if (Test-Path $confFile) { $items += $confFile }
$markerFile = Join-Path $Root "data_dir.txt"
if (Test-Path $markerFile) { $items += $markerFile }

if ($items.Count -eq 0) {
    Write-Host "[跳过] 没有可备份的内容" -ForegroundColor Yellow
    exit 0
}

Write-Host "数据目录：$DataDir"
Write-Host "正在打包 $(($items | ForEach-Object { Split-Path $_ -Leaf }) -join ', ') ..."

# SQLite 可能正在写入，先做一致性快照再压缩
$tempDir = Join-Path $env:TEMP "sau-backup-$stamp"
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
try {
    foreach ($item in $items) {
        Copy-Item -Path $item -Destination $tempDir -Recurse -Force
    }
    Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $zipPath -Force
} finally {
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-Host "备份完成：$zipPath ($sizeMB MB)" -ForegroundColor Green

# ---- 清理过期备份 ----
$cutoff = (Get-Date).AddDays(-$KeepDays)
$old = Get-ChildItem -Path $BackupDir -Filter "sau-backup-*.zip" |
    Where-Object { $_.LastWriteTime -lt $cutoff }
if ($old) {
    $old | Remove-Item -Force
    Write-Host "已清理 $($old.Count) 个超过 $KeepDays 天的备份"
}

$total = (Get-ChildItem -Path $BackupDir -Filter "sau-backup-*.zip" | Measure-Object).Count
Write-Host "当前保留 $total 份备份"
