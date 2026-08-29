from fastapi import APIRouter, Depends, Query
from app.core.deps import get_db_connection, get_merchant_id
from app.schemas.finance import TransactionOut, SettlementOut
from app.services import finance_service

router = APIRouter(tags=["transactions"])


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(limit: int = Query(100, le=500), status: str | None = None,
                       conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id)):
    return finance_service.list_transactions(conn, merchant_id, limit, status)


@router.get("/settlements", response_model=list[SettlementOut])
def list_settlements(limit: int = Query(100, le=500), status: str | None = None,
                      conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id)):
    return finance_service.list_settlements(conn, merchant_id, limit, status)
