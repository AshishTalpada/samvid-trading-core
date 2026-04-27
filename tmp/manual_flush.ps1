# Sovereign Flush Script (Ghosts Purification)
Write-Host "Initiating Sovereign Resource Flush (Port Recovery)..."

$targets = @("tws", "ibgateway", "python", "pythonw")
$myPid = $pid
$foundGhosts = 0

foreach ($target in $targets) {
    $procs = Get-Process -Name $target -ErrorAction SilentlyContinue
    foreach ($proc in $procs) {
        if ($proc.Id -ne $myPid) {
            Write-Host "Purifying Ghost: $($proc.ProcessName) (PID: $($proc.Id))..."
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $foundGhosts++
        }
    }
}

Write-Host "Purification complete - $foundGhosts component sectors flushed."
