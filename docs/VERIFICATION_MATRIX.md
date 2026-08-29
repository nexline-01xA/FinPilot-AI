# FinPilot AI — Verification Matrix

## Canonical GitHub verification

FinPilot's canonical source now lives in this repository. The v1.2 runtime baseline has been exercised both independently before import and through GitHub Actions after import.

### Automated regression suites

- **84/84 deterministic core tests** — restored in `finpilot/tests/test_core_full_01.py` through `test_core_full_08.py`
- **21/21 service-layer tests**
- **18/18 FastAPI HTTP integration tests**
- **123/123 total application/core tests**

### Runtime and product verification

GitHub Actions verifies:

- fresh dependency installation on Python 3.12
- deterministic core evaluation
- 62 reconciliation cases and 93.5% reconciliation health on the seeded NovaCart scenario
- all 6 injected scenarios detected
- forecast benchmark remains measured against the naive baseline
- FastAPI HTTP routes, role enforcement, tenant isolation, approvals and audit chain
- production dependency security audit (`npm audit --omit=dev --audit-level=high`)
- production Next.js build
- `docker compose config`
- backend and frontend Docker image builds
- actual `docker compose up -d`
- live backend `/health` and `/overview` responses
- live frontend HTTP response on port 3000
- live Q1 Controller request as VIEWER routes to `cash_weakening`
- live Q3 Controller request as ANALYST routes to `resolve_top_priority`
- clean Docker teardown after the smoke test

## v1.2 integration fixes verified

- TestClient enters/exits FastAPI lifespan correctly.
- Controller frontend sends an explicit demo role; AI Controller defaults to ANALYST for the flagship action proposal flow.
- Server-rendered Next.js calls use `INTERNAL_API_URL=http://backend:8000/api/v1`; browser calls use `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`.
- Docker sets `SQLITE_PATH=/app/data/finpilot.db` so demo persistence lands on the mounted volume.
- User-visible rupee presentation uses `₹` without changing integer-paise arithmetic.
- NumPy is an explicit backend runtime dependency.
- Next.js/React were upgraded to patched current releases and production dependencies are audit-gated in CI.
- PostgreSQL remains an explicitly documented migration target, not falsely presented as the active persistence backend; SQLite is the verified demo runtime.

## Deliberately outside automated CI

- Human visual/UX review in a desktop browser on the Windows development machine.
- Live Anthropic network round-trip when an API key is intentionally configured. Demo reasoning mode remains the default and is labelled honestly.
- SQLAlchemy/PostgreSQL migration of the active service layer.

None of those are required for the deterministic NovaCart demo workflow to boot and run.

## Verification commands

```bash
python -m unittest discover -s finpilot/tests -p 'test*.py' -v
cd backend && python -m unittest tests.test_services -v
cd backend && pytest tests/test_api.py -v
cd frontend && npm install && npm audit --omit=dev --audit-level=high && npm run build
cp .env.example .env
docker compose up --build
```

The canonical CI workflow is `.github/workflows/ci.yml` and runs on pull requests to `main` and pushes to `main`.
