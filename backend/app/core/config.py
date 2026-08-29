"""
Application configuration + import bootstrap for the frozen `finpilot` core.

The core lives as a sibling directory (`../finpilot`) rather than an
installed package -- there's no package registry available in the
environment this was built in. In Docker, PYTHONPATH is set explicitly (see
the root Dockerfile) so `import finpilot` resolves without this fallback.
This fallback exists purely for `uvicorn app.main:app` run directly from
`backend/` in local dev without Docker.
"""
from pydantic_settings import BaseSettings
from app.core import _bootstrap
from app.core._bootstrap import REPO_ROOT as _REPO_ROOT


class Settings(BaseSettings):
    app_name: str = "FinPilot AI"
    demo_mode: bool = True
    ai_provider: str = "demo"
    ai_model: str = "claude-sonnet-4-6"
    anthropic_api_key: str | None = None
    sqlite_path: str = str(_REPO_ROOT / "data" / "finpilot.db")
    persistence_backend: str = "sqlite"
    database_url: str | None = None
    secret_key: str = "dev-only-not-for-production"
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
