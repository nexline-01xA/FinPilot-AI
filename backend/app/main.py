"""
FinPilot AI backend entrypoint.

IMPORTANT (read before assuming this runs): this file has NOT been executed
in the environment it was originally written in -- FastAPI/uvicorn are not
installed there (no PyPI access). It is written correctly to the
framework's documented API surface and is syntax-checked. Several bugs in
earlier versions of this app (including the startup bootstrap this file
now wires in) were found by external runtime testing in an environment
where FastAPI genuinely was installed -- see docs/VERIFICATION_MATRIX.md.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.bootstrap_demo import ensure_demo_bootstrap
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.demo_mode:
        ensure_demo_bootstrap(settings.sqlite_path)
    yield


app = FastAPI(
    title=settings.app_name,
    description="Agentic finance controller for digital businesses -- deterministic core, "
                 "human-approved actions, full audit trail.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {"service": settings.app_name, "status": "ok", "docs": "/docs"}
