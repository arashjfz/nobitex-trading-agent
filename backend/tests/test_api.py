"""Tests for the HTTP API using monkeypatched market data (no network)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import nobitex
from app import main
from app.main import app


def _fake_analysis(symbol: str, resolution: str = "60", countback: int = 200, client=None):
    return {
        "symbol": symbol.upper(),
        "resolution": resolution,
        "as_of": 1_700_000_000,
        "last_price": 65000.0,
        "signal": "BUY",
        "score": 0.42,
        "confidence": 0.7,
        "indicators": {"rsi14": 55.0},
        "levels": {"entry": 65000.0, "stop_loss": 63000.0, "take_profit": 69000.0},
        "reasons": ["EMA20 above EMA50"],
        "candles": [],
    }


def test_health_reports_nobitex_mcp() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mcp"]["server"] == "nobitex"
    assert body["mcp"]["exists"] is True
    assert "nobitex" in body["nobitex"]["base_url"]


def test_config_exposes_default_mcp_server() -> None:
    with TestClient(app) as client:
        response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert "nobitex" in body["mcp_servers"]
    assert body["mcp_servers"]["nobitex"]["args"] == ["-m", "nobitex_mcp"]


def test_analysis_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(nobitex, "analyze_symbol", _fake_analysis)
    with TestClient(app) as client:
        response = client.get("/api/analysis/BTCUSDT?resolution=60")
    assert response.status_code == 200
    assert response.json()["signal"] == "BUY"


def test_markets_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        nobitex,
        "fetch_all_markets",
        lambda client=None: [
            {
                "symbol": "BTCIRT",
                "src": "btc",
                "dst": "rls",
                "price": 1.0,
                "change_pct": 0.0,
                "high": 1.0,
                "low": 1.0,
                "volume": 1.0,
            },
            {
                "symbol": "ETHUSDT",
                "src": "eth",
                "dst": "usdt",
                "price": 2.0,
                "change_pct": 0.0,
                "high": 2.0,
                "low": 2.0,
                "volume": 2.0,
            },
        ],
    )
    with TestClient(app) as client:
        response = client.get("/api/markets")
    assert response.status_code == 200
    assert [m["symbol"] for m in response.json()["markets"]] == ["ETHUSDT", "BTCIRT"]


def test_normalize_stats_maps_rls_to_irt() -> None:
    items = nobitex.normalize_stats({"stats": {"btc-rls": {"latest": "1"}}})
    assert items[0]["symbol"] == "BTCIRT"


def test_validate_cron_endpoint() -> None:
    with TestClient(app) as client:
        response = client.post("/api/schedules/validate", json={"cron": "0 9 * * *"})
    body = response.json()
    assert response.status_code == 200
    assert body["valid"] is True
    assert len(body["next_runs"]) == 3


def test_validate_cron_rejects_bad_expression() -> None:
    with TestClient(app) as client:
        response = client.post("/api/schedules/validate", json={"cron": "nope"})
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_create_schedule_endpoint(monkeypatch) -> None:
    captured: dict = {}

    def fake_create(prompt, cron, name=None, enabled=True):
        captured.update(prompt=prompt, cron=cron, name=name, enabled=enabled)
        return {"id": "t1", "prompt": prompt, "cron": cron, "name": name, "enabled": enabled}

    monkeypatch.setattr(main.scheduler, "create", fake_create)
    with TestClient(app) as client:
        response = client.post(
            "/api/schedules",
            json={"prompt": "buy up to $50", "cron": "*/30 * * * *", "name": "scan"},
        )
    assert response.status_code == 200
    assert response.json()["id"] == "t1"
    assert captured == {
        "prompt": "buy up to $50",
        "cron": "*/30 * * * *",
        "name": "scan",
        "enabled": True,
    }


def test_opportunities_endpoint(monkeypatch) -> None:
    def fake_scan(symbols=None, resolution="60", countback=200, client=None):
        return {
            "resolution": resolution,
            "opportunities": [_fake_analysis("BTCUSDT")],
            "errors": [],
        }

    monkeypatch.setattr(nobitex, "scan_symbols", fake_scan)
    with TestClient(app) as client:
        response = client.get("/api/opportunities?symbols=BTCUSDT,ETHUSDT")
    assert response.status_code == 200
    assert response.json()["opportunities"][0]["symbol"] == "BTCUSDT"


def test_limit_order_requires_price() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/orders",
            json={"symbol": "BTCUSDT", "side": "buy", "amount": "0.001", "execution": "limit"},
        )
    assert response.status_code == 422


def test_place_order(monkeypatch) -> None:
    captured: dict = {}

    def fake_order(symbol, side, amount, execution="limit", price=None, client=None):
        captured.update(symbol=symbol, side=side, amount=amount, price=price)
        return {"status": "ok", "order": {"id": 1}, "paper": True}

    monkeypatch.setattr(nobitex, "place_spot_order", fake_order)
    with TestClient(app) as client:
        response = client.post(
            "/api/orders",
            json={
                "symbol": "BTCUSDT",
                "side": "buy",
                "amount": "0.001",
                "execution": "limit",
                "price": "60000",
            },
        )
    assert response.status_code == 200
    assert captured == {"symbol": "BTCUSDT", "side": "buy", "amount": "0.001", "price": "60000"}


def test_session_lifecycle() -> None:
    with TestClient(app) as client:
        created = client.post("/api/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        fetched = client.get(f"/api/sessions/{session_id}")
        assert fetched.status_code == 200
        assert fetched.json()["status"] == "idle"

        missing = client.get("/api/sessions/does-not-exist")
        assert missing.status_code == 404
