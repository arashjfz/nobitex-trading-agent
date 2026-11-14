"""Unit tests for the technical-analysis engine."""

from __future__ import annotations

import math

import pytest

from app import technical
from app.nobitex import parse_udf, split_symbol


def make_candles(n: int = 120, drift: float = 0.8) -> list[dict[str, float]]:
    price = 100.0
    candles: list[dict[str, float]] = []
    for i in range(n):
        price += drift + math.sin(i / 4.0) * 0.3
        candles.append(
            {
                "t": 1_700_000_000 + i * 3600,
                "o": price - 0.2,
                "h": price + 1.0,
                "l": price - 1.0,
                "c": price,
                "v": 10.0 + (i % 5),
            }
        )
    return candles


def test_sma_and_ema_alignment() -> None:
    values = [float(i) for i in range(1, 51)]
    sma = technical.sma_series(values, 5)
    ema = technical.ema_series(values, 5)
    assert sma[:4] == [None] * 4
    assert sma[4] == pytest.approx(3.0)
    assert ema[4] == pytest.approx(3.0)
    assert ema[-1] > sma[-1]  # EMA reacts faster to a rising series


def test_rsi_bounds_and_direction() -> None:
    rising = [float(i) for i in range(1, 60)]
    falling = list(reversed(rising))
    rsi_up = technical.rsi_series(rising, 14)[-1]
    rsi_down = technical.rsi_series(falling, 14)[-1]
    assert rsi_up == pytest.approx(100.0)
    assert rsi_down == pytest.approx(0.0)


def test_macd_and_bollinger_shapes() -> None:
    values = [100 + math.sin(i / 3.0) * 5 for i in range(80)]
    line, signal, hist = technical.macd_series(values)
    assert len(line) == len(signal) == len(hist) == len(values)
    mid, upper, lower, pct_b = technical.bollinger_series(values, 20)
    for i in range(19, len(values)):
        assert lower[i] <= mid[i] <= upper[i]
        assert 0.0 <= pct_b[i] <= 1.0


def test_atr_positive() -> None:
    candles = make_candles()
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    closes = [c["c"] for c in candles]
    atr = technical.atr_series(highs, lows, closes, 14)
    assert atr[-1] is not None and atr[-1] > 0


def test_analyze_uptrend_is_not_sell() -> None:
    result = technical.analyze(make_candles(drift=0.8), "BTCUSDT", "60")
    assert result["symbol"] == "BTCUSDT"
    assert result["signal"] in {"BUY", "HOLD"}
    assert result["score"] > 0
    assert result["levels"]["stop_loss"] < result["last_price"] < result["levels"]["take_profit"]
    assert result["confidence"] <= 0.95
    assert len(result["candles"]) == 120


def test_analyze_downtrend_is_not_buy() -> None:
    result = technical.analyze(make_candles(drift=-0.8), "ETHUSDT", "60")
    assert result["signal"] in {"SELL", "HOLD"}
    assert result["score"] < 0


def test_analyze_requires_enough_candles() -> None:
    with pytest.raises(ValueError):
        technical.analyze(make_candles(n=10), "BTCUSDT", "60")


def test_rank_analyses_puts_buys_first() -> None:
    ranked = technical.rank_analyses(
        [
            {"symbol": "A", "signal": "HOLD", "score": 0.0},
            {"symbol": "B", "signal": "BUY", "score": 0.4},
            {"symbol": "C", "signal": "BUY", "score": 0.8},
        ]
    )
    assert [item["symbol"] for item in ranked] == ["C", "B", "A"]


@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("BTCUSDT", ("btc", "usdt")),
        ("ethirt", ("eth", "rls")),
        ("BTC-IRT", ("btc", "rls")),
        ("SOL/USDT", ("sol", "usdt")),
    ],
)
def test_split_symbol(symbol: str, expected: tuple[str, str]) -> None:
    assert split_symbol(symbol) == expected


def test_parse_udf() -> None:
    payload = {
        "s": "ok",
        "t": [1, 2, 3],
        "o": [10, 11, 12],
        "h": [11, 12, 13],
        "l": [9, 10, 11],
        "c": [10.5, 11.5, 12.5],
        "v": [100, 200, 300],
    }
    candles = parse_udf(payload)
    assert len(candles) == 3
    assert candles[0] == {"t": 1, "o": 10.0, "h": 11.0, "l": 9.0, "c": 10.5, "v": 100.0}
