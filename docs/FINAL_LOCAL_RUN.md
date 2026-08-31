# Final local run

Windows one-command startup:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-finpilot.ps1
```

Open http://localhost:3000 when the script reports that the backend is healthy.

Stop with:

```powershell
docker compose down
```
