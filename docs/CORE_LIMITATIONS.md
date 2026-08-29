# FinPilot Core — Hardening History

The deterministic SQLite core went through five adversarial hardening rounds. The fixes included:

- reconciliation/anomaly idempotency
- real sandbox side effects instead of cosmetic SUCCEEDED states
- complete approval/audit transitions
- critical cross-tenant read/write isolation
- failure-safe EXECUTING → FAILED behavior
- stable reconciliation and anomaly identity across reruns and moving windows
- atomic business-state + audit persistence
- controlled retry behavior with duplicate-effect protection
- immutable per-run observation history
- rollback of all partial derived state on failed runs
- correct run finalization when audit itself fails

Final verified core baseline before product integration: **84/84 tests**, **62 reconciliation cases**, **93.5% reconciliation health**, **6/6 injected scenarios detected**, and exponential-smoothing MAE below the naive baseline.

Core hardening stopped deliberately after that baseline so engineering effort could move to the actual FastAPI/Next.js product and real runtime integration.
