from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.deps import get_db_connection, get_merchant_id, get_today_offset
from app.core.roles import Role, get_role, require_can_propose
from app.services import controller_service

router = APIRouter(prefix="/controller", tags=["controller"])


class ControllerQuery(BaseModel):
    question: str


@router.post("/query")
def query(body: ControllerQuery, conn=Depends(get_db_connection), merchant_id=Depends(get_merchant_id),
          today=Depends(get_today_offset), role: Role = Depends(get_role)):
    route = controller_service.classify_route(body.question)
    if route in controller_service.ACTION_PRODUCING_ROUTES:
        require_can_propose(role)
    return controller_service.ask(conn, merchant_id, today, body.question)
