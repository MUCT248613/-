# Kill VirtualStudent Sandbox backend + frontend process trees.
#
# Why this exists:
#   The backend runs under scripts/supervise_backend.py, which auto-restarts
#   uvicorn forever. Killing only the port-listening uvicorn worker is useless
#   -- the supervisor immediately spawns a new worker that re-grabs port 6668,
#   causing "[Errno 10048] port already in use". We must terminate the
#   SUPERVISOR process itself (matched by its command line), plus anything that
#   still listens on the two ports (covers the frontend vite dev server).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kill_services.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kill_services.ps1 -DryRun
param(
    [switch]$DryRun
)

$ErrorActionPreference = 'SilentlyContinue'
$BackendPort  = 6668
$FrontendPort = 4000

function Kill-Tree([int]$TargetPid, [string]$Reason) {
    if ($TargetPid -le 0) { return }
    if ($DryRun) {
        Write-Host ("  [dry-run] would kill pid={0}  ({1})" -f $TargetPid, $Reason)
    } else {
        & taskkill /PID $TargetPid /T /F 2>$null | Out-Null
        Write-Host ("  killed pid={0}  ({1})" -f $TargetPid, $Reason)
    }
}

Write-Host "Stopping VirtualStudent Sandbox services ..."

# 1) Kill the backend supervisor and any orphan uvicorn worker by command line.
#    'supervise_backend' and 'src.api.main' are project-specific, so this will
#    not touch unrelated processes from other projects.
$procs = Get-CimInstance Win32_Process
foreach ($p in $procs) {
    $cl = $p.CommandLine
    if (-not $cl) { continue }
    if ($cl -like '*supervise_backend*') {
        Kill-Tree $p.ProcessId 'backend supervisor'
    } elseif ($cl -like '*src.api.main*') {
        Kill-Tree $p.ProcessId 'uvicorn worker'
    }
}

# 2) Kill whatever still listens on the two ports. This is precise (it only
#    affects the actual listeners) and covers the frontend, whose vite dev
#    server has no supervisor.
foreach ($port in @($BackendPort, $FrontendPort)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen
    foreach ($c in $conns) {
        Kill-Tree $c.OwningProcess ("listener on port {0}" -f $port)
    }
}

Write-Host "Done."
