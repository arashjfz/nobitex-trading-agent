"""Configuration loading for the Nobitex MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MAINNET_BASE_URL = "https://apiv2.nobitex.ir"
TESTNET_BASE_URL = "https://testnetapiv2.nobitex.ir"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - optional at runtime
        return
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    base_url: str
    environment: str
    token: str | None
    public_key: str | None
    private_key: str | None
    auth_mode: str | None
    read_only: bool
    user_agent: str
    timeout: float
    transport: str
    host: str
    port: int
    dry_run: bool = False

    @property
    def is_testnet(self) -> bool:
        return "testnet" in self.base_url


def load_settings() -> Settings:
    _load_dotenv()

    environment = (os.getenv("NOBITEX_ENV") or "mainnet").strip().lower()
    base_url = (os.getenv("NOBITEX_BASE_URL") or "").strip()
    if not base_url:
        base_url = TESTNET_BASE_URL if environment == "testnet" else MAINNET_BASE_URL
    else:
        environment = "testnet" if "testnet" in base_url else "mainnet"

    auth_mode = (os.getenv("NOBITEX_AUTH_MODE") or "").strip().lower() or None
    if auth_mode not in (None, "token", "key"):
        raise ValueError("NOBITEX_AUTH_MODE must be 'token' or 'key'")

    return Settings(
        base_url=base_url.rstrip("/"),
        environment=environment,
        token=(os.getenv("NOBITEX_TOKEN") or "").strip() or None,
        public_key=(os.getenv("NOBITEX_PUBLIC_KEY") or "").strip() or None,
        private_key=(os.getenv("NOBITEX_PRIVATE_KEY") or "").strip() or None,
        auth_mode=auth_mode,
        read_only=_as_bool(os.getenv("NOBITEX_READ_ONLY")),
        user_agent=(os.getenv("NOBITEX_USER_AGENT") or "TraderBot/nobitex-mcp-1.0.0").strip(),
        timeout=float(os.getenv("NOBITEX_TIMEOUT") or "30"),
        transport=(os.getenv("NOBITEX_TRANSPORT") or "stdio").strip().lower(),
        host=(os.getenv("NOBITEX_HOST") or "127.0.0.1").strip(),
        port=int(os.getenv("NOBITEX_PORT") or "8000"),
        dry_run=_as_bool(os.getenv("NOBITEX_DRY_RUN")),
    )
