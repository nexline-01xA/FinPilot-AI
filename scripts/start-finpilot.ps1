$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is not installed or is not available on PATH.' }
try { docker info *> $null } catch { throw 'Docker Desktop is not running. Start Docker Desktop and run this again.' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }

docker compose up --build -d
docker compose ps

for ($i = 0; $i -lt 40; $i++) {
    try { Invoke-WebRequest -UseBasicParsing 'http://localhost:8000/api/v1/health' -TimeoutSec 3 | Out-Null; break }
    catch { Start-Sleep -Seconds 2 }
    if ($i -eq 39) { docker compose logs --tail 100 backend; throw 'Backend did not become healthy within 80 seconds.' }
}

Write-Host 'FinPilot is ready at http://localhost:3000' -ForegroundColor Green
Start-Process 'http://localhost:3000'
