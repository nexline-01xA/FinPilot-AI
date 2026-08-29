from fastapi import APIRouter, Depends
from app.core.deps import get_db_connection
from app.core.bootstrap_demo import demo_state_is_usable
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(conn=Depends(get_db_connection)):
    conn.execute("SELECT 1")
    usable = demo_state_is_usable(settings.sqlite_path)
    return {"status": "healthy" if usable else "degraded",
            "database_reachable": True,
            "demo_state_usable": usable}
