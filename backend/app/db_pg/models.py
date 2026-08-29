"""
SQLAlchemy 2.0 declarative models, one per table in finpilot/core/schema.sql.

Design choices carried over deliberately from the tested core (not
reinvented here):
- Money is BigInteger paise, never Float or Numeric -- matches the core's
  own "money must never use floating point" rule, and every financial
  invariant test in finpilot/tests/test_core.py already validates integer-
  paise arithmetic. Introducing Decimal here would be a second, untested
  representation of the same numbers.
- case_key/UNIQUE(merchant_id, case_key) on reconciliation_match and
  financial_anomaly preserves the stable-identity design from round 3-5 of
  core hardening -- this is not optional schema sugar, it's load-bearing.
- approval_request_id is UNIQUE on every side-effect table (alert,
  finance_task, reconciliation_report) -- enforces "one effect per
  approval" at the DB level, exactly as in schema.sql.

Composite tenant-integrity constraints (a payment's settlement must belong
to the same merchant as the payment) are NOT yet added -- SQLite doesn't
support the composite-FK pattern needed to enforce this cleanly, and it
was deliberately deferred to this Postgres layer per the round-5 review.
Marked TODO below at each relevant relationship; implement as composite
foreign keys against (id, merchant_id) once this is actually run against
Postgres and can be tested.
"""
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer,
    String, Text, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchant"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Order(Base):
    __tablename__ = "order_tbl"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (CheckConstraint("status IN ('created','paid','failed')"),)


class Payment(Base):
    __tablename__ = "payment"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("order_tbl.id"))
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    settlement_id: Mapped[str | None] = mapped_column(ForeignKey("settlement.id"))
    __table_args__ = (CheckConstraint("status IN ('captured','failed','refunded','partially_refunded')"),)


class Settlement(Base):
    __tablename__ = "settlement"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    utr: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    expected_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    settled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("status IN ('expected','settled','delayed')"),)


class Refund(Base):
    __tablename__ = "refund"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payment.id"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (CheckConstraint("status IN ('processed','failed')"),)


class LedgerEntry(Base):
    __tablename__ = "ledger_entry"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    value_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Expense(Base):
    __tablename__ = "expense"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (CheckConstraint("status IN ('scheduled','paid')"),)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_run"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, nullable=False)
    settlements_considered: Mapped[int | None] = mapped_column(Integer)
    ledger_entries_considered: Mapped[int | None] = mapped_column(Integer)
    active_cases_before: Mapped[int | None] = mapped_column(Integer)
    active_cases_after: Mapped[int | None] = mapped_column(Integer)
    new_cases: Mapped[int | None] = mapped_column(Integer)
    resolved_cases: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("status IN ('running','completed','failed')"),)


class ReconciliationMatch(Base):
    __tablename__ = "reconciliation_match"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    case_key: Mapped[str] = mapped_column(String, nullable=False)
    settlement_id: Mapped[str | None] = mapped_column(ForeignKey("settlement.id"))
    ledger_entry_id: Mapped[str | None] = mapped_column(ForeignKey("ledger_entry.id"))
    status: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_id: Mapped[str | None] = mapped_column(ForeignKey("reconciliation_run.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("merchant_id", "case_key"),
        CheckConstraint("status IN ('MATCHED','PARTIAL','DUPLICATE','MISSING_SETTLEMENT','UNKNOWN_CREDIT','UNKNOWN_DEBIT','REFUND_MISMATCH','AMOUNT_MISMATCH')"),
    )


class ReconciliationObservation(Base):
    __tablename__ = "reconciliation_observation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_run.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_match.id"), nullable=False, index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False)
    case_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnomalyDetectionRun(Base):
    __tablename__ = "anomaly_detection_run"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, nullable=False)
    days_scanned: Mapped[int | None] = mapped_column(Integer)
    active_before: Mapped[int | None] = mapped_column(Integer)
    active_after: Mapped[int | None] = mapped_column(Integer)
    new_cases: Mapped[int | None] = mapped_column(Integer)
    resolved_cases: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("status IN ('running','completed','failed')"),)


class FinancialAnomaly(Base):
    __tablename__ = "financial_anomaly"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    case_key: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_id: Mapped[str | None] = mapped_column(ForeignKey("anomaly_detection_run.id"))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("merchant_id", "case_key"),
        CheckConstraint("kind IN ('RULE_BASED_ALERT','STATISTICAL_ANOMALY')"),
        CheckConstraint("severity IN ('low','medium','high')"),
    )


class AnomalyObservation(Base):
    __tablename__ = "anomaly_observation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("anomaly_detection_run.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("financial_anomaly.id"), nullable=False, index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False)
    case_key: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApprovalRequest(Base):
    __tablename__ = "approval_request"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    proposal_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String)
    result_json: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("status IN ('PROPOSED','AWAITING_APPROVAL','APPROVED','EXECUTING','SUCCEEDED','VERIFICATION_FAILED','FAILED','REJECTED')"),
    )


class Alert(Base):
    __tablename__ = "alert"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    approval_request_id: Mapped[str] = mapped_column(ForeignKey("approval_request.id"), nullable=False, unique=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FinanceTask(Base):
    __tablename__ = "finance_task"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    approval_request_id: Mapped[str] = mapped_column(ForeignKey("approval_request.id"), nullable=False, unique=True)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("task_type IN ('finance_task','schedule_review','investigation','payout_proposal','refund_recommendation')"),)


class ReconciliationReport(Base):
    __tablename__ = "reconciliation_report"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    approval_request_id: Mapped[str] = mapped_column(ForeignKey("approval_request.id"), nullable=False, unique=True)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.id"), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    inputs_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str | None] = mapped_column(String)
    approval_state: Mapped[str | None] = mapped_column(String)
    result_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
