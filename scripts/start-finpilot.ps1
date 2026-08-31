$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not installed or not available on PATH. Install/start Docker Desktop, then run this script again.'
}

try {
    docker info *> $null
} catch {
    throw 'Docker Desktop is not running. Start Docker Desktop, wait for the engine to become ready, then run this script again.'
}

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
}

Write-Host 'Starting FinPilot AI...' -ForegroundColor Cyan
docker compose up --build -d

Write-Host ''
Write-Host 'Container status:' -ForegroundColor Cyan
docker compose ps

Write-Host ''
Write-Host 'Waiting for backend health...' -ForegroundColor Cyan
for ($i = 0; $i -lt 40; $i++) {
    try {
        Invoke-WebRequest -UseBasicParsing 'http://localhost:8000/api/v1/health' -TimeoutSec 3 | Out-Null
        break
    } catch {
        Start-Sleep -Seconds 2
    }
    if ($i -eq 39) {
        docker compose logs --tail 100 backend
        throw 'Backend did not become healthy within 80 seconds.'
    }
}

Write-Host 'FinPilot is ready: http://localhost:3000' -ForegroundColor Green
Start-Process 'http://localhost:3000'
