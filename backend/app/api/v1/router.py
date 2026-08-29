from fastapi import APIRouter
from app.api.v1 import health, overview, transactions, reconciliation, anomalies, cashflow, controller, approvals, audit, demo

api_router = APIRouter()
for module in (health, overview, transactions, reconciliation, anomalies, cashflow, controller, approvals, audit, demo):
    api_router.include_router(module.router)
