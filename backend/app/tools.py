"""Custom agent tool that runs the deterministic technical analysis."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from openhands.sdk import (
    Action,
    ImageContent,
    Observation,
    TextContent,
    ToolDefinition,
)
from openhands.sdk.tool import ToolExecutor
from pydantic import Field

from . import nobitex


class AnalyzeMarketAction(Action):
    symbol: str = Field(description="Market symbol, e.g. BTCUSDT, ETHUSDT or BTCIRT")
    resolution: str = Field(
        default="60",
        description="Candle timeframe: minutes (1,5,15,30,60,240) or days (D)",
    )
    countback: int = Field(
        default=200, ge=50, le=500, description="Number of candles to analyse"
    )


class AnalyzeMarketObservation(Observation):
    symbol: str = ""
    signal: str = ""
    score: float = 0.0
    confidence: float = 0.0
    last_price: float | None = None
    summary: str = ""
    analysis: dict[str, Any] = Field(default_factory=dict)

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        payload = {k: v for k, v in self.analysis.items() if k != "candles"}
        return [
            TextContent(
                text=(
                    f"{self.summary}\n\n"
                    "Raw analysis (JSON):\n"
                    f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
                )
            )
        ]


def _format_summary(result: dict[str, Any]) -> str:
    indicators = result["indicators"]
    levels = result["levels"]
    price = result["last_price"]
    lines = [
        f"{result['symbol']} @ {result['resolution']}m — {result['signal']} "
        f"(score {result['score']:+.2f}, confidence {result['confidence']:.0%})",
        f"Last price: {price}",
        "Indicators: "
        f"RSI14={indicators.get('rsi14')}, "
        f"MACD hist={indicators.get('macd_histogram')}, "
        f"EMA20={indicators.get('ema20')}, EMA50={indicators.get('ema50')}, "
        f"BB %B={indicators.get('bollinger_percent_b')}, "
        f"ATR14={indicators.get('atr14')}",
        "Levels: "
        f"entry={levels.get('entry')}, stop={levels.get('stop_loss')}, "
        f"target={levels.get('take_profit')}, "
        f"support={levels.get('support')}, resistance={levels.get('resistance')}",
        "Reasons:",
    ]
    lines.extend(f"- {reason}" for reason in result["reasons"])
    return "\n".join(lines)


class AnalyzeMarketExecutor(ToolExecutor[AnalyzeMarketAction, AnalyzeMarketObservation]):
    def __call__(
        self, action: AnalyzeMarketAction, conversation: Any = None
    ) -> AnalyzeMarketObservation:
        result = nobitex.analyze_symbol(
            action.symbol, resolution=action.resolution, countback=action.countback
        )
        return AnalyzeMarketObservation(
            symbol=result["symbol"],
            signal=result["signal"],
            score=result["score"],
            confidence=result["confidence"],
            last_price=result["last_price"],
            summary=_format_summary(result),
            analysis=result,
        )


_DESCRIPTION = """\
Run deterministic technical analysis on a Nobitex market.

Fetches OHLC candles from Nobitex, computes EMA20/EMA50, RSI14, MACD,
Bollinger Bands, ATR14 and stochastic %K, then returns a scored BUY/SELL/HOLD
signal with entry, stop-loss, take-profit, support and resistance levels plus
the reasons behind the score. Use this before recommending a trade.
"""


class AnalyzeMarketTool(ToolDefinition[AnalyzeMarketAction, AnalyzeMarketObservation]):
    """Technical-analysis tool exposed to the trading agent."""

    @classmethod
    def create(cls, conv_state: Any = None, **params: Any) -> Sequence[ToolDefinition]:
        return [
            cls(
                description=_DESCRIPTION,
                action_type=AnalyzeMarketAction,
                observation_type=AnalyzeMarketObservation,
                executor=AnalyzeMarketExecutor(),
            )
        ]
