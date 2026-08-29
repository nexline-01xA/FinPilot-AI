import os
import sys
import json
import unittest
from datetime import datetime, timezone

# Repo root (not finpilot/) on sys.path, and package-qualified imports below --
# same fix, same reason, as run_evaluation.py: this only worked before when
# invoked with cwd=finpilot/; `python -m finpilot.tests.test_core` from the
# repo root would otherwise fail the same way. Packaging-only change, zero
# test logic touched -- rerun to confirm: still 84/84. See docs/VERIFICATION_MATRIX.md.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from finpilot.core import db, generator, reconciliation, forecasting, anomaly, approvals, audit
from finpilot.core.agent_tools import FinanceTools
from finpilot.core.agent import DeterministicDemoAgent

DB_PATH = "/tmp/finpilot_test.db"


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(DB_PATH, fresh=True)
        self.ground_truth = generator.generate(self.conn, seed=42)
        self.mid = self.ground_truth["merchant_id"]
        self.start = datetime.fromisoformat(self.ground_truth["start_date"].replace("Z", "+00:00")).replace(tzinfo=None)
        self.days = self.ground_truth["days"]

    def tearDown(self):
        self.conn.close()


class TestRunHistoryReconstruction(BaseCase):
    def test_run1_case_state_is_reconstructable_after_run2_changes_it(self):
        reconciliation.reconcile(self.conn, self.mid)
        run1 = self.conn.execute(
            "SELECT id FROM reconciliation_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()
        case = self.conn.execute(
            "SELECT * FROM reconciliation_match WHERE merchant_id=? AND status='MATCHED' LIMIT 1",
            (self.mid,)
        ).fetchone()
        run1_status = case["status"]
        self.conn.execute(
            "UPDATE settlement SET amount_paise = amount_paise - 500000 WHERE id=?",
            (case["settlement_id"],)
        )
        self.conn.commit()
        reconciliation.reconcile(self.conn, self.mid)
        current = self.conn.execute(
            "SELECT * FROM reconciliation_match WHERE id=?", (case["id"],)
        ).fetchone()
        self.assertEqual(current["id"], case["id"])
        self.assertNotEqual(current["status"], run1_status)
        obs_run1 = self.conn.execute(
            "SELECT status FROM reconciliation_observation WHERE run_id=? AND case_id=?",
            (run1["id"], case["id"])
        ).fetchone()
        self.assertIsNotNone(obs_run1, "RUN1's observation of this case no longer exists")
        self.assertEqual(obs_run1["status"], run1_status)

    def test_run2_does_not_overwrite_run1_observation(self):
        reconciliation.reconcile(self.conn, self.mid)
        obs_count_after_run1 = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_observation WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        reconciliation.reconcile(self.conn, self.mid)
        obs_count_after_run2 = self.conn.execute(
            "SELECT COUNT(*) c FROM reconciliation_observation WHERE merchant_id=?", (self.mid,)
        ).fetchone()["c"]
        self.assertEqual(obs_count_after_run2, obs_count_after_run1 * 2)

    def test_resolution_is_attributed_to_the_resolving_run(self):
        reconciliation.reconcile(self.conn, self.mid)
        run1_id = self.conn.execute(
            "SELECT id FROM reconciliation_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()["id"]
        row = self.conn.execute(
            "SELECT id, ledger_entry_id FROM reconciliation_match WHERE merchant_id=? "
            "AND status='UNKNOWN_CREDIT' AND active=1 LIMIT 1", (self.mid,)
        ).fetchone()
        self.conn.execute("UPDATE ledger_entry SET reference='explained' WHERE id=?",
                          (row["ledger_entry_id"],))
        self.conn.commit()
        reconciliation.reconcile(self.conn, self.mid)
        run2_id = self.conn.execute(
            "SELECT id FROM reconciliation_run WHERE merchant_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (self.mid,)
        ).fetchone()["id"]
        current = self.conn.execute(
            "SELECT last_run_id, active FROM reconciliation_match WHERE id=?", (row["id"],)
        ).fetchone()
        self.assertEqual(current["active"], 0)
        self.assertEqual(current["last_run_id"], run2_id,
                          "resolved case still points at the run BEFORE the one that resolved it")
        resolution_obs = self.conn.execute(
            "SELECT * FROM reconciliation_observation WHERE case_id=? AND run_id=? AND active=0",
            (row["id"], run2_id)
        ).fetchone()
        self.assertIsNotNone(resolution_obs, "no observation records the resolving run")


class TestRefundIncidentIdentityAcrossClippedWindow(BaseCase):
    def test_incident_id_stable_when_window_starts_inside_it(self):
        anomaly.detect(self.conn, self.mid, self.start, self.days)
        run1 = self.conn.execute(
            "SELECT id, evidence_json FROM financial_anomaly WHERE merchant_id=? "
            "AND category='refund_rate_spike' AND active=1", (self.mid,)
        ).fetchall()
        self.assertTrue(run1)
        id1 = run1[0]["id"]
        span1 = json.loads(run1[0]["evidence_json"])["date_span"]
        from datetime import datetime as dt, timedelta
        clipped_start = dt.strptime(span1[0], "%Y-%m-%d") + timedelta(days=4)
        end_of_data = self.start + timedelta(days=self.days)
        remaining_days = (end_of_data - clipped_start).days
        anomaly.detect(self.conn, self.mid, clipped_start, remaining_days)
        run2 = self.conn.execute(
            "SELECT id, evidence_json FROM financial_anomaly WHERE merchant_id=? "
            "AND category='refund_rate_spike' AND active=1", (self.mid,)
        ).fetchall()
        self.assertTrue(run2)
        id2 = run2[0]["id"]
        span2 = json.loads(run2[0]["evidence_json"])["date_span"]
        self.assertEqual(id1, id2, "the same real-world incident got a new id when the window clipped it")
        self.assertEqual(span2[0], span1[0], "the incident's known start date regressed")
