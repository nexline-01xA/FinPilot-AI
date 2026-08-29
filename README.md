# FinPilot AI

### Your autonomous finance operations layer — with humans in control.

FinPilot AI is an evidence-grounded finance controller for digital businesses, built for **Razorpay AI Builder Internship 2026 — Track 4: AI Finance Controller**.

It reconciles payments and settlements, computes cash-flow intelligence, detects anomalies, forecasts cash, answers finance questions through an allowlisted agent tool layer, and routes operational actions through human approval, execution verification, and an audit trail.

## Core principle

> **The LLM is not the source of financial truth.**

Money, balances, reconciliation, anomaly scores, forecast calculations, approval state and execution state are deterministic. AI reasons over verified tool outputs and may only propose governed actions.

```text
OBSERVE → RECONCILE → ANALYSE → FORECAST → DETECT → EXPLAIN
        → RECOMMEND → REQUEST APPROVAL → ACT → VERIFY → AUDIT
```

## Verified runtime baseline

The canonical GitHub branch is continuously checked by `.github/workflows/ci.yml`.

- **84/84 deterministic core tests**
- **21/21 application-service tests**
- **18/18 FastAPI HTTP integration tests**
- **123/123 total tests**
- Fresh SQLite bootstrap
- Core evaluation: 62 reconciliation cases, 93.5% reconciliation health, 6/6 injected scenarios detected
- Production dependency security audit
- Production Next.js build
- Docker Compose validation and backend/frontend image builds
- Actual Docker stack startup
- Live backend health + overview smoke checks
- Live frontend HTTP smoke check
- Live Q1 Controller request as VIEWER
- Live Q3 Controller request as ANALYST

The exact verification boundary and intentionally deferred items are documented in `docs/VERIFICATION_MATRIX.md`.

## Demo

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Frontend: `http://localhost:3000`
- FastAPI docs: `http://localhost:8000/docs`

The backend automatically seeds the deterministic **NovaCart Technologies** demo dataset on first start and preserves state across restarts.

## The three flagship questions

1. **Why is our cash position expected to weaken next week?**
2. **What requires my attention first?**
3. **Can you resolve the most important issue?**

Q3 does not execute autonomously. It produces an `AWAITING_APPROVAL` action. The Approvals page demonstrates separation of duties: ANALYST proposes, APPROVER decides, then FinPilot executes a sandbox effect, verifies it from persisted state, and records the full audit chain.

## Repository layout

```text
finpilot/        deterministic finance engine + full core regression suite
backend/         FastAPI routes, application services, schemas, Postgres migration target
frontend/        Next.js / TypeScript finance-operations UI
docs/            architecture, threat model, demo script, verification matrix
docker-compose.yml
.env.example
```

## Safety posture

- Synthetic/demo financial data only.
- Integer paise for authoritative money calculations.
- Merchant-scoped reads/writes.
- Explicit read/write agent tool allowlist.
- High-risk operations cannot auto-execute.
- Approval execution uses persisted-state verification and duplicate-effect constraints.
- Demo roles are not production authentication; see `docs/THREAT_MODEL.md`.
- PostgreSQL is a documented migration target; **SQLite is intentionally the active verified demo runtime**.
- Live Anthropic tool-calling is optional; default demo reasoning mode is labelled honestly.

## Documentation

- `docs/ARCHITECTURE.md`
- `docs/DEMO_SCRIPT.md`
- `docs/THREAT_MODEL.md`
- `docs/VERIFICATION_MATRIX.md`
- `docs/LOCAL_SETUP.md`
- `docs/CORE_LIMITATIONS.md`
