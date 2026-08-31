# Local execution

Windows PowerShell from repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-finpilot.ps1
```

This checks Docker Desktop, creates `.env` from `.env.example` when absent, starts Compose, waits for the backend health endpoint, and opens `http://localhost:3000`.
