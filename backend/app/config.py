"""Application settings loaded from environment / .env files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM ---------------------------------------------------------------
    llm_model: str = "anthropic/claude-sonnet-4-5-20250929"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_temperature: float = 0.2

    # --- Nobitex -----------------------------------------------------------
    nobitex_env: str = "mainnet"
    nobitex_base_url: str | None = None
    nobitex_token: str | None = None
    nobitex_public_key: str | None = None
    nobitex_private_key: str | None = None
    nobitex_auth_mode: str | None = None
    nobitex_timeout: float = 30.0
    # Paper trading is on by default so the assistant never sends real orders
    # until the operator explicitly opts in.
    nobitex_dry_run: bool = True
    nobitex_read_only: bool = False

    # --- Agent safety ------------------------------------------------------
    # Withdrawals and credential management are excluded from the toolset
    # unless explicitly enabled.
    allow_withdrawals: bool = False
    agent_max_iterations: int = 60
    agent_max_budget: float | None = None

    # --- Scheduler ---------------------------------------------------------
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Asia/Tehran"
    scheduler_poll_seconds: float = 15.0
    scheduler_run_timeout: float = 900.0
    scheduler_api_url: str = "http://127.0.0.1:8011"
    scheduler_db_path: Path = Field(default_factory=lambda: BACKEND_DIR / "scheduler.db")

    # --- Server ------------------------------------------------------------
    cors_origins: str = "http://localhost:4200,http://127.0.0.1:4200"
    workspace_root: Path = Field(default_factory=lambda: BACKEND_DIR / "workspace")
    mcp_nobitex_path: Path = Field(default_factory=lambda: REPO_ROOT / "mcp" / "nobitex-mcp")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_nobitex_base_url(self) -> str:
        if self.nobitex_base_url:
            return self.nobitex_base_url.rstrip("/")
        if self.nobitex_env.lower() == "testnet":
            return "https://testnetapiv2.nobitex.ir"
        return "https://apiv2.nobitex.ir"

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
