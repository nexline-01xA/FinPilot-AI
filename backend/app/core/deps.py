"""
FastAPI dependency providers. Every request-scoped DB connection is opened
and closed here -- nothing in services/ or api/ manages connections directly.
"""
from datetime import datetime, timedelta
from fastapi import Header

from app.core.config import settings
from app.core.constants import DEMO_TODAY_OFFSET_DAYS
from finpilot.core import db as core_db
from finpilot.core.generator import MERCHANT_ID as DEFAULT_MERCHANT_ID, START as DATASET_START
from finpilot.core.agent_tools import FinanceTools


def get_db_connection():
    conn = core_db.connect(settings.sqlite_path)
    try:
        yield conn
    finally:
        conn.close()


def get_merchant_id(x_merchant_id: str | None = Header(default=None)) -> str:
    return x_merchant_id or DEFAULT_MERCHANT_ID


def get_today_offset() -> int:
    return DEMO_TODAY_OFFSET_DAYS


def get_finance_tools(conn=None, merchant_id: str = None) -> FinanceTools:
    return FinanceTools(conn, merchant_id, DATASET_START, DEMO_TODAY_OFFSET_DAYS)
