@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0follow_live_logs.ps1" -StartIfMissing -IncludeWatchdog
