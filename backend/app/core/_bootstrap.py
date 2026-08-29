"""
Single source of truth for making `finpilot` importable. Imported first
(as a side-effecting import) by both config.py (needs it for settings) and
constants.py (needs it for DATASET_START) -- so the path fix happens
exactly once regardless of which module an external caller imports first.
A prior version relied on config.py happening to be imported before
constants.py, which worked by accident in manual testing but wasn't
guaranteed for e.g. a test that imports app.services.finance_service
directly. Found by actually testing that path; see docs/VERIFICATION_MATRIX.md.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]  # app/core/_bootstrap.py -> repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
