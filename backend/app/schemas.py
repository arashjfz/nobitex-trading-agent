"""Request/response models for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Conversation id; created if omitted")
    message: str = Field(min_length=1, description="User instruction for the agent")
    language: Literal["en", "fa", "ar", "de"] | None = Field(
        default=None, description="Preferred reply language"
    )


class SettingsUpdate(BaseModel):
    """Partial runtime configuration. Omitted fields are left unchanged."""

    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_temperature: float | None = None
    nobitex_env: Literal["mainnet", "testnet"] | None = None
    nobitex_base_url: str | None = None
    nobitex_token: str | None = None
    nobitex_public_key: str | None = None
    nobitex_private_key: str | None = None
    nobitex_auth_mode: Literal["token", "key"] | None = None
    nobitex_dry_run: bool | None = None
    nobitex_read_only: bool | None = None
    allow_withdrawals: bool | None = None
    agent_max_iterations: int | None = None
    scheduler_enabled: bool | None = None
    scheduler_timezone: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    created_at: float


class OrderRequest(BaseModel):
    symbol: str = Field(examples=["BTCUSDT"])
    side: Literal["buy", "sell"]
    amount: str = Field(description="Amount in the base currency, as a decimal string")
    execution: Literal["limit", "market", "stop_limit", "stop_market"] = "limit"
    price: str | None = Field(default=None, description="Required for limit orders")


class CancelRequest(BaseModel):
    order_id: int


class ScheduleCreate(BaseModel):
    name: str | None = Field(default=None, description="Optional label")
    prompt: str = Field(min_length=1, description="Prompt the agent should run")
    cron: str = Field(min_length=1, description="Cron expression, e.g. '0 9 * * *'")
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None
    cron: str | None = None
    enabled: bool | None = None


class CronRequest(BaseModel):
    cron: str = Field(min_length=1)


class AnalysisResponse(BaseModel):
    symbol: str
    resolution: str
    as_of: int
    last_price: float | None
    signal: Literal["BUY", "SELL", "HOLD"]
    score: float
    confidence: float
    indicators: dict
    levels: dict
    reasons: list[str]
    candles: list[dict]


class ScanResponse(BaseModel):
    resolution: str
    opportunities: list[dict]
    errors: list[dict]
