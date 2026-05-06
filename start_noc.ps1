# ╔══════════════════════════════════════════════════╗
# ║        Emircom NOC Agent — One-Click Start       ║
# ║  Run from project root:  .\start_noc.ps1         ║
# ╚══════════════════════════════════════════════════╝

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT

function Write-Step($msg) {
    Write-Host "`n[$([datetime]::Now.ToString('HH:mm:ss'))] $msg" -ForegroundColor Cyan
}

function Write-OK($msg) {
    Write-Host "  OK  $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "  !!  $msg" -ForegroundColor Yellow
}

# ── 1. Docker Desktop ────────────────────────────────────────────────────────
Write-Step "Checking Docker Desktop..."
$dockerRunning = $false
try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
} catch {}

if (-not $dockerRunning) {
    Write-Warn "Docker not running — starting Docker Desktop..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "  Waiting for Docker engine" -NoNewline
    $maxWait = 60
    $waited  = 0
    while ($waited -lt $maxWait) {
        Start-Sleep 3
        $waited += 3
        Write-Host "." -NoNewline
        try {
            docker info 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { break }
        } catch {}
    }
    Write-Host ""
    if ($waited -ge $maxWait) {
        Write-Warn "Docker took too long to start. Try running the script again once Docker Desktop is open."
        exit 1
    }
}
Write-OK "Docker is running"

# ── 2. GLPI Containers ───────────────────────────────────────────────────────
Write-Step "Starting GLPI containers (mariadb + glpi)..."
docker start mariadb 2>$null | Out-Null
docker start glpi    2>$null | Out-Null
Start-Sleep 4
Write-OK "GLPI containers started  →  http://localhost  (login: glpi / glpi)"

# ── 3. FastAPI Backend ───────────────────────────────────────────────────────
Write-Step "Starting FastAPI backend on port 8001..."
$backendCmd = "Set-Location '$ROOT'; .\venv\Scripts\Activate.ps1; python -m uvicorn react.backend.main:app --port 8001; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
Start-Sleep 3
Write-OK "Backend started  →  http://localhost:8001"

# ── 4. GLPI Agent Worker ─────────────────────────────────────────────────────
Write-Step "Starting GLPI NOC Agent worker..."
$agentCmd = "Set-Location '$ROOT'; .\venv\Scripts\Activate.ps1; python glpi\glpi_agent.py; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $agentCmd -WindowStyle Normal
Start-Sleep 2
Write-OK "GLPI Agent started (polling every 15 seconds)"

# ── 5. Meraki Webhook Receiver ───────────────────────────────────────────────
Write-Step "Starting Meraki Webhook Receiver on port 8002..."
$merakiCmd = "Set-Location '$ROOT'; .\venv\Scripts\Activate.ps1; python -m uvicorn meraki.webhook_receiver:app --host 0.0.0.0 --port 8002; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $merakiCmd -WindowStyle Normal
Start-Sleep 2
Write-OK "Meraki receiver started  →  http://localhost:8002/webhook/meraki"

# ── 6. React Frontend ────────────────────────────────────────────────────────
Write-Step "Starting React frontend on port 5173..."
$frontendCmd = "Set-Location '$ROOT\frontend'; npm run dev; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
Start-Sleep 4
Write-OK "Frontend started  →  http://localhost:5173"

# ── Summary ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "======================================================" -ForegroundColor DarkGray
Write-Host "  All services are running!" -ForegroundColor White
Write-Host ""
Write-Host "  React Dashboard     ->  http://localhost:5173" -ForegroundColor Cyan
Write-Host "  GLPI                ->  http://localhost        (admin/admin)" -ForegroundColor Cyan
Write-Host "  API Docs            ->  http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "  Meraki Webhook      ->  http://localhost:8003/webhook/meraki" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "To push fresh mock tickets to GLPI:" -ForegroundColor Gray
Write-Host "  .\venv\Scripts\python.exe glpi\push_to_glpi.py" -ForegroundColor Gray
Write-Host ""
