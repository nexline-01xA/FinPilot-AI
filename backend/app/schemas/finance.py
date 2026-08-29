from pydantic import BaseModel
from app.schemas.common import Money


class OverviewResponse(BaseModel):
    current_cash: Money
    total_settled: Money
    outstanding_receivables: Money
    total_refund_exposure: Money
    reconciliation_health_pct: float | None
    reconciliation_exceptions: int
    open_anomalies: int
    forecast_7d_cash: Money
    possible_shortfall_dates: list[str]


class ReconciliationCaseOut(BaseModel):
    id: str
    merchant_id: str
    case_key: str
    settlement_id: str | None
    ledger_entry_id: str | None
    status: str
    confidence: float
    evidence: dict
    active: bool
    last_run_id: str | None = None
    created_at: str
    updated_at: str


class ReconciliationObservationOut(BaseModel):
    run_id: str
    status: str
    confidence: float
    evidence: dict
    active: bool
    observed_at: str


class ReconciliationCaseDetailOut(ReconciliationCaseOut):
    observation_history: list[ReconciliationObservationOut]


class ReconciliationReportResponse(BaseModel):
    total_matches: int
    matched: int
    exceptions: int
    health_pct: float | None
    by_status: dict[str, int]
    cases: list[ReconciliationCaseOut]


class AnomalyOut(BaseModel):
    id: str
    merchant_id: str
    case_key: str
    kind: str
    category: str
    severity: str
    evidence: dict
    active: bool
    last_run_id: str | None = None
    detected_at: str
    updated_at: str


class AnomalyObservationOut(BaseModel):
    run_id: str
    severity: str
    evidence: dict
    active: bool
    observed_at: str


class AnomalyDetailOut(AnomalyOut):
    observation_history: list[AnomalyObservationOut]


class ForecastPointOut(BaseModel):
    day: str
    expected_cash_paise: int
    lower_paise: int
    upper_paise: int


class ForecastBenchmark(BaseModel):
    naive_baseline_mae_paise: float | None
    model_mae_paise: float | None
    backtest_points: int
    model_beats_naive: bool


class ForecastResponse(BaseModel):
    horizon_days: int
    model: str
    benchmark: ForecastBenchmark
    points: list[ForecastPointOut]
    upcoming_obligations: list[dict]
    possible_shortfall_dates: list[str]


class ScenarioRequest(BaseModel):
    type: str
    settlement_id: str | None = None
    delay_days: int | None = None
    pct: float | None = None


class TransactionOut(BaseModel):
    id: str
    merchant_id: str
    order_id: str | None
    amount_paise: int
    fee_paise: int
    tax_paise: int
    status: str
    method: str
    created_at: str
    settlement_id: str | None


class SettlementOut(BaseModel):
    id: str
    merchant_id: str
    amount_paise: int
    expected_amount_paise: int
    status: str
    utr: str | None
    expected_date: str
    settled_date: str | None
