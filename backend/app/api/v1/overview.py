from fastapi import APIRouter, Depends
from app.core.deps import get_db_connection, get_merchant_id, get_today_offset
from app.schemas.finance import OverviewResponse
from app.schemas.common import Money
from app.services import finance_service

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
def overview(conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id),
             today=Depends(get_today_offset)):
    d = finance_service.get_overview(conn, merchant_id, today)
    return OverviewResponse(
        current_cash=Money.of(d["current_cash_paise"]),
        total_settled=Money.of(d["total_settled_paise"]),
        outstanding_receivables=Money.of(d["outstanding_receivables_paise"]),
        total_refund_exposure=Money.of(d["total_refund_exposure_paise"]),
        reconciliation_health_pct=d["reconciliation_health_pct"],
        reconciliation_exceptions=d["reconciliation_exceptions"],
        open_anomalies=d["open_anomalies"],
        forecast_7d_cash=Money.of(d["forecast_7d_cash_paise"]),
        possible_shortfall_dates=d["possible_shortfall_dates"],
    )
