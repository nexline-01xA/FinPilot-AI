from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from app.core.deps import get_db_connection, get_merchant_id
from app.core.roles import Role, get_role, require_can_propose, require_can_decide
from app.services import approval_service
from finpilot.core.approvals import ApprovalError

router = APIRouter(tags=["approvals"])


class ProposeActionRequest(BaseModel):
    action_type: str
    proposal: dict


class RetryRequest(BaseModel):
    retry_by: str
    reason: str


class DecideRequest(BaseModel):
    decided_by: str


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/actions")
def list_actions(status: str | None = None, conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id)):
    return approval_service.list_approvals(conn, merchant_id, status)


@router.post("/actions")
def propose_action(body: ProposeActionRequest, conn=Depends(get_db_connection),
                    merchant_id=Depends(get_merchant_id), role: Role = Depends(get_role)):
    require_can_propose(role)
    return _handle(approval_service.propose, conn, merchant_id, body.action_type, body.proposal)


@router.get("/approvals")
def list_approvals_alias(status: str | None = None, conn=Depends(get_db_connection),
                          merchant_id=Depends(get_merchant_id)):
    return approval_service.list_approvals(conn, merchant_id, status)


@router.get("/approvals/{request_id}")
def get_approval(request_id: str, conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id)):
    result = approval_service.get_approval(conn, merchant_id, request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return result


@router.post("/approvals/{request_id}/approve")
def approve(request_id: str, body: DecideRequest, conn=Depends(get_db_connection),
            merchant_id=Depends(get_merchant_id), role: Role = Depends(get_role)):
    require_can_decide(role)
    result = _handle(approval_service.decide, conn, merchant_id, request_id, True, body.decided_by)
    exec_result = _handle(approval_service.execute, conn, merchant_id, request_id)
    return exec_result


@router.post("/approvals/{request_id}/reject")
def reject(request_id: str, body: DecideRequest, conn=Depends(get_db_connection),
           merchant_id=Depends(get_merchant_id), role: Role = Depends(get_role)):
    require_can_decide(role)
    return _handle(approval_service.decide, conn, merchant_id, request_id, False, body.decided_by)


@router.post("/approvals/{request_id}/retry")
def retry(request_id: str, body: RetryRequest, conn=Depends(get_db_connection),
          merchant_id=Depends(get_merchant_id), role: Role = Depends(get_role)):
    require_can_decide(role)
    retried = _handle(approval_service.retry, conn, merchant_id, request_id, body.retry_by, body.reason)
    return _handle(approval_service.execute, conn, merchant_id, request_id)
