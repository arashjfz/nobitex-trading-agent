import asyncio

import httpx
import pytest

from nobitex_mcp import server
from nobitex_mcp.client import NobitexClient


def run(coro):
    return asyncio.run(coro)


def test_tool_surface_covers_all_api_sections():
    tools = run(server.mcp.list_tools())
    names = {tool.name for tool in tools}

    expected = {
        "nobitex_server_info",
        # market data
        "nobitex_get_orderbook",
        "nobitex_get_market_depth",
        "nobitex_get_recent_trades",
        "nobitex_get_market_stats",
        "nobitex_get_ohlc_history",
        "nobitex_get_system_options",
        # user / wallets
        "nobitex_get_profile",
        "nobitex_get_wallets",
        "nobitex_get_wallet_balance",
        "nobitex_get_transactions_history",
        "nobitex_generate_deposit_address",
        # deposit addresses
        "nobitex_list_deposit_addresses",
        "nobitex_generate_deposit_address_v2",
        # spot
        "nobitex_place_spot_order",
        "nobitex_get_order_status",
        "nobitex_list_orders",
        "nobitex_cancel_order",
        "nobitex_cancel_old_orders",
        "nobitex_list_user_trades",
        # margin
        "nobitex_list_margin_markets",
        "nobitex_list_liquidity_pools",
        "nobitex_transfer_between_wallets",
        "nobitex_place_margin_order",
        "nobitex_list_positions",
        "nobitex_close_position",
        "nobitex_edit_position_collateral",
        # withdrawals
        "nobitex_withdraw_crypto",
        "nobitex_confirm_withdraw",
        "nobitex_list_withdrawals",
        "nobitex_request_rial_withdrawal",
        "nobitex_list_rial_withdraw_banks",
        # address book
        "nobitex_validate_address_network",
        "nobitex_create_address_book_item",
        "nobitex_confirm_address_book_item",
        "nobitex_list_address_book",
        "nobitex_activate_whitelist",
        # security
        "nobitex_get_login_attempts",
        "nobitex_get_anti_phishing",
        # referral
        "nobitex_list_referral_links",
        # auth
        "nobitex_login",
        "nobitex_logout",
        # api keys
        "nobitex_create_api_key",
        "nobitex_list_api_keys",
        # portfolio
        "nobitex_get_last_week_daily_profit",
        # websocket
        "nobitex_get_websocket_token",
        "nobitex_get_websocket_info",
        # paper trading
        "nobitex_paper_reset",
        "nobitex_paper_match_open_orders",
        # escape hatch
        "nobitex_request",
    }
    assert expected <= names
    assert len(names) >= 80


def test_server_info_reports_testnet(monkeypatch):
    client = NobitexClient(
        base_url="https://testnetapiv2.nobitex.ir",
        token="t",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    monkeypatch.setattr(server, "_CLIENT", client)

    info = server.nobitex_server_info()
    assert info["environment"] == "testnet"
    assert info["base_url"] == "https://testnetapiv2.nobitex.ir"
    assert info["is_testnet"] is True
    assert info["has_credentials"] is True


def test_public_tool_uses_global_client(monkeypatch):
    def handler(request):
        assert request.url.path == "/v3/orderbook/BTCUSDT"
        return httpx.Response(200, json={"status": "ok", "lastTradePrice": "100"})

    client = NobitexClient(
        base_url="https://testnetapiv2.nobitex.ir",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(server, "_CLIENT", client)

    assert server.nobitex_get_orderbook("BTCUSDT")["lastTradePrice"] == "100"


def test_tool_error_is_raised_for_api_failure(monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    client = NobitexClient(
        base_url="https://testnetapiv2.nobitex.ir",
        token="t",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"status": "failed", "code": "Bad"})
        ),
    )
    monkeypatch.setattr(server, "_CLIENT", client)

    with pytest.raises(ToolError):
        server.nobitex_get_profile()


def test_generic_request_rejects_relative_path(monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError):
        server.nobitex_request("GET", "users/profile")
