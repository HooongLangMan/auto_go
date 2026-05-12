$ErrorActionPreference = "Stop"

$required = @(
    "POSTGRES_PASSWORD",
    "API_FOOTBALL_KEY"
)

$missing = @()
foreach ($name in $required) {
    if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue)) {
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    Write-Host "缺少环境变量：" ($missing -join ", ")
    Write-Host "请先在当前 PowerShell 会话里设置它们，再重新运行。"
    exit 1
}

if (-not $env:POSTGRES_HOST) { $env:POSTGRES_HOST = "localhost" }
if (-not $env:POSTGRES_PORT) { $env:POSTGRES_PORT = "32768" }
if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = "postgres" }
if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = "postgres" }

$python = "D:\code_app\annconda_use\envs\auto_football\python.exe"

Write-Host "[1/4] 检查数据库表..."
& $python -m auto_football.cli init-db

Write-Host "[2/4] 生成当天内容（预览模式，不发帖）..."
$env:RUN_DRY = "true"
$env:PUBLISH_ENABLED = "false"
& $python -m auto_football.cli run --date 2026-04-22

Write-Host "[3/4] 生成预览页..."
& $python -m auto_football.cli preview --limit 3

Write-Host "[4/4] 打开预览目录页..."
Start-Process "D:\auto_go\generated\previews\latest_preview.html"

Write-Host ""
Write-Host "预览页已打开。"
Write-Host "数据库查看页：http://localhost:8082"
