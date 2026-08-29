"""
Pure-Python constants with zero framework dependency. Anything imported by
the service layer (which must stay importable without FastAPI installed, so
it can be unit-tested against the real core -- see docs/VERIFICATION_MATRIX.md)
belongs here, not in deps.py, which imports `fastapi`.
"""

DEMO_TODAY_OFFSET_DAYS = 57

from app.core import _bootstrap
from finpilot.core.generator import START as _AWARE_DATASET_START

DATASET_START = _AWARE_DATASET_START.replace(tzinfo=None)
