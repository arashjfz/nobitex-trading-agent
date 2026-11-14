"""Deterministic technical-analysis engine.

The functions here are pure: they take price series and return indicator
values. ``analyze`` turns a candle series into a scored BUY/SELL/HOLD signal
with entry, stop-loss and take-profit levels derived from ATR.
"""

from __future__ import annotations

from math import sqrt
from typing import Any, Sequence

Candle = dict[str, float]


def _round(value: float | None, digits: int = 8) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def sma_series(values: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    window_sum = sum(values[:period])
    out[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out[i] = window_sum / period
    return out


def ema_series(values: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2.0 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi_series(values: Sequence[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0
        rs = gain / loss
        return 100.0 - 100.0 / (1.0 + rs)

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i + 1] = _rsi(avg_gain, avg_loss)
    return out


def macd_series(
    values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast_ema = ema_series(values, fast)
    slow_ema = ema_series(values, slow)
    line: list[float | None] = [None] * len(values)
    for i in range(len(values)):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            line[i] = fast_ema[i] - slow_ema[i]

    indices = [i for i, value in enumerate(line) if value is not None]
    signal_line: list[float | None] = [None] * len(values)
    if len(indices) >= signal:
        compact = [line[i] for i in indices]  # type: ignore[misc]
        compact_signal = ema_series(compact, signal)
        for j, i in enumerate(indices):
            signal_line[i] = compact_signal[j]

    histogram: list[float | None] = [None] * len(values)
    for i in range(len(values)):
        if line[i] is not None and signal_line[i] is not None:
            histogram[i] = line[i] - signal_line[i]
    return line, signal_line, histogram


def bollinger_series(
    values: Sequence[float], period: int = 20, k: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None], list[float | None]]:
    mid = sma_series(values, period)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)
    percent_b: list[float | None] = [None] * len(values)
    for i in range(len(values)):
        if mid[i] is None:
            continue
        window = values[i - period + 1 : i + 1]
        mean = mid[i]
        variance = sum((x - mean) ** 2 for x in window) / period
        sd = sqrt(variance)
        upper[i] = mean + k * sd
        lower[i] = mean - k * sd
        band = upper[i] - lower[i]
        percent_b[i] = (values[i] - lower[i]) / band if band else 0.5
    return mid, upper, lower, percent_b


def atr_series(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14
) -> list[float | None]:
    if not closes:
        return []
    true_range: list[float] = []
    for i in range(len(closes)):
        if i == 0:
            true_range.append(highs[i] - lows[i])
        else:
            true_range.append(
                max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
            )
    out: list[float | None] = [None] * len(closes)
    if len(closes) < period:
        return out
    prev = sum(true_range[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(closes)):
        prev = (prev * (period - 1) + true_range[i]) / period
        out[i] = prev
    return out


def stochastic_series(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14
) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        highest = max(highs[i - period + 1 : i + 1])
        lowest = min(lows[i - period + 1 : i + 1])
        out[i] = 100.0 * (closes[i] - lowest) / (highest - lowest) if highest != lowest else 50.0
    return out


def _last(series: Sequence[float | None]) -> float | None:
    for value in reversed(series):
        if value is not None:
            return value
    return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def analyze(candles: Sequence[Candle], symbol: str, resolution: str) -> dict[str, Any]:
    """Score a candle series and return a structured trading recommendation."""
    if len(candles) < 30:
        raise ValueError(
            f"Need at least 30 candles for analysis, received {len(candles)}"
        )

    closes = [float(c["c"]) for c in candles]
    highs = [float(c["h"]) for c in candles]
    lows = [float(c["l"]) for c in candles]
    volumes = [float(c.get("v", 0.0)) for c in candles]
    timestamps = [int(c["t"]) for c in candles]

    ema20 = ema_series(closes, 20)
    ema50 = ema_series(closes, 50)
    rsi14 = rsi_series(closes, 14)
    macd_line, macd_signal, macd_hist = macd_series(closes)
    bb_mid, bb_upper, bb_lower, bb_percent_b = bollinger_series(closes, 20)
    atr14 = atr_series(highs, lows, closes, 14)
    stoch_k = stochastic_series(highs, lows, closes, 14)
    volume_sma20 = sma_series(volumes, 20)

    price = closes[-1]
    score = 0.0
    reasons: list[str] = []
    bullish: list[str] = []
    bearish: list[str] = []

    def _vote(weight: float, bullish_side: bool, bull_reason: str, bear_reason: str) -> None:
        nonlocal score
        if bullish_side:
            score += weight
            bullish.append(bull_reason)
            reasons.append(bull_reason)
        else:
            score -= weight
            bearish.append(bear_reason)
            reasons.append(bear_reason)

    e20 = _last(ema20)
    e50 = _last(ema50)
    if e50 is not None:
        _vote(
            0.15,
            price > e50,
            f"Price {price:.6g} is above EMA50 ({e50:.6g}) — uptrend",
            f"Price {price:.6g} is below EMA50 ({e50:.6g}) — downtrend",
        )
    if e20 is not None and e50 is not None:
        _vote(
            0.15,
            e20 > e50,
            "EMA20 above EMA50 — bullish trend alignment",
            "EMA20 below EMA50 — bearish trend alignment",
        )

    hist = _last(macd_hist)
    if hist is not None:
        _vote(
            0.15,
            hist > 0,
            "MACD histogram positive — momentum is bullish",
            "MACD histogram negative — momentum is bearish",
        )

    rsi = _last(rsi14)
    if rsi is not None:
        if rsi < 30:
            _vote(0.2, True, f"RSI {rsi:.1f} is oversold — rebound potential", "")
        elif rsi > 70:
            _vote(0.2, False, "", f"RSI {rsi:.1f} is overbought — pullback risk")
        elif rsi >= 50:
            _vote(0.05, True, f"RSI {rsi:.1f} shows mild bullish bias", "")
        else:
            _vote(0.05, False, "", f"RSI {rsi:.1f} shows mild bearish bias")

    pct_b = _last(bb_percent_b)
    if pct_b is not None:
        if pct_b < 0.05:
            _vote(0.15, True, f"Price at lower Bollinger band (%B {pct_b:.2f})", "")
        elif pct_b > 0.95:
            _vote(0.15, False, "", f"Price at upper Bollinger band (%B {pct_b:.2f})")

    if len(closes) >= 21:
        momentum = (price / closes[-21] - 1.0) * 100.0
        _vote(
            0.1,
            momentum > 0,
            f"20-candle momentum +{momentum:.2f}%",
            f"20-candle momentum {momentum:.2f}%",
        )

    vol = volumes[-1]
    vol_avg = _last(volume_sma20)
    if vol_avg:
        if vol > vol_avg * 1.5:
            direction = "buying" if closes[-1] >= closes[-2] else "selling"
            reasons.append(
                f"Volume {vol:.4g} is {vol / vol_avg:.1f}x the 20-candle average — strong {direction} pressure"
            )

    score = _clamp(score, -1.0, 1.0)
    if score >= 0.2:
        signal = "BUY"
    elif score <= -0.2:
        signal = "SELL"
    else:
        signal = "HOLD"

    agreement = max(len(bullish), len(bearish))
    confidence = _clamp(0.5 + abs(score) * 0.45 + agreement * 0.02, 0.0, 0.95)

    atr = _last(atr14) or (price * 0.02)
    support = min(lows[-20:])
    resistance = max(highs[-20:])
    if signal == "SELL":
        stop_loss = price + 1.5 * atr
        take_profit = price - 3.0 * atr
    else:
        stop_loss = price - 1.5 * atr
        take_profit = price + 3.0 * atr

    indicators = {
        "ema20": _round(e20),
        "ema50": _round(e50),
        "rsi14": _round(rsi, 2),
        "macd": _round(_last(macd_line)),
        "macd_signal": _round(_last(macd_signal)),
        "macd_histogram": _round(hist),
        "bollinger_upper": _round(_last(bb_upper)),
        "bollinger_middle": _round(_last(bb_mid)),
        "bollinger_lower": _round(_last(bb_lower)),
        "bollinger_percent_b": _round(pct_b, 4),
        "atr14": _round(_last(atr14)),
        "stochastic_k": _round(_last(stoch_k), 2),
        "volume": _round(vol, 4),
        "volume_sma20": _round(vol_avg, 4),
    }

    chart = [
        {
            "t": timestamps[i],
            "o": _round(closes[i] if candles[i].get("o") is None else float(candles[i]["o"])),
            "h": _round(highs[i]),
            "l": _round(lows[i]),
            "c": _round(closes[i]),
            "v": _round(volumes[i], 4),
        }
        for i in range(len(candles))
    ]

    return {
        "symbol": symbol.upper(),
        "resolution": resolution,
        "as_of": timestamps[-1],
        "last_price": _round(price),
        "signal": signal,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
        "indicators": indicators,
        "levels": {
            "entry": _round(price),
            "stop_loss": _round(stop_loss),
            "take_profit": _round(take_profit),
            "risk_reward": 2.0,
            "support": _round(support),
            "resistance": _round(resistance),
        },
        "reasons": reasons,
        "candles": chart,
    }


def rank_analyses(analyses: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort analyses by conviction, BUY signals first."""
    return sorted(
        analyses,
        key=lambda item: (item["signal"] == "BUY", item["score"]),
        reverse=True,
    )
