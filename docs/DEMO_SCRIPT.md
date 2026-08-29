# Demo Script (3–5 minutes)

## Setup
`docker compose up --build`, then open http://localhost:3000. The NovaCart demo dataset seeds automatically on first backend startup.

## 1. Overview
Show cash, settlements, receivables, refund exposure, reconciliation health, anomalies, and forecast. Emphasize that the numbers come from stored synthetic transactions and deterministic calculations.

## 2. Reconciliation
Open an exception and show the evidence and observation/run history. Explain that matching/classification is deterministic, not an LLM opinion.

## 3. Cash Flow
Show the forecast and benchmark. Exponential smoothing beats the naive baseline on the seeded data.

## 4. AI Controller
Ask exactly:

1. **Why is our cash position expected to weaken next week?**
2. **What requires my attention first?**
3. **Can you resolve the most important issue?**

The Controller role selector defaults to ANALYST. Q3 creates an **AWAITING_APPROVAL** action; it does not auto-execute.

## 5. Approvals
Switch to APPROVER and approve the proposed investigation. Show the action reaching SUCCEEDED only after persisted-state verification.

## 6. Audit
Show the propose → decide → execute → verify chain in the audit timeline.

## Closing line
*Every number traces to stored data. Every sensitive action requires a human. Every material step is auditable.*
