"""Live smoke tests against the Nobitex testnet.

These only exercise public endpoints, so no credentials are required.
Enable with:

    NOBITEX_LIVE_TEST=1 uv run pytest tests/test_live_testnet.py -v
"""

import os

import pytest

from nobitex_mcp.client import NobitexClient

pytestmark = pytest.mark.skipif(
    os.getenv("NOBITEX_LIVE_TEST") != "1",
    reason="set NOBITEX_LIVE_TEST=1 to run live testnet tests",
)

TESTNET = "https://testnetapiv2.nobitex.ir"


@pytest.fixture(scope="module")
def client():
    with NobitexClient(base_url=TESTNET) as c:
        yield c


def test_orderbook(client):
    data = client.get("/v3/orderbook/BTCUSDT", auth=False)
    assert data["status"] == "ok"
    assert "bids" in data and "asks" in data


def test_market_stats(client):
    data = client.get(
        "/market/stats", params={"srcCurrency": "btc", "dstCurrency": "usdt"}, auth=False
    )
    assert data["status"] == "ok"
    assert "stats" in data


def test_system_options(client):
    data = client.get("/v2/options", auth=False)
    assert data["status"] == "ok"


def test_ohlc(client):
    import time

    now = int(time.time())
    data = client.get(
        "/market/udf/history",
        params={"symbol": "BTCUSDT", "resolution": "60", "from": now - 7200, "to": now},
        auth=False,
    )
    assert data["s"] in {"ok", "no_data"}
