param(
    [int]$Tail = 120,
    [string]$LogPath = "logs\trading_system.log",
    [int]$PollMs = 750,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
try { chcp 65001 | Out-Null } catch {}

function Get-EngineStatus {
    $mainPid = $null
    $watchdogPid = $null
    $heartbeatAge = $null

    if (Test-Path "data\main.pid") {
        $pidText = (Get-Content "data\main.pid" -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($pidText -match '^\d+$') { $mainPid = [int]$pidText }
    }
    if (Test-Path "data\watchdog.pid") {
        $pidText = (Get-Content "data\watchdog.pid" -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($pidText -match '^\d+$') { $watchdogPid = [int]$pidText }
    }
    if (Test-Path "data\task_heartbeats.json") {
        try {
            $hb = Get-Content "data\task_heartbeats.json" -Encoding UTF8 -Raw | ConvertFrom-Json
            if ($hb.heartbeats.BRAIN_PRIMARY) {
                $heartbeatAge = [math]::Round(([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [double]$hb.heartbeats.BRAIN_PRIMARY), 1)
            }
        } catch {}
    }

    $mainAlive = $false
    $watchdogAlive = $false
    if ($mainPid) { $mainAlive = [bool](Get-Process -Id $mainPid -ErrorAction SilentlyContinue) }
    if ($watchdogPid) { $watchdogAlive = [bool](Get-Process -Id $watchdogPid -ErrorAction SilentlyContinue) }

    [pscustomobject]@{
        MainPid = $mainPid
        MainAlive = $mainAlive
        WatchdogPid = $watchdogPid
        WatchdogAlive = $watchdogAlive
        HeartbeatAge = $heartbeatAge
    }
}

function Write-EngineStatus {
    $s = Get-EngineStatus
    $mainText = if ($s.MainPid) { "$($s.MainPid) alive=$($s.MainAlive)" } else { "missing" }
    $watchText = if ($s.WatchdogPid) { "$($s.WatchdogPid) alive=$($s.WatchdogAlive)" } else { "missing" }
    $hbText = if ($null -ne $s.HeartbeatAge) { "$($s.HeartbeatAge)s" } else { "unknown" }
    Write-Host "[log-view] main=$mainText | watchdog=$watchText | brain heartbeat age=$hbText" -ForegroundColor Cyan
}

function Write-NewUtf8Text {
    param(
        [string]$Path,
        [long]$Offset
    )

    $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        if ($Offset -gt $fs.Length) { $Offset = 0 }
        $fs.Seek($Offset, [System.IO.SeekOrigin]::Begin) | Out-Null
        $reader = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8, $true, 4096, $true)
        try {
            $text = $reader.ReadToEnd()
            if ($text.Length -gt 0) {
                [Console]::Write($text)
            }
            return $fs.Position
        } finally {
            $reader.Dispose()
        }
    } finally {
        $fs.Dispose()
    }
}

if (-not (Test-Path $LogPath)) {
    Write-Host "Log file not found: $LogPath" -ForegroundColor Red
    exit 1
}

Write-EngineStatus
$item = Get-Item $LogPath
Write-Host "[log-view] tailing $($item.FullName) as UTF-8. Press Ctrl+C to stop." -ForegroundColor Cyan

Get-Content $LogPath -Encoding UTF8 -Tail $Tail
$position = (Get-Item $LogPath).Length
$lastStatus = Get-Date

while ($true) {
    Start-Sleep -Milliseconds $PollMs
    if (-not (Test-Path $LogPath)) {
        Write-Host "`n[log-view] waiting for log file to reappear: $LogPath" -ForegroundColor Yellow
        $position = 0
        continue
    }

    $current = Get-Item $LogPath
    if ($current.Length -lt $position) {
        Write-Host "`n[log-view] log rotated/truncated; reopening $LogPath" -ForegroundColor Yellow
        $position = 0
    }
    if ($current.Length -gt $position) {
        $position = Write-NewUtf8Text -Path $LogPath -Offset $position
    }

    if ($Status -and ((Get-Date) - $lastStatus).TotalSeconds -ge 30) {
        Write-EngineStatus
        $lastStatus = Get-Date
    }
}
