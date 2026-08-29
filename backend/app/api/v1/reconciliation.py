from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.deps import get_db_connection, get_merchant_id
from app.core.roles import Role, get_role, require_can_propose
from app.schemas.finance import ReconciliationReportResponse, ReconciliationCaseDetailOut
from app.services import finance_service

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.get("", response_model=ReconciliationReportResponse)
def get_report(include_resolved: bool = False, conn=Depends(get_db_connection),
               merchant_id=Depends(get_merchant_id)):
    return finance_service.get_reconciliation_report(conn, merchant_id, include_resolved)


@router.get("/runs")
def get_runs(limit: int = Query(20, le=200), conn=Depends(get_db_connection),
             merchant_id=Depends(get_merchant_id)):
    return finance_service.get_reconciliation_runs(conn, merchant_id, limit)


@router.post("/run")
def trigger_run(conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id),
                 role: Role = Depends(get_role)):
    require_can_propose(role)
    return finance_service.run_reconciliation(conn, merchant_id)


@router.get("/{case_id}", response_model=ReconciliationCaseDetailOut)
def get_case(case_id: str, conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id)):
    case = finance_service.get_reconciliation_case(conn, merchant_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Reconciliation case not found")
    return case
