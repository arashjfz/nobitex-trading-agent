"""Nobitex market-data and trading helpers.

Thin wrapper around the vendored ``nobitex-mcp`` client so the REST API and
the agent share the same authentication, paper-trading and read-only guards.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Sequence

from nobitex_mcp import NobitexClient

from . import technical
from .config import Settings, get_settings

DEFAULT_SCAN_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "BTCIRT",
    "ETHIRT",
]

_QUOTE_SUFFIXES = ("USDT", "IRT", "RLS", "USD", "EUR", "BTC", "ETH")


def split_symbol(symbol: str) -> tuple[str, str]:
    """Split ``BTCUSDT`` into (``btc``, ``usdt``) using Nobitex conventions."""
    normalized = symbol.upper().replace("-", "").replace("/", "")
    for quote in _QUOTE_SUFFIXES:
        if normalized.endswith(quote) and len(normalized) > len(quote):
            base = normalized[: -len(quote)]
            dst = "rls" if quote == "IRT" else quote.lower()
            return base.lower(), dst
    raise ValueError(f"Cannot split market symbol: {symbol}")


@lru_cache
def get_client() -> NobitexClient:
    settings = get_settings()
    return build_client(settings)


def build_client(settings: Settings) -> NobitexClient:
    return NobitexClient(
        base_url=settings.resolved_nobitex_base_url,
        token=settings.nobitex_token,
        public_key=settings.nobitex_public_key,
        private_key=settings.nobitex_private_key,
        auth_mode=settings.nobitex_auth_mode,
        read_only=settings.nobitex_read_only,
        dry_run=settings.nobitex_dry_run,
        timeout=settings.nobitex_timeout,
    )


def parse_udf(payload: dict[str, Any]) -> list[technical.Candle]:
    """Convert a Nobitex UDF OHLC response into a list of candle dicts."""
    if payload.get("s") not in (None, "ok") and payload.get("status") != "ok":
        raise ValueError(f"Unexpected OHLC response: {payload.get('s') or payload.get('status')}")

    times = payload.get("t") or []
    opens = payload.get("o") or []
    highs = payload.get("h") or []
    lows = payload.get("l") or []
    closes = payload.get("c") or []
    volumes = payload.get("v") or []

    candles: list[technical.Candle] = []
    for i in range(min(len(times), len(opens), len(highs), len(lows), len(closes))):
        if closes[i] is None:
            continue
        candles.append(
            {
                "t": int(times[i]),
                "o": float(opens[i]),
                "h": float(highs[i]),
                "l": float(lows[i]),
                "c": float(closes[i]),
                "v": float(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0.0,
            }
        )
    return candles


def fetch_candles(
    symbol: str,
    resolution: str = "60",
    countback: int = 200,
    client: NobitexClient | None = None,
) -> list[technical.Candle]:
    client = client or get_client()
    payload = client.request(
        "GET",
        "/market/udf/history",
        params={
            "symbol": symbol.upper(),
            "resolution": resolution,
            "to": int(time.time()),
            "countback": countback,
        },
        auth=False,
    )
    return parse_udf(payload)


def fetch_market_stats(
    src_currency: str = "btc",
    dst_currency: str = "usdt",
    client: NobitexClient | None = None,
) -> dict[str, Any]:
    client = client or get_client()
    return client.request(
        "GET",
        "/market/stats",
        params={"srcCurrency": src_currency, "dstCurrency": dst_currency},
        auth=False,
    )


def normalize_stats(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the ``/market/stats`` map into a list of market summaries."""
    stats = payload.get("stats") or {}
    result: list[dict[str, Any]] = []
    for key, value in stats.items():
        if not isinstance(value, dict):
            continue
        if "-" in key:
            src, dst = key.split("-", 1)
        else:
            src, dst = key, ""
        quote = "IRT" if dst.lower() == "rls" else dst.upper()
        result.append(
            {
                "symbol": f"{src.upper()}{quote}",
                "src": src,
                "dst": dst,
                "price": _num(value.get("latest")),
                "change_pct": _num(value.get("dayChangePercent", value.get("dayChange"))),
                "high": _num(value.get("dayHigh")),
                "low": _num(value.get("dayLow")),
                "volume": _num(value.get("volumeDst", value.get("volumeSrc", value.get("volume")))),
                "best_buy": _num(value.get("bestBuy")),
                "best_sell": _num(value.get("bestSell")),
            }
        )
    return result


def fetch_all_markets(client: NobitexClient | None = None) -> list[dict[str, Any]]:
    """Return every market summary, mirroring the MCP ``nobitex_get_market_stats`` tool."""
    client = client or get_client()
    payload = client.request("GET", "/market/stats", auth=False)
    return normalize_stats(payload)


def fetch_orderbook(symbol: str, client: NobitexClient | None = None) -> dict[str, Any]:
    client = client or get_client()
    return client.request("GET", f"/v3/orderbook/{symbol.upper()}", auth=False)


def analyze_symbol(
    symbol: str,
    resolution: str = "60",
    countback: int = 200,
    client: NobitexClient | None = None,
) -> dict[str, Any]:
    candles = fetch_candles(symbol, resolution=resolution, countback=countback, client=client)
    return technical.analyze(candles, symbol=symbol, resolution=resolution)


def scan_symbols(
    symbols: Sequence[str] | None = None,
    resolution: str = "60",
    countback: int = 200,
    client: NobitexClient | None = None,
) -> dict[str, Any]:
    """Analyze several markets and return them ranked by conviction."""
    symbols = list(symbols or DEFAULT_SCAN_SYMBOLS)
    analyses: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for symbol in symbols:
        try:
            analyses.append(
                analyze_symbol(symbol, resolution=resolution, countback=countback, client=client)
            )
        except Exception as exc:  # noqa: BLE001 - one bad market must not fail the scan
            errors.append({"symbol": symbol.upper(), "error": str(exc)})
    return {
        "resolution": resolution,
        "opportunities": technical.rank_analyses(analyses),
        "errors": errors,
    }


def place_spot_order(
    symbol: str,
    side: str,
    amount: str,
    execution: str = "limit",
    price: str | None = None,
    client: NobitexClient | None = None,
) -> dict[str, Any]:
    src, dst = split_symbol(symbol)
    body: dict[str, Any] = {
        "type": side.lower(),
        "execution": execution,
        "srcCurrency": src,
        "dstCurrency": dst,
        "amount": str(amount),
    }
    if price is not None:
        body["price"] = str(price)
    client = client or get_client()
    return client.request("POST", "/market/orders/add", body=body)


def list_orders(client: NobitexClient | None = None) -> dict[str, Any]:
    client = client or get_client()
    return client.request("GET", "/market/orders/list", params={"status": "open"})


def cancel_order(order_id: int, client: NobitexClient | None = None) -> dict[str, Any]:
    client = client or get_client()
    return client.request(
        "POST", "/market/orders/update-status", body={"order": order_id, "status": "canceled"}
    )


def get_wallets(client: NobitexClient | None = None) -> dict[str, Any]:
    client = client or get_client()
    return client.request("POST", "/users/wallets/list", body={})


def server_info(client: NobitexClient | None = None) -> dict[str, Any]:
    client = client or get_client()
    return {
        "environment": client.settings.environment,
        "base_url": client.base_url,
        "is_testnet": client.settings.is_testnet,
        "has_credentials": client.has_credentials,
        "read_only": client.read_only,
        "dry_run": client.dry_run,
    }


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
