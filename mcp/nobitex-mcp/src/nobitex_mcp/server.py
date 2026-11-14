"""Nobitex MCP server: full-coverage tools for the Nobitex exchange API.

Tools are grouped by the official API sections:

* market data (public)
* user data / wallets / deposit addresses
* spot trading
* margin trading
* withdrawals (crypto + rial)
* address book / whitelist
* security
* referral
* authentication
* API keys
* portfolio / P&L
* websocket helpers
* generic escape hatch for any documented path

Set ``NOBITEX_ENV=testnet`` to point every tool at
``https://testnetapiv2.nobitex.ir`` for safe agent testing.
"""

from __future__ import annotations

import json
from typing import Any, Literal
from urllib.parse import quote

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .client import NobitexClient
from .errors import NobitexAPIError, NobitexError

mcp = MCPServer(
    name="nobitex",
    title="Nobitex Exchange",
    version="1.0.0",
    instructions=(
        "Tools for the Nobitex cryptocurrency exchange (Iranian market). "
        "Public market-data tools work without credentials. Trading, wallet, "
        "withdrawal, address-book, security and API-key tools require "
        "NOBITEX_TOKEN or an Ed25519 API key. Use NOBITEX_ENV=testnet "
        "(https://testnetapiv2.nobitex.ir) to exercise the agent safely. "
        "Monetary values are strings; send amounts and prices as decimal strings. "
        "Always confirm the active environment with nobitex_server_info before trading."
    ),
)

_CLIENT: NobitexClient | None = None


def get_client() -> NobitexClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = NobitexClient()
    return _CLIENT


def _call(method: str, path: str, **kwargs: Any) -> Any:
    try:
        return get_client().request(method, path, **kwargs)
    except NobitexAPIError as exc:
        raise ToolError(json.dumps(exc.to_dict(), ensure_ascii=False)) from exc
    except NobitexError as exc:
        raise ToolError(str(exc)) from exc


def _q(value: Any) -> str:
    return quote(str(value), safe="")


def _clean(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


# ===========================================================================
# Server / environment
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_server_info() -> Any:
    """Report the active Nobitex environment, base URL and credential status.

    Call this first to confirm whether the server is pointed at mainnet or
    testnet and whether trading credentials are configured.
    """
    client = get_client()
    return {
        "environment": client.settings.environment,
        "base_url": client.base_url,
        "is_testnet": client.settings.is_testnet,
        "has_credentials": client.has_credentials,
        "auth_mode": client.settings.auth_mode
        or ("token" if client.settings.token else "key" if client.settings.public_key else None),
        "read_only": client.read_only,
        "dry_run": client.dry_run,
        "paper_balances": (
            {currency: str(balance) for currency, balance in client.paper.spot.items()}
            if client.paper is not None
            else None
        ),
        "user_agent": client.user_agent,
    }


# ===========================================================================
# Market data (public)
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_get_orderbook(symbol: str = "all") -> Any:
    """Get the level-2 order book for one market or all markets.

    Args:
        symbol: Market symbol such as BTCIRT or BTCUSDT, or "all".
    """
    return _call("GET", f"/v3/orderbook/{_q(symbol)}", auth=False)


@mcp.tool(structured_output=False)
def nobitex_get_market_depth(symbol: str) -> Any:
    """Get aggregated market depth for a single market.

    Args:
        symbol: Market symbol such as BTCIRT or BTCUSDT ("all" is not supported).
    """
    return _call("GET", f"/v2/depth/{_q(symbol)}", auth=False)


@mcp.tool(structured_output=False)
def nobitex_get_recent_trades(symbol: str) -> Any:
    """Get the most recent public trades for a single market.

    Args:
        symbol: Market symbol such as BTCIRT or BTCUSDT ("all" is not supported).
    """
    return _call("GET", f"/v2/trades/{_q(symbol)}", auth=False)


@mcp.tool(structured_output=False)
def nobitex_get_market_stats(
    src_currency: str | None = None,
    dst_currency: str | None = None,
) -> Any:
    """Get 24h market statistics (price, volume, change) for markets.

    Args:
        src_currency: Source currency or comma-separated list, e.g. "btc,eth".
        dst_currency: Destination currency or comma-separated list, e.g. "rls,usdt".
    """
    params = _clean({"srcCurrency": src_currency, "dstCurrency": dst_currency})
    return _call("GET", "/market/stats", params=params, auth=False)


@mcp.tool(structured_output=False)
def nobitex_get_ohlc_history(
    symbol: str,
    resolution: Literal["1", "5", "15", "30", "60", "180", "240", "360", "720", "D", "1D", "2D", "3D"],
    to: int,
    from_ts: int | None = None,
    countback: int | None = None,
    page: int | None = None,
) -> Any:
    """Get OHLC candle history for a market.

    Args:
        symbol: Market symbol such as BTCIRT or BTCUSDT.
        resolution: Candle timeframe: minutes (1,5,15,30,60,180,240,360,720) or days (D,1D,2D,3D).
        to: End time as a Unix timestamp in seconds.
        from_ts: Start time as a Unix timestamp in seconds.
        countback: Number of candles before `to` (max 500); takes priority over `from_`.
        page: Page number for older candles.
    """
    params = _clean(
        {
            "symbol": symbol,
            "resolution": resolution,
            "from": from_ts,
            "to": to,
            "countback": countback,
            "page": page,
        }
    )
    return _call("GET", "/market/udf/history", params=params, auth=False)


@mcp.tool(structured_output=False)
def nobitex_get_system_options() -> Any:
    """Get exchange system options: currencies, networks, tags and withdrawal limits."""
    return _call("GET", "/v2/options", auth=False)


# ===========================================================================
# User data / wallets
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_get_profile() -> Any:
    """Get the authenticated user's profile (KYC level, bank accounts, cards)."""
    return _call("GET", "/users/profile")


@mcp.tool(structured_output=False)
def nobitex_get_wallets(type: Literal["spot", "margin", "credit", "debit"] | None = None) -> Any:
    """List the user's wallets and balances.

    Args:
        type: Optional wallet type filter.
    """
    return _call("POST", "/users/wallets/list", body=_clean({"type": type}))


@mcp.tool(structured_output=False)
def nobitex_get_selected_wallets(
    currencies: str | None = None,
    type: Literal["spot", "margin", "credit", "debit"] | None = None,
) -> Any:
    """List selected wallets, optionally filtered by currencies.

    Args:
        currencies: Comma-separated currency list, e.g. "btc,usdt".
        type: Optional wallet type filter.
    """
    return _call("POST", "/v2/wallets", body=_clean({"currencies": currencies, "type": type}))


@mcp.tool(structured_output=False)
def nobitex_get_wallet_balance(currency: str) -> Any:
    """Get the balance of one currency wallet.

    Args:
        currency: Currency symbol, e.g. "btc" or "rls".
    """
    return _call("POST", "/users/wallets/balance", body={"currency": currency})


@mcp.tool(structured_output=False)
def nobitex_list_wallet_transactions(
    wallet: int,
    page: int | None = None,
    page_size: int | None = None,
    details: int | None = None,
) -> Any:
    """List transactions for a single wallet.

    Args:
        wallet: Wallet id.
        page: Page number.
        page_size: Items per page.
        details: Detail level.
    """
    params = _clean({"wallet": wallet, "page": page, "pageSize": page_size, "details": details})
    return _call("GET", "/users/wallets/transactions/list", params=params)


@mcp.tool(structured_output=False)
def nobitex_get_transactions_history(
    currency: str | None = None,
    tp: str | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    from_id: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
    details: int | None = None,
    download: bool | None = None,
) -> Any:
    """Get the user's transaction history across wallets.

    Args:
        currency: Optional currency filter.
        tp: Transaction type list (API-specific string).
        from_ts: Start time as Unix timestamp (seconds).
        to_ts: End time as Unix timestamp (seconds).
        from_id: Minimum transaction id.
        page: Page number.
        page_size: Items per page.
        details: Detail level.
        download: Request a downloadable export when supported.
    """
    params = _clean(
        {
            "currency": currency,
            "tp": tp,
            "from": from_ts,
            "to": to_ts,
            "from_id": from_id,
            "page": page,
            "pageSize": page_size,
            "details": details,
            "download": download,
        }
    )
    return _call("GET", "/users/transactions-history", params=params)


@mcp.tool(structured_output=False)
def nobitex_list_deposits(
    wallet: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List crypto deposits.

    Args:
        wallet: Optional wallet id; all wallets when omitted.
        page: Page number.
        page_size: Items per page.
    """
    params = _clean({"wallet": wallet, "page": page, "pageSize": page_size})
    return _call("GET", "/users/wallets/deposits/list", params=params)


@mcp.tool(structured_output=False)
def nobitex_get_limitations() -> Any:
    """Get the user's account limitations and verification limits."""
    return _call("POST", "/users/limitations", body={})


@mcp.tool(structured_output=False)
def nobitex_generate_deposit_address(
    wallet: int | None = None,
    currency: str | None = None,
    network: str | None = None,
    address_type: Literal["default", "legacy"] | None = None,
) -> Any:
    """Generate a blockchain deposit address.

    Args:
        wallet: Spot wallet id.
        currency: Currency code when wallet is omitted.
        network: Network name.
        address_type: Address type, "default" or "legacy".
    """
    body = _clean(
        {"wallet": wallet, "currency": currency, "network": network, "addressType": address_type}
    )
    return _call("POST", "/users/wallets/generate-address", body=body)


@mcp.tool(structured_output=False)
def nobitex_add_bank_card(number: str, bank: str | None = None) -> Any:
    """Add a bank card to the user's profile.

    Args:
        number: Card number.
        bank: Bank name; defaults to "سایر" on the server.
    """
    return _call("POST", "/users/cards-add", body=_clean({"number": number, "bank": bank}))


@mcp.tool(structured_output=False)
def nobitex_add_bank_account(shaba: str, number: str | None = None) -> Any:
    """Add a bank account (IBAN/SHABA) to the user's profile.

    Args:
        shaba: SHABA/IBAN number.
        number: Optional account number.
    """
    return _call("POST", "/users/accounts-add", body=_clean({"number": number, "shaba": shaba}))


@mcp.tool(structured_output=False)
def nobitex_delete_bank_card(id: int) -> Any:
    """Delete a bank card by id."""
    return _call("POST", "/users/cards-delete", body={"id": id})


@mcp.tool(structured_output=False)
def nobitex_delete_bank_account(id: int) -> Any:
    """Delete a bank account by id."""
    return _call("POST", "/users/accounts-delete", body={"id": id})


# ===========================================================================
# Deposit addresses (multi-address API)
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_list_deposit_addresses(
    network: str,
    coin: str,
    ordering: Literal["created_at", "-created_at"] | None = None,
    is_disabled: bool | None = None,
    search: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List generated deposit addresses for a coin/network.

    Args:
        network: Network name, e.g. "ETH".
        coin: Coin symbol, e.g. "eth".
        ordering: Sort by creation time, newest first by default.
        is_disabled: true = disabled only, false = active only.
        search: Substring search on address title.
        page: Page number.
        page_size: Items per page.
    """
    params = _clean(
        {
            "network": network,
            "coin": coin,
            "ordering": ordering,
            "is_disabled": is_disabled,
            "search": search,
            "page": page,
            "pageSize": page_size,
        }
    )
    return _call("GET", "/users/wallets/deposit/address/list", params=params)


@mcp.tool(structured_output=False)
def nobitex_generate_deposit_address_v2(
    coin: str,
    network: str,
    title: str | None = None,
) -> Any:
    """Generate a new deposit address (multi-address API).

    Args:
        coin: Coin symbol.
        network: Network name.
        title: Optional address title.
    """
    return _call(
        "POST",
        "/users/wallets/deposit/address/generate",
        body=_clean({"coin": coin, "network": network, "title": title}),
    )


@mcp.tool(structured_output=False)
def nobitex_update_deposit_address_title(address_id: int, title: str | None = None) -> Any:
    """Update the title of a deposit address.

    Args:
        address_id: Address id from the list/generate endpoints.
        title: New title; empty/null clears it.
    """
    return _call(
        "POST",
        "/users/wallets/deposit/address/update",
        body=_clean({"address_id": address_id, "title": title}),
    )


# ===========================================================================
# Spot trading
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_place_spot_order(
    type: Literal["buy", "sell"],
    src_currency: str,
    dst_currency: str,
    amount: str,
    execution: Literal["limit", "market", "stop_limit", "stop_market"] = "limit",
    price: str | None = None,
    client_order_id: str | None = None,
    pro: bool | None = None,
    mode: Literal["default", "oco"] | None = None,
    stop_price: str | None = None,
    stop_limit_price: str | None = None,
) -> Any:
    """Place a spot order.

    Args:
        type: Order side, "buy" or "sell".
        src_currency: Source/base currency, e.g. "btc".
        dst_currency: Destination/quote currency, e.g. "usdt" or "rls".
        amount: Order size in src_currency, as a decimal string.
        execution: "limit" (default), "market", "stop_limit" or "stop_market".
        price: Unit price; required for limit/stop_limit. Decimal string.
        client_order_id: Optional unique client id (max 32 chars).
        pro: Disable the 10-second duplicate-order check.
        mode: Set "oco" for an OCO order.
        stop_price: Trigger price for stop orders / OCO.
        stop_limit_price: Paired stop-limit price for OCO.
    """
    body = _clean(
        {
            "type": type,
            "execution": execution,
            "srcCurrency": src_currency,
            "dstCurrency": dst_currency,
            "amount": amount,
            "price": price,
            "clientOrderId": client_order_id,
            "pro": pro,
            "mode": mode,
            "stopPrice": stop_price,
            "stopLimitPrice": stop_limit_price,
        }
    )
    return _call("POST", "/market/orders/add", body=body)


@mcp.tool(structured_output=False)
def nobitex_get_order_status(id: int | None = None, client_order_id: str | None = None) -> Any:
    """Get the status of one order by id or client order id.

    Args:
        id: Server order id.
        client_order_id: Client order id.
    """
    body = _clean({"id": id, "clientOrderId": client_order_id})
    if not body:
        raise ToolError("Provide either id or client_order_id")
    return _call("POST", "/market/orders/status", body=body)


@mcp.tool(structured_output=False)
def nobitex_list_orders(
    status: Literal["all", "open", "done", "close"] | None = None,
    type: Literal["buy", "sell"] | None = None,
    execution: Literal["limit", "market", "stop_limit", "stop_market"] | None = None,
    trade_type: Literal["spot", "margin"] | None = None,
    src_currency: str | None = None,
    dst_currency: str | None = None,
    details: Literal[1, 2] | None = None,
    from_id: int | None = None,
    order: Literal["id", "-id", "created_at", "-created_at", "price", "-price"] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List the user's orders with optional filters.

    Args:
        status: all, open, done or close.
        type: buy or sell.
        execution: Order execution type.
        trade_type: spot or margin.
        src_currency: Source currency, e.g. "btc".
        dst_currency: Destination currency, e.g. "rls".
        details: Detail level, 1 or 2.
        from_id: Only orders with id >= from_id (do not combine with page).
        order: Sort order.
        page: Page number.
        page_size: Items per page.
    """
    params = _clean(
        {
            "status": status,
            "type": type,
            "execution": execution,
            "tradeType": trade_type,
            "srcCurrency": src_currency,
            "dstCurrency": dst_currency,
            "details": details,
            "fromId": from_id,
            "order": order,
            "page": page,
            "pageSize": page_size,
        }
    )
    return _call("GET", "/market/orders/list", params=params)


@mcp.tool(structured_output=False)
def nobitex_cancel_order(order: int | None = None, client_order_id: str | None = None) -> Any:
    """Cancel a single open order.

    Args:
        order: Server order id.
        client_order_id: Client order id.
    """
    body = _clean({"order": order, "clientOrderId": client_order_id, "status": "canceled"})
    if order is None and client_order_id is None:
        raise ToolError("Provide either order or client_order_id")
    return _call("POST", "/market/orders/update-status", body=body)


@mcp.tool(structured_output=False)
def nobitex_cancel_old_orders(
    hours: float | None = None,
    execution: Literal["market", "limit", "stop_market", "stop_limit"] | None = None,
    trade_type: Literal["spot", "margin"] | None = None,
    src_currency: str | None = None,
    dst_currency: str | None = None,
) -> Any:
    """Cancel old open orders in bulk.

    Args:
        hours: Cancel orders older than this many hours.
        execution: Filter by execution type.
        trade_type: Filter by spot or margin.
        src_currency: Filter by source currency.
        dst_currency: Filter by destination currency.
    """
    body = _clean(
        {
            "hours": hours,
            "execution": execution,
            "tradeType": trade_type,
            "srcCurrency": src_currency,
            "dstCurrency": dst_currency,
        }
    )
    return _call("POST", "/market/orders/cancel-old", body=body)


@mcp.tool(structured_output=False)
def nobitex_list_user_trades(
    src_currency: str | None = None,
    dst_currency: str | None = None,
    from_id: int | None = None,
    trade_type: Literal["buy", "sell"] | None = None,
    trade_order: Literal["asc", "desc"] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List the user's executed trades.

    Args:
        src_currency: Source currency (must be paired with dst_currency).
        dst_currency: Destination currency (must be paired with src_currency).
        from_id: Minimum trade id.
        trade_type: buy or sell.
        trade_order: asc or desc (default desc).
        page: Page number.
        page_size: Items per page.
    """
    params = _clean(
        {
            "srcCurrency": src_currency,
            "dstCurrency": dst_currency,
            "fromId": from_id,
            "tradeType": trade_type,
            "tradeOrder": trade_order,
            "page": page,
            "pageSize": page_size,
        }
    )
    return _call("GET", "/market/trades/list", params=params)


# ===========================================================================
# Margin trading
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_list_margin_markets(details: bool | None = None) -> Any:
    """List margin markets.

    Args:
        details: Include extra market details such as delegation limits.
    """
    return _call("GET", "/margin/markets/list", params=_clean({"details": details}))


@mcp.tool(structured_output=False)
def nobitex_list_liquidity_pools() -> Any:
    """List active liquidity/delegation pools."""
    return _call("GET", "/liquidity-pools/list")


@mcp.tool(structured_output=False)
def nobitex_transfer_between_wallets(
    currency: str,
    amount: str,
    src: Literal["spot", "margin"],
    dst: Literal["spot", "margin"],
) -> Any:
    """Transfer funds between the spot and margin wallets.

    Args:
        currency: Currency name.
        amount: Amount as a decimal string.
        src: Source wallet, "spot" or "margin".
        dst: Destination wallet, "spot" or "margin".
    """
    return _call(
        "POST",
        "/wallets/transfer",
        body={"currency": currency, "amount": amount, "src": src, "dst": dst},
    )


@mcp.tool(structured_output=False)
def nobitex_get_margin_delegation_limit(market: str) -> Any:
    """Get the delegation limit for a margin market.

    Args:
        market: Market symbol, e.g. "BTCIRT".
    """
    return _call("GET", "/margin/v2/delegation-limit", params={"market": market})


@mcp.tool(structured_output=False)
def nobitex_place_margin_order(
    type: Literal["buy", "sell"],
    src_currency: str,
    dst_currency: str,
    amount: str,
    execution: Literal["limit", "market", "stop_limit", "stop_market"] = "limit",
    price: str | None = None,
    stop_price: str | None = None,
    stop_limit_price: str | None = None,
    leverage: str | None = None,
    client_order_id: str | None = None,
    mode: Literal["default", "oco"] | None = None,
) -> Any:
    """Place a margin (leverage) order.

    Args:
        type: Order side, "buy" or "sell".
        src_currency: Base currency, e.g. "btc".
        dst_currency: Quote currency, e.g. "usdt".
        amount: Order size as a decimal string.
        execution: "limit", "market", "stop_limit" or "stop_market".
        price: Limit price (required for limit/stop_limit).
        stop_price: Trigger price (required for stop orders / OCO).
        stop_limit_price: Paired stop-limit price (required for OCO).
        leverage: Leverage multiplier as a string, e.g. "2".
        client_order_id: Optional unique client id.
        mode: Set "oco" for an OCO order.
    """
    body = _clean(
        {
            "type": type,
            "execution": execution,
            "srcCurrency": src_currency,
            "dstCurrency": dst_currency,
            "amount": amount,
            "price": price,
            "stopPrice": stop_price,
            "stopLimitPrice": stop_limit_price,
            "leverage": leverage,
            "clientOrderId": client_order_id,
            "mode": mode,
        }
    )
    return _call("POST", "/margin/orders/add", body=body)


@mcp.tool(structured_output=False)
def nobitex_list_positions(
    src_currency: str | None = None,
    dst_currency: str | None = None,
    status: Literal["active", "past"] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List margin positions.

    Args:
        src_currency: Base currency filter.
        dst_currency: Quote currency filter.
        status: "active" (open) or "past" (settled/closed/liquidated).
        page: Page number.
        page_size: Items per page.
    """
    params = _clean(
        {
            "srcCurrency": src_currency,
            "dstCurrency": dst_currency,
            "status": status,
            "page": page,
            "pageSize": page_size,
        }
    )
    return _call("GET", "/positions/list", params=params)


@mcp.tool(structured_output=False)
def nobitex_get_position_status(position_id: int) -> Any:
    """Get one margin position by id."""
    return _call("GET", f"/positions/{_q(position_id)}/status")


@mcp.tool(structured_output=False)
def nobitex_close_position(
    position_id: int,
    execution: Literal["limit", "market", "stop_limit", "stop_market"] = "market",
    amount: str | None = None,
    price: str | None = None,
    stop_price: str | None = None,
    stop_limit_price: str | None = None,
    client_order_id: str | None = None,
) -> Any:
    """Close (settle) a margin position.

    Args:
        position_id: Position id.
        execution: Close execution type; "market" closes at best price.
        amount: Amount to settle as a decimal string.
        price: Limit price for limit/stop_limit closes.
        stop_price: Trigger price for stop closes.
        stop_limit_price: Paired stop-limit price.
        client_order_id: Optional client order id.
    """
    body = _clean(
        {
            "execution": execution,
            "amount": amount,
            "price": price,
            "stopPrice": stop_price,
            "stopLimitPrice": stop_limit_price,
            "clientOrderId": client_order_id,
        }
    )
    return _call("POST", f"/positions/{_q(position_id)}/close", body=body)


@mcp.tool(structured_output=False)
def nobitex_edit_position_collateral(position_id: int, collateral: str) -> Any:
    """Set the total collateral of an open margin position.

    Args:
        position_id: Position id.
        collateral: New total collateral as a decimal string (not a delta).
    """
    return _call(
        "POST", f"/positions/{_q(position_id)}/edit-collateral", body={"collateral": collateral}
    )


# ===========================================================================
# Withdrawals (crypto)
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_withdraw_crypto(
    wallet: int,
    amount: str | None = None,
    address: str | None = None,
    network: str | None = None,
    tag: str | None = None,
    no_tag: bool | None = None,
    invoice: str | None = None,
    explanations: str | None = None,
    totp: str | None = None,
) -> Any:
    """Request a crypto withdrawal.

    Args:
        wallet: Spot wallet id.
        amount: Amount as a decimal string (omit for Lightning invoices).
        address: Destination address (omit for Lightning invoices).
        network: Network name; required for multi-network assets such as USDT.
        tag: Destination tag/memo where supported.
        no_tag: Set true to withdraw without a tag.
        invoice: Lightning invoice (BTCLN), replaces amount/address.
        explanations: Optional note.
        totp: 2FA code when the destination is not whitelisted.
    """
    body = _clean(
        {
            "wallet": wallet,
            "amount": amount,
            "address": address,
            "network": network,
            "tag": tag,
            "noTag": no_tag,
            "invoice": invoice,
            "explanations": explanations,
        }
    )
    return _call("POST", "/users/wallets/withdraw", body=body, totp=totp)


@mcp.tool(structured_output=False)
def nobitex_confirm_withdraw(withdraw: int, otp: str | None = None) -> Any:
    """Confirm a pending withdrawal.

    Args:
        withdraw: Withdrawal id returned by the request step.
        otp: SMS one-time code when required.
    """
    return _call("POST", "/users/wallets/withdraw-confirm", body=_clean({"withdraw": withdraw, "otp": otp}))


@mcp.tool(structured_output=False)
def nobitex_cancel_withdraw(withdraw: int) -> Any:
    """Cancel a pending crypto withdrawal."""
    return _call("POST", "/users/wallets/withdraw-cancel", body={"withdraw": withdraw})


@mcp.tool(structured_output=False)
def nobitex_list_withdrawals(
    wallet: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """List crypto withdrawals.

    Args:
        wallet: Wallet id or "all".
        from_date: Start date, YYYY-MM-DD.
        to_date: End date, YYYY-MM-DD.
        page: Page number.
        page_size: Items per page.
    """
    params = _clean(
        {"wallet": wallet, "from": from_date, "to": to_date, "page": page, "pageSize": page_size}
    )
    return _call("GET", "/users/wallets/withdraws/list", params=params)


@mcp.tool(structured_output=False)
def nobitex_get_withdrawal(withdraw_id: int) -> Any:
    """Get details of one withdrawal by id."""
    return _call("GET", f"/withdraws/{_q(withdraw_id)}")


# ===========================================================================
# Withdrawals (rial / Cobank)
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_request_rial_withdrawal(destination_bank_account_id: int, amount: str) -> Any:
    """Request a rial withdrawal to a verified bank account.

    Args:
        destination_bank_account_id: Verified bank account id.
        amount: Total amount in rial as a decimal string (fee is deducted).
    """
    return _call(
        "POST",
        "/cobank/withdraw",
        body={"destinationBankAccountId": destination_bank_account_id, "amount": amount},
    )


@mcp.tool(structured_output=False)
def nobitex_get_rial_withdrawal(withdraw_id: str) -> Any:
    """Get details of one rial withdrawal (id prefixed CW/WJ/W)."""
    return _call("GET", f"/cobank/withdraw/{_q(withdraw_id)}")


@mcp.tool(structured_output=False)
def nobitex_list_rial_withdraw_banks() -> Any:
    """List banks supported for instant rial withdrawal."""
    return _call("GET", "/cobank/withdraw-banks")


@mcp.tool(structured_output=False)
def nobitex_cancel_rial_withdrawal(withdraw_id: str) -> Any:
    """Cancel a pending rial withdrawal."""
    return _call("POST", f"/cobank/withdraw/{_q(withdraw_id)}/cancel")


# ===========================================================================
# Address book / whitelist
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_validate_address_network(network: str, address: str, tag: str | None = None) -> Any:
    """Validate a destination address (and optional tag) for a network.

    Args:
        network: Network name, e.g. "BSC".
        address: Destination wallet address.
        tag: Optional tag/memo.
\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call(
        "GET",
        "/security/validate-address-network",
        params=_clean({"network": network, "address": address, "tag": tag}),
    )


@mcp.tool(structured_output=False)
def nobitex_create_address_book_item(
    title: str,
    network: str,
    address: str,
    tfa_code: str,
    tag: str | None = None,
) -> Any:
    """Create an inactive address-book item (step 1 of 2).

    Args:
        title: Address title.
        network: Network name.
        address: Destination address.
        tfa_code: TOTP two-factor code.
        tag: Optional tag/memo.
    """
    return _call(
        "POST",
        "/security/address-book-item/create",
        body=_clean(
            {"title": title, "network": network, "address": address, "tag": tag, "tfaCode": tfa_code}
        ),
    )


@mcp.tool(structured_output=False)
def nobitex_confirm_address_book_item(id: int, otp_code: str) -> Any:
    """Confirm an address-book item (step 2 of 2).

    Args:
        id: address_book_item_id from the create step.
        otp_code: OTP obtained from /v2/otp/request with usage=address_book.
    """
    return _call(
        "POST", "/security/address-book-item/confirm", body={"id": id, "otpCode": otp_code}
    )


@mcp.tool(structured_output=False)
def nobitex_list_address_book(network: str | None = None) -> Any:
    """List address-book entries, optionally filtered by network."""
    return _call("GET", "/address_book", params=_clean({"network": network}))


@mcp.tool(structured_output=False)
def nobitex_add_address_book(
    title: str,
    network: str,
    address: str,
    otp_code: str,
    tfa_code: str,
    tag: str | None = None,
) -> Any:
    """Add an address-book entry in one step (legacy flow).

    Args:
        title: Address title.
        network: Network name.
        address: Destination address.
        otp_code: SMS/email one-time code.
        tfa_code: TOTP two-factor code.
        tag: Optional tag/memo.
    """
    return _call(
        "POST",
        "/address_book",
        body=_clean(
            {
                "title": title,
                "network": network,
                "address": address,
                "tag": tag,
                "otpCode": otp_code,
                "tfaCode": tfa_code,
            }
        ),
    )


@mcp.tool(structured_output=False)
def nobitex_delete_address_book(address_id: int) -> Any:
    """Delete an address-book entry by id."""
    return _call("DELETE", f"/address_book/{_q(address_id)}/delete")


@mcp.tool(structured_output=False)
def nobitex_activate_whitelist() -> Any:
    """Enable secure-withdrawal (whitelist) mode."""
    return _call("POST", "/address_book/whitelist/activate")


@mcp.tool(structured_output=False)
def nobitex_deactivate_whitelist(otp_code: str, tfa_code: str) -> Any:
    """Disable secure-withdrawal (whitelist) mode.

    Args:
        otp_code: SMS/email one-time code.
        tfa_code: TOTP two-factor code.
    """
    return _call(
        "POST",
        "/address_book/whitelist/deactivate",
        body={"otpCode": otp_code, "tfaCode": tfa_code},
    )


# ===========================================================================
# Security
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_get_login_attempts() -> Any:
    """Get the user's login attempt history.\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("POST", "/users/login-attempts", body={})


@mcp.tool(structured_output=False)
def nobitex_get_emergency_cancel_code() -> Any:
    """Get an emergency withdrawal-cancel code."""
    return _call("POST", "/security/emergency-cancel/get-code", body={})


@mcp.tool(structured_output=False)
def nobitex_activate_emergency_cancel() -> Any:
    """Activate emergency withdrawal cancellation."""
    return _call("POST", "/security/emergency-cancel/activate", body={})


@mcp.tool(structured_output=False)
def nobitex_get_anti_phishing() -> Any:
    """Get the account anti-phishing code.\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("GET", "/security/anti-phishing")


@mcp.tool(structured_output=False)
def nobitex_set_anti_phishing(code: str, otp_code: str) -> Any:
    """Create or change the anti-phishing code.

    Args:
        code: New anti-phishing code.
        otp_code: One-time code sent to the user.
\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("POST", "/security/anti-phishing", body={"code": code, "otpCode": otp_code})


# ===========================================================================
# Referral
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_list_referral_links() -> Any:
    """List the user's referral links.\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("POST", "/users/referral/links-list", body={})


@mcp.tool(structured_output=False)
def nobitex_create_referral_link(friend_share: int | None = None, agenda: str | None = None) -> Any:
    """Create a referral link.

    Args:
        friend_share: Commission share granted to the invited friend.
        agenda: Referral program/scenario identifier.
\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call(
        "POST", "/users/referral/links-add", body=_clean({"friendShare": friend_share, "agenda": agenda})
    )


@mcp.tool(structured_output=False)
def nobitex_get_referral_status() -> Any:
    """Get the user's referrer status.\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("POST", "/users/referral/referral-status", body={})


@mcp.tool(structured_output=False)
def nobitex_set_referrer(referrer_code: str) -> Any:
    """Register a referrer code for the user.\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("POST", "/users/referral/set-referrer", body={"referrerCode": referrer_code})


# ===========================================================================
# Authentication
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_login(
    username: str,
    password: str | None = None,
    captcha: str = "api",
    remember: Literal["yes"] | None = None,
    mfa_token: str | None = None,
    device: str | None = None,
    otp: str | None = None,
) -> Any:
    """Log in and obtain a user token (handles MFA second step).

    Args:
        username: Username/email.
        password: Password (first step).
        captcha: Captcha value; "api" for bots.
        remember: "yes" to issue a persistent token.
        mfa_token: Temporary token from the first step (MFA step).
        device: Device id from the first step (MFA step).
        otp: OTP for MFA methods 3/4.
    """
    if mfa_token and device:
        body = _clean(
            {"username": username, "mfaToken": mfa_token, "device": device, "otp": otp, "remember": remember}
        )
    else:
        if not password:
            raise ToolError("password is required for the first login step")
        body = _clean({"username": username, "password": password, "captcha": captcha, "remember": remember})
    return _call("POST", "/v2/auth/login", body=body, auth=False)


@mcp.tool(structured_output=False)
def nobitex_resend_login_otp(username: str, mfa_token: str, device: str) -> Any:
    """Resend the MFA OTP for a pending login.

    Args:
        username: Username/email.
        mfa_token: Temporary token from the first step.
        device: Device id from the first step.
    """
    return _call(
        "POST",
        "/v2/auth/login/otp",
        body={"username": username, "mfaToken": mfa_token, "device": device},
        auth=False,
    )


@mcp.tool(structured_output=False)
def nobitex_legacy_login(
    username: str,
    password: str,
    captcha: str = "api",
    remember: Literal["yes"] | None = None,
) -> Any:
    """Log in through the legacy endpoint.

    Args:
        username: Username/email.
        password: Password.
        captcha: Captcha value; "api" for bots.
        remember: "yes" to issue a persistent token.
    """
    return _call(
        "POST",
        "/auth/login/",
        body=_clean({"username": username, "password": password, "captcha": captcha, "remember": remember}),
        auth=False,
    )


@mcp.tool(structured_output=False)
def nobitex_logout() -> Any:
    """Log out the current user token.\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("POST", "/auth/logout/", body={})


# ===========================================================================
# API keys
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_create_api_key(
    name: str,
    permissions: str,
    description: str | None = None,
    ip_whitelist: list[str] | None = None,
    expiration_date: str | None = None,
    totp: str | None = None,
) -> Any:
    """Create an API key. The private key is returned only once.

    Args:
        name: Key name.
        permissions: Comma-separated permissions: READ,TRADE,WITHDRAW,DEPOSIT,ADDRESS_BOOK,OTP,VIP_CREDIT.
        description: Optional description.
        ip_whitelist: Optional list of allowed IPv4/IPv6 addresses (max 15).
        expiration_date: Optional ISO-8601 expiry in the future.
        totp: TOTP two-factor code (required, sent as X-TOTP).
\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    body = _clean(
        {
            "name": name,
            "permissions": permissions,
            "description": description,
            "ipAddressesWhitelist": ip_whitelist,
            "expirationDate": expiration_date,
        }
    )
    return _call("POST", "/apikeys/create", body=body, totp=totp)


@mcp.tool(structured_output=False)
def nobitex_list_api_keys() -> Any:
    """List the user's API keys.\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("GET", "/apikeys/list")


@mcp.tool(structured_output=False)
def nobitex_delete_api_key(public_key: str, totp: str | None = None) -> Any:
    """Delete an API key.

    Args:
        public_key: Public key of the API key.
        totp: TOTP two-factor code (required, sent as X-TOTP).
\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    return _call("POST", f"/apikeys/delete/{_q(public_key)}", totp=totp)


@mcp.tool(structured_output=False)
def nobitex_update_api_key(
    public_key: str,
    totp: str | None = None,
    name: str | None = None,
    description: str | None = None,
    ip_whitelist: list[str] | None = None,
) -> Any:
    """Update an API key's name, description or IP whitelist.

    Args:
        public_key: Public key of the API key.
        totp: TOTP two-factor code (required, sent as X-TOTP).
        name: New name.
        description: New description.
        ip_whitelist: New IP whitelist (max 15).
\n\n    Requires a user token; Nobitex does not accept API-key auth for this endpoint.
    """
    body = _clean({"name": name, "description": description, "ipAddressesWhitelist": ip_whitelist})
    return _call("POST", f"/apikeys/update/{_q(public_key)}", body=body, totp=totp)


# ===========================================================================
# Portfolio / P&L
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_get_last_week_daily_profit(monthly: bool | None = None) -> Any:
    """Get last week's daily profit/loss.

    Args:
        monthly: Return the last 30 days instead of one week.
    """
    return _call("POST", "/users/portfolio/last-week-daily-profit", body=_clean({"monthly": monthly}))


@mcp.tool(structured_output=False)
def nobitex_get_last_week_daily_total_profit(monthly: bool | None = None) -> Any:
    """Get last week's daily total profit/loss.

    Args:
        monthly: Return the last 30 days instead of one week.
    """
    return _call(
        "POST", "/users/portfolio/last-week-daily-total-profit", body=_clean({"monthly": monthly})
    )


@mcp.tool(structured_output=False)
def nobitex_get_last_month_total_profit() -> Any:
    """Get last month's total profit/loss."""
    return _call("POST", "/users/portfolio/last-month-total-profit", body={})


# ===========================================================================
# Websocket helpers
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_get_websocket_token() -> Any:
    """Get a token for a private websocket connection."""
    return _call("GET", "/auth/ws/token/")


@mcp.tool(structured_output=False)
def nobitex_get_websocket_info() -> Any:
    """Describe the Nobitex websocket endpoint and available channels.

    MCP tools are request/response, so this returns connection details rather
    than streaming. Use the token tool for private channels.
    """
    client = get_client()
    host = "wss://ws.testnet.nobitex.ir" if client.settings.is_testnet else "wss://ws.nobitex.ir"
    return {
        "websocket_url": host,
        "connection_path": "/connection/websocket",
        "protocol": "Centrifugo",
        "public_channels": [
            "orderbook",
            "candle",
            "public-trades",
            "market-stats",
        ],
        "private_channels": ["private-orders", "private-trades"],
        "private_auth": "Call nobitex_get_websocket_token and pass the token to the private channel subscription.",
    }


# ===========================================================================
# Paper trading helpers (NOBITEX_DRY_RUN=true)
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_paper_reset() -> Any:
    """Reset paper-trading balances, orders, trades and positions.

    Only available when the server runs with NOBITEX_DRY_RUN=true.
    """
    client = get_client()
    if client.paper is None:
        raise ToolError("Paper mode is not enabled. Set NOBITEX_DRY_RUN=true.")
    client.reset_paper()
    return {
        "status": "ok",
        "paper": True,
        "balances": {currency: str(balance) for currency, balance in client.paper.spot.items()},
    }


@mcp.tool(structured_output=False)
def nobitex_paper_match_open_orders() -> Any:
    """Re-check open paper limit orders against the live order book and fill crossing ones.

    Only available when the server runs with NOBITEX_DRY_RUN=true.
    """
    client = get_client()
    if client.paper is None:
        raise ToolError("Paper mode is not enabled. Set NOBITEX_DRY_RUN=true.")
    filled = client.match_paper_orders()
    return {"status": "ok", "paper": True, "filled_orders": filled}


# ===========================================================================
# Generic escape hatch
# ===========================================================================


@mcp.tool(structured_output=False)
def nobitex_request(
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"],
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    auth: Literal["auto", "none", "token", "key"] = "auto",
    totp: str | None = None,
) -> Any:
    """Call any Nobitex API path with correct authentication and signing.

    Use this for documented endpoints that do not yet have a dedicated tool,
    for example /v2/otp/request, /users/wallets/convert, /credit/*,
    /market/orders/batch-add, /market/orders/cancel-batch, /users/preferences.

    Args:
        method: HTTP method.
        path: API path beginning with "/", e.g. "/v2/otp/request".
        params: Query parameters.
        body: JSON request body.
        auth: "auto" (use configured credentials), "none", "token" or "key".
        totp: Optional X-TOTP code.
    """
    if not path.startswith("/"):
        raise ToolError("path must start with '/'")
    auth_value: bool | str
    if auth == "none":
        auth_value = False
    elif auth == "auto":
        auth_value = True
    else:
        auth_value = auth
    return _call(method, path, params=params, body=body, auth=auth_value, totp=totp)


# ===========================================================================
# Entry point
# ===========================================================================


def main() -> None:
    settings = get_client().settings
    transport = settings.transport
    if transport == "streamable-http":
        mcp.run(transport="streamable-http", host=settings.host, port=settings.port)
    elif transport == "sse":
        mcp.run(transport="sse", host=settings.host, port=settings.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
