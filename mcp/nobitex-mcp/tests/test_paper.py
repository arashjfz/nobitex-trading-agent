from decimal import Decimal

import httpx
import pytest

from nobitex_mcp.client import NobitexClient
from nobitex_mcp.errors import NobitexAPIError
from nobitex_mcp.paper import PaperBroker, PaperError


@pytest.fixture
def broker(monkeypatch):
    monkeypatch.setenv("NOBITEX_PAPER_BALANCES", '{"usdt":"10000","btc":"0.5","rls":"100000000"}')
    monkeypatch.setenv("NOBITEX_PAPER_FEE_RATE", "0.001")
    return PaperBroker()


def test_market_buy_fills_at_ask_and_updates_balances(broker):
    result = broker.handle(
        "POST",
        "/market/orders/add",
        None,
        {
            "type": "buy",
            "execution": "market",
            "srcCurrency": "btc",
            "dstCurrency": "usdt",
            "amount": "0.01",
        },
        market_price=lambda symbol, side: Decimal("68000"),
    )

    assert result["status"] == "ok"
    assert result["paper"] is True
    order = result["order"]
    assert order["status"] == "Done"
    assert order["averagePrice"] == "68000"
    assert broker.spot["btc"] == Decimal("0.51")
    assert broker.spot["usdt"] == Decimal("10000") - Decimal("680") - Decimal("0.68")
    assert len(broker.trades) == 1
    assert broker.trades[0]["price"] == "68000"


def test_insufficient_balance_rolls_back_order(broker):
    with pytest.raises(PaperError) as exc:
        broker.handle(
            "POST",
            "/market/orders/add",
            None,
            {
                "type": "buy",
                "execution": "market",
                "srcCurrency": "btc",
                "dstCurrency": "usdt",
                "amount": "100",
            },
            market_price=lambda symbol, side: Decimal("68000"),
        )
    assert exc.value.code == "InsufficientBalance"
    assert broker.orders == {}


def test_limit_order_stays_open_then_matches(broker):
    placed = broker.handle(
        "POST",
        "/market/orders/add",
        None,
        {
            "type": "buy",
            "execution": "limit",
            "srcCurrency": "btc",
            "dstCurrency": "usdt",
            "amount": "0.01",
            "price": "60000",
        },
        market_price=lambda symbol, side: Decimal("68000"),
    )
    order_id = placed["order"]["id"]
    assert placed["order"]["status"] == "Active"

    broker.market_price = lambda symbol, side: Decimal("59000")
    assert broker.match_open_orders() == 1

    status = broker.handle("POST", "/market/orders/status", None, {"id": order_id})
    assert status["order"]["status"] == "Done"
    assert status["order"]["averagePrice"] == "59000"


def test_cancel_open_order(broker):
    placed = broker.handle(
        "POST",
        "/market/orders/add",
        None,
        {
            "type": "sell",
            "execution": "limit",
            "srcCurrency": "btc",
            "dstCurrency": "usdt",
            "amount": "0.01",
            "price": "90000",
        },
        market_price=lambda symbol, side: Decimal("68000"),
    )
    order_id = placed["order"]["id"]

    canceled = broker.handle(
        "POST", "/market/orders/update-status", None, {"order": order_id, "status": "canceled"}
    )
    assert canceled["status"] == "ok"
    assert canceled["updatedStatus"] == "Canceled"
    assert broker.orders[order_id].status == "Canceled"


def test_list_orders_and_trades(broker):
    broker.handle(
        "POST",
        "/market/orders/add",
        None,
        {
            "type": "buy",
            "execution": "market",
            "srcCurrency": "btc",
            "dstCurrency": "usdt",
            "amount": "0.001",
        },
        market_price=lambda symbol, side: Decimal("68000"),
    )
    orders = broker.handle("GET", "/market/orders/list", {}, None)
    trades = broker.handle("GET", "/market/trades/list", {}, None)
    assert len(orders["orders"]) == 1
    assert len(trades["trades"]) == 1


def test_transfer_between_spot_and_margin(broker):
    result = broker.handle(
        "POST",
        "/wallets/transfer",
        None,
        {"currency": "usdt", "amount": "100", "src": "spot", "dst": "margin"},
    )
    assert result["status"] == "ok"
    assert broker.spot["usdt"] == Decimal("9900")
    assert broker.margin["usdt"] == Decimal("100")


def test_unsupported_path_raises(broker):
    with pytest.raises(PaperError) as exc:
        broker.handle("POST", "/users/wallets/withdraw", None, {})
    assert exc.value.code == "PaperModeUnsupported"


def test_public_paths_pass_through(broker):
    assert broker.handle("GET", "/v3/orderbook/BTCUSDT", None, None) is None
    assert broker.handle("GET", "/market/stats", None, None) is None


def test_client_dry_run_uses_paper_and_live_orderbook(monkeypatch):
    monkeypatch.setenv("NOBITEX_PAPER_BALANCES", '{"usdt":"10000","btc":"0"}')
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json={"status": "ok", "bids": [["67999", "1"]], "asks": [["68000", "1"]]},
        )

    client = NobitexClient(
        base_url="https://testnetapiv2.nobitex.ir",
        dry_run=True,
        transport=httpx.MockTransport(handler),
    )

    result = client.post(
        "/market/orders/add",
        body={
            "type": "buy",
            "execution": "market",
            "srcCurrency": "btc",
            "dstCurrency": "usdt",
            "amount": "0.01",
        },
    )
    assert result["paper"] is True
    assert result["order"]["averagePrice"] == "68000"
    assert calls == ["/v3/orderbook/BTCUSDT"]

    wallets = client.post("/users/wallets/list", body={})
    assert wallets["paper"] is True
    assert any(w["currency"] == "btc" and w["balance"] == "0.01" for w in wallets["wallets"])

    with pytest.raises(NobitexAPIError) as exc:
        client.post("/users/wallets/withdraw", body={})
    assert exc.value.code == "PaperModeUnsupported"
