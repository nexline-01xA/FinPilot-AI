from fastapi import APIRouter, Depends, Query
from app.core.deps import get_db_connection, get_merchant_id
from app.services import audit_service

router = APIRouter(tags=["audit"])


@router.get("/audit")
def list_audit(operation: str | None = None, actor: str | None = None, limit: int = Query(200, le=1000),
                conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id)):
    return audit_service.list_audit_events(conn, merchant_id, operation, actor, limit)
