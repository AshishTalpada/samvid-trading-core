param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$StartIfMissing,
    [switch]$IncludeWatchdog,
    [int]$Tail = 80
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$MainLog = Join-Path $ProjectRoot "logs\trading_system.log"
$WatchdogLog = Join-Path $ProjectRoot "logs\watchdog.log"
$UvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LegacyPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$Python = if (Test-Path $UvPython) { $UvPython } else { $LegacyPython }

function Test-MainProcess {
    $escaped = [regex]::Escape($ProjectRoot)
    $pattern = "$escaped.*src[\\/]+main.py"
    return [bool](Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -match $pattern })
}

function Start-MainProcess {
    if (-not (Test-Path $Python)) {
        throw "Runtime Python not found: $Python"
    }
    Start-Process -FilePath $Python `
        -ArgumentList "src\main.py" `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden
}

function Wait-ForFile {
    param([string]$Path)
    while (-not (Test-Path $Path)) {
        Write-Host "[logs] Waiting for $Path ..."
        Start-Sleep -Seconds 2
    }
}

Set-Location $ProjectRoot

if ($StartIfMissing -and -not (Test-MainProcess)) {
    Write-Host "[logs] main.py is not running; starting it in the background..."
    Start-MainProcess
    Start-Sleep -Seconds 3
}

Wait-ForFile $MainLog
if ($IncludeWatchdog) {
    Wait-ForFile $WatchdogLog
}

Write-Host "[logs] Following live system logs. Press Ctrl+C to stop viewing logs; the engine is not stopped."
Write-Host "[logs] Main: $MainLog"
if ($IncludeWatchdog) {
    Write-Host "[logs] Watchdog: $WatchdogLog"
}

if ($IncludeWatchdog) {
    Get-Content -Path $MainLog, $WatchdogLog -Tail $Tail -Wait
} else {
    Get-Content -Path $MainLog -Tail $Tail -Wait
}
