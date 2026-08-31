# Local FinPilot launch

From the repository root on Windows:

- Double-click `scripts/start-finpilot.cmd` to build/start the demo and open `http://localhost:3000`.
- Use `scripts/stop-finpilot.ps1` to stop the stack.

The launcher creates `.env` from `.env.example` when needed, checks that Docker Desktop is running, starts Compose, waits for the backend health endpoint, and then opens the frontend.
