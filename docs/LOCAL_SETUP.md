# Local Setup

## With Docker

```bash
cp .env.example .env
docker compose up --build
```

Backend: http://localhost:8000/docs · Frontend: http://localhost:3000

The demo stack runs on SQLite. The backend seeds NovaCart automatically on first startup and reuses existing state on restart.

## Without Docker

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Tests
```bash
python3 -m finpilot.tests.test_core -v
cd backend && python3 -m unittest tests.test_services -v
cd backend && pytest tests/test_api.py -v
```

### Frontend
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
npm run dev
```

## PostgreSQL target

`backend/app/db_pg/` and `docker-compose.postgres.yml` are the migration target. The verified demo runtime remains SQLite until the SQLAlchemy persistence path is genuinely wired and tested.
