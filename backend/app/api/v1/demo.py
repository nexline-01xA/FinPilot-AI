from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.core.roles import Role, get_role, require_admin

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/reset")
def reset(role: Role = Depends(get_role)):
    require_admin(role)
    from app.services import demo_service
    return demo_service.reset_demo(settings.sqlite_path)
