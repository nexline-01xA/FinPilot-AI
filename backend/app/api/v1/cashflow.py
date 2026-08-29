from fastapi import APIRouter, Depends
from app.core.deps import get_db_connection, get_merchant_id, get_today_offset
from app.schemas.finance import ScenarioRequest, ForecastResponse
from app.services import finance_service

router = APIRouter(tags=["cash-flow"])


@router.get("/cash-flow", response_model=ForecastResponse)
@router.get("/forecasts", response_model=ForecastResponse)
def forecast(horizon_days: int = 30, conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id),
             today=Depends(get_today_offset)):
    # response_model=ForecastResponse means FastAPI now validates and filters the
    # service layer's dict against the schema on every response, so contract drift
    # between this route and app/schemas/finance.py fails loudly instead of silently
    # shipping a mismatched shape. See docs/VERIFICATION_MATRIX.md.
    return finance_service.get_forecast(conn, merchant_id, today, horizon_days)


@router.post("/forecasts/simulate")
def simulate(scenario: ScenarioRequest, conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id),
             today=Depends(get_today_offset)):
    return finance_service.simulate_scenario(conn, merchant_id, today, scenario.model_dump(exclude_none=True))
