# Architecture

## Layering

```
Next.js frontend  →  FastAPI routes  →  Application services  →  Deterministic core  →  Storage
```

**The deterministic core (`finpilot/core`) is the trust boundary.** Every financial number in this product — cash position, reconciliation status, forecast, anomaly — is computed there, by tested Python, never by an LLM.

**Application services (`backend/app/services`) exist as a distinct layer for testability without the framework.** Routes call services; services call the core.

**FastAPI routes are intentionally thin.** They do argument parsing, dependency injection, role enforcement, and response-model wrapping.

**SQLAlchemy/PostgreSQL (`backend/app/db_pg/`) exists in parallel with, not instead of, the tested SQLite core.** The running application today still goes through `finpilot/core/db.py`'s raw `sqlite3` connection. The Postgres layer is a migration target, not decorative runtime infrastructure.

## Request flow

```
Next.js page
  → FastAPI route
    → request-scoped SQLite connection + merchant context
      → application service
        → deterministic core / persisted derived state
      → Pydantic response model
    ← JSON
```

## Agent architecture

Two agents share one allowlisted tool registry (`finpilot/core/tool_registry.py`):

- **`DeterministicDemoAgent`** — the verified demo path. Answers the required demo questions by composing tested core reads.
- **`ClaudeAgentProvider`** — a real tool-calling loop against Anthropic Messages API, written but not end-to-end network verified in the build sandbox.

Neither can execute a financial action directly — `prepare_action` only creates an `AWAITING_APPROVAL` row.

## Approval and audit chain

```
propose_action → AWAITING_APPROVAL
  → decide(approved=True) → APPROVED
    → execute() → EXECUTING
      → domain effect written
      → re-read back to verify → SUCCEEDED
      → on exception: rollback → FAILED
        → retry() [human-authorized] → APPROVED → execute() again
```

Every protected transition writes audit evidence transactionally with the state change it describes.

## Multi-tenancy

Merchant-owned reads/writes are scoped by merchant context. Cross-tenant lookup/execution paths are regression-tested in the core and HTTP integration suite.
