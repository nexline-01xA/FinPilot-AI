from enum import Enum
from fastapi import Header, HTTPException


class Role(str, Enum):
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    APPROVER = "APPROVER"
    ADMIN = "ADMIN"


_CAN_PROPOSE = {Role.ANALYST, Role.APPROVER, Role.ADMIN}
_CAN_DECIDE = {Role.APPROVER, Role.ADMIN}
_CAN_ADMIN = {Role.ADMIN}


def get_role(x_demo_role: str = Header(default="VIEWER")) -> Role:
    try:
        return Role(x_demo_role.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown role: {x_demo_role}")


def require_can_propose(role: Role) -> None:
    if role not in _CAN_PROPOSE:
        raise HTTPException(status_code=403, detail=f"Role {role} cannot propose actions (requires ANALYST, APPROVER, or ADMIN)")


def require_can_decide(role: Role) -> None:
    if role not in _CAN_DECIDE:
        raise HTTPException(status_code=403, detail=f"Role {role} cannot approve/reject actions (requires APPROVER or ADMIN)")


def require_admin(role: Role) -> None:
    if role not in _CAN_ADMIN:
        raise HTTPException(status_code=403, detail=f"Role {role} cannot perform this action (requires ADMIN)")
