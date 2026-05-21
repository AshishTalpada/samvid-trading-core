param(
    [int]$Tail = 120,
    [string]$LogPath = "logs\trading_system.log"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $LogPath)) {
    Write-Host "Log file not found: $LogPath" -ForegroundColor Red
    exit 1
}

if (Test-Path "data\main.pid") {
    $pidText = (Get-Content "data\main.pid" -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($pidText -and ($pidText -match '^\d+$')) {
        $engine = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
        if ($engine) {
            Write-Host "Sovereign engine running: PID $pidText" -ForegroundColor Green
        } else {
            Write-Host "main.pid points to $pidText, but that process is not running." -ForegroundColor Yellow
        }
    }
}

Write-Host "Tailing $LogPath. Press Ctrl+C to stop watching logs." -ForegroundColor Cyan
Get-Content $LogPath -Tail $Tail -Wait
