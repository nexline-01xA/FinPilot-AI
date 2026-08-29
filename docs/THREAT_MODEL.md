# Threat Model

## Scope
This document covers the demo application as built: a synthetic-data finance controller, not a production system handling real money. Treat every "demo-only" item below as a hard blocker to any real deployment, not a nice-to-have.

## What's real security work

- **Tenant isolation**: service/core reads and writes are merchant-scoped; a prior cross-tenant leak was fixed and regression-tested.
- **Prompt-injection posture**: the tool registry is allowlisted and read/write separated.
- **Financial action safety**: no sensitive action executes without an explicit approved state transition.
- **Parameterized SQL** is used throughout core transactional logic.

## Demo-only items

- **Authentication**: `X-Demo-Role` and `X-Merchant-Id` are demo headers, not real authentication. A production deployment must replace this with authenticated session/JWT identity.
- **CORS**: local-only origin defaults.
- **Secrets**: `.env.example` ships placeholders only; production must override the development secret.
- **Rate limiting**: not implemented.

## Known gaps

- Database-level composite tenant-integrity constraints are deferred to the PostgreSQL migration target.
- No formal fuzzing or penetration test has been performed.
- The live LLM path requires its own adversarial runtime verification before production use.
