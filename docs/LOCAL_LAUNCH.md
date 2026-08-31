# Local launch

On Windows, from the repository root:

    powershell -ExecutionPolicy Bypass -File .\scripts\start-finpilot.ps1

The launcher checks Docker Desktop, creates `.env` from `.env.example` when needed, starts Compose, waits for backend health, and opens the frontend at http://localhost:3000.

To stop:

    powershell -ExecutionPolicy Bypass -File .\scripts\stop-finpilot.ps1
