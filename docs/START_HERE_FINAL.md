# Start FinPilot

Run from repository root in Windows PowerShell:
`powershell -ExecutionPolicy Bypass -File .\scripts\start-finpilot.ps1`

The script verifies Docker Desktop, creates `.env` when needed, starts the Compose stack, waits for backend health, and opens http://localhost:3000.
