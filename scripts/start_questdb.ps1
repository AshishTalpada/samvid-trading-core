# Start QuestDB in Docker for the trading stack (Windows PowerShell)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found. Install Docker Desktop, then retry." -ForegroundColor Red
    exit 1
}

docker compose -f docker-compose.questdb.yml up -d

$container = docker ps --filter "name=trading_questdb" --format "{{.Names}}|{{.Ports}}" |
    Select-Object -First 1
if (-not $container) {
    Write-Host "QuestDB container trading_questdb is not running after compose startup." -ForegroundColor Red
    docker ps -a --filter "name=questdb" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    exit 1
}

$ports = ($container -split "\|", 2)[1]
$required = @("9000", "9009", "8812")
$missing = @()
foreach ($port in $required) {
    if ($ports -notmatch "0\.0\.0\.0:$port->" -and $ports -notmatch "\[::\]:$port->") {
        $missing += $port
    }
}

if ($missing.Count -gt 0) {
    Write-Host "QuestDB is running but missing host port binding(s): $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Current container ports: $ports" -ForegroundColor Yellow
    Write-Host "Stop anonymous/unbound QuestDB containers and rerun this script." -ForegroundColor Yellow
    exit 1
}

Write-Host "QuestDB is running with host ports 9000, 9009, and 8812 published." -ForegroundColor Green
Write-Host "Web console: http://127.0.0.1:9000" -ForegroundColor Green
Write-Host "Use QUESTDB_HOST=127.0.0.1 QUESTDB_PORT=9009 QUESTDB_PG_PORT=8812 for local runs." -ForegroundColor Cyan
