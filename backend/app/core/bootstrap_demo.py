"""
Idempotent demo-mode startup bootstrap.

Found by external runtime testing (not by this sandbox, which can't run
FastAPI): a fresh SQLite file has no schema and no seeded merchant, so every
route that queries `settlement`/`financial_anomaly`/etc. raised
`sqlite3.OperationalError: no such table` -> unhandled -> HTTP 500, while
`/health`'s bare `SELECT 1` passed regardless, since it never touches an
actual table. That's a fresh-deploy dead end: Docker starts, health checks
pass, and the homepage still 500s. Fixed here with a startup hook that
checks for usable state and seeds it ONLY if missing -- never resets
existing data on restart. See docs/VERIFICATION_MATRIX.md.

Takes sqlite_path as a parameter rather than importing app.core.config
directly -- keeps this testable without pydantic_settings installed, same
reasoning as app/core/constants.py. The FastAPI lifespan hook in main.py is
the only caller that needs settings at all; it passes settings.sqlite_path in.
"""
import os
import sqlite3


def demo_state_is_usable(sqlite_path: str) -> bool:
    """True only if the schema exists AND at least one merchant is seeded --
    matches what /health also checks, so both agree on what "healthy" means."""
    if not os.path.exists(sqlite_path):
        return False
    conn = sqlite3.connect(sqlite_path)
    try:
        has_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='merchant'"
        ).fetchone()
        if not has_table:
            return False
        count = conn.execute("SELECT COUNT(*) FROM merchant").fetchone()[0]
        return count > 0
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def ensure_demo_bootstrap(sqlite_path: str) -> dict:
    """
    Idempotent: does nothing if usable demo state already exists (so a
    restart never silently resets whatever the demo/reviewer has done so
    far). Only seeds when the DB is genuinely missing or empty.
    """
    os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)

    if demo_state_is_usable(sqlite_path):
        return {"bootstrapped": False, "reason": "usable demo state already present"}

    from app.services import demo_service
    result = demo_service.reset_demo(sqlite_path)
    return {"bootstrapped": True, **result}
