# FinPilot — start here

On Windows, from the repository root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-finpilot.ps1
```

The launcher creates `.env` when needed, starts Docker Compose, waits for backend health, and opens the application at http://localhost:3000.
