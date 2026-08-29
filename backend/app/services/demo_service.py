from app.core import _bootstrap  # noqa: F401 -- must run before any `finpilot` import below
"""Demo data lifecycle: (re)seed the synthetic NovaCart dataset and run the engines once."""
from finpilot.core import db as core_db, generator, reconciliation, anomaly
from app.core.constants import DEMO_TODAY_OFFSET_DAYS, DATASET_START


def reset_demo(sqlite_path: str, seed: int = 42) -> dict:
    conn = core_db.init_db(sqlite_path, fresh=True)
    try:
        ground_truth = generator.generate(conn, seed=seed)
        mid = ground_truth["merchant_id"]
        reconciliation.reconcile(conn, mid)
        anomaly.detect(conn, mid, DATASET_START, DEMO_TODAY_OFFSET_DAYS)
        return {"merchant_id": mid, "seed": seed, "days": ground_truth["days"],
                "scenarios_seeded": list(ground_truth["scenarios"].keys())}
    finally:
        conn.close()
