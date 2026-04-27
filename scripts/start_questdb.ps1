# Start QuestDB in Docker for the trading stack (Windows PowerShell)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found. Install Docker Desktop, then retry." -ForegroundColor Red
    exit 1
}

docker compose -f docker-compose.questdb.yml up -d
Write-Host "QuestDB starting. Web console: http://127.0.0.1:9000" -ForegroundColor Green
Write-Host "Ensure .env matches QUESTDB_HOST=127.0.0.1 QUESTDB_PORT=9009 QUESTDB_PG_PORT=8812" -ForegroundColor Cyan
