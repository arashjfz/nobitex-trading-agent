"""Request/response models for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Conversation id; created if omitted")
    message: str = Field(min_length=1, description="User instruction for the agent")


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
