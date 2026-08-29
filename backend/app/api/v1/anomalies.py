from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.deps import get_db_connection, get_merchant_id, get_today_offset
from app.core.roles import Role, get_role, require_can_propose
from app.schemas.finance import AnomalyOut, AnomalyDetailOut
from app.services import finance_service

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("", response_model=list[AnomalyOut])
def list_anomalies(include_resolved: bool = False, conn=Depends(get_db_connection),
                    merchant_id=Depends(get_merchant_id)):
    return finance_service.get_anomalies(conn, merchant_id, include_resolved)


@router.get("/runs")
def get_runs(limit: int = Query(20, le=200), conn=Depends(get_db_connection),
             merchant_id=Depends(get_merchant_id)):
    return finance_service.get_anomaly_runs(conn, merchant_id, limit)


@router.post("/run")
def trigger_run(conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id),
                 today=Depends(get_today_offset), role: Role = Depends(get_role)):
    require_can_propose(role)
    return finance_service.run_anomaly_detection(conn, merchant_id, today)


@router.get("/{anomaly_id}", response_model=AnomalyDetailOut)
def get_anomaly(anomaly_id: str, conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id)):
    result = finance_service.get_anomaly(conn, merchant_id, anomaly_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return result
