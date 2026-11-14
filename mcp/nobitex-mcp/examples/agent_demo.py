#!/usr/bin/env python3
"""End-to-end agent demo for the Nobitex MCP server.

Modes:
  paper     (default) run a small trading loop against live prices with
            in-memory paper balances. No real orders are sent.
  readonly  connect with real credentials and verify read access plus the
            read-only guard. Requires NOBITEX_PUBLIC_KEY/NOBITEX_PRIVATE_KEY
            or NOBITEX_TOKEN.

Usage:
  python examples/agent_demo.py
  python examples/agent_demo.py --mode readonly
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]


def _summary(name: str, data: dict) -> str:
    if name == "nobitex_server_info":
        return (
            f"env={data.get('environment')} auth={data.get('auth_mode')} "
            f"creds={data.get('has_credentials')} read_only={data.get('read_only')} "
            f"dry_run={data.get('dry_run')}"
        )
    if name == "nobitex_get_profile":
        profile = data.get("profile") or {}
        return f"level={profile.get('level')}"
    if name in ("nobitex_get_wallets", "nobitex_get_selected_wallets"):
        wallets = data.get("wallets") or []
        return f"wallets={len(wallets)} currencies={[w.get('currency') for w in wallets]}"
    if name == "nobitex_get_orderbook":
        return (
            f"bid={data['bids'][0][0]} ask={data['asks'][0][0]} "
            f"levels={len(data['bids'])}x{len(data['asks'])}"
        )
    if name == "nobitex_get_market_stats":
        stats = data.get("stats") or {}
        key = next(iter(stats), None)
        return f"market={key} latest={stats.get(key, {}).get('latest')}"
    if name == "nobitex_list_orders":
        return f"orders={len(data.get('orders') or [])}"
    if name == "nobitex_list_positions":
        return f"positions={len(data.get('positions') or [])}"
    if name == "nobitex_get_transactions_history":
        return f"transactions={len(data.get('transactions') or [])}"
    if name == "nobitex_list_user_trades":
        return f"trades={len(data.get('trades') or [])}"
    return f"status={data.get('status')}"


class Agent:
    def __init__(self, session: ClientSession) -> None:
        self.session = session

    async def call(self, name: str, **args):
        result = await self.session.call_tool(name, args)
        text = result.content[0].text if result.content else ""
        if result.is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def try_call(self, name: str, **args):
        try:
            return await self.call(name, **args), None
        except Exception as exc:  # noqa: BLE001 - demo reports the error
            return None, str(exc)


async def run(mode: str) -> int:
    env = dict(os.environ)
    env["NOBITEX_ENV"] = "mainnet"
    if mode == "paper":
        env.update(
            {
                "NOBITEX_DRY_RUN": "true",
                "NOBITEX_PAPER_BALANCES": '{"usdt":"10000","btc":"0"}',
                "NOBITEX_PAPER_FEE_RATE": "0.001",
            }
        )
    else:
        env["NOBITEX_READ_ONLY"] = "true"

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nobitex_mcp.server"],
        env=env,
        cwd=str(ROOT),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            agent = Agent(session)

            print(f"=== mode: {mode} ===")
            info = await agent.call("nobitex_server_info")
            print(f"server_info: {_summary('nobitex_server_info', info)}")

            book = await agent.call("nobitex_get_orderbook", symbol="BTCUSDT")
            print(f"orderbook:   {_summary('nobitex_get_orderbook', book)}")
            best_bid = float(book["bids"][0][0])
            best_ask = float(book["asks"][0][0])

            stats = await agent.call(
                "nobitex_get_market_stats", src_currency="btc", dst_currency="usdt"
            )
            print(f"market:      {_summary('nobitex_get_market_stats', stats)}")

            wallets = await agent.call("nobitex_get_wallets")
            print(f"wallets:     {_summary('nobitex_get_wallets', wallets)}")

            if mode == "readonly":
                profile = await agent.call("nobitex_get_profile")
                print(f"profile:     {_summary('nobitex_get_profile', profile)}")
                for name, args in [
                    ("nobitex_list_orders", {"status": "open", "page_size": 5}),
                    ("nobitex_list_positions", {"status": "active"}),
                    ("nobitex_get_transactions_history", {"page_size": 3}),
                ]:
                    data, error = await agent.try_call(name, **args)
                    print(
                        f"{name:38} "
                        f"{'ERROR ' + error[:80] if error else _summary(name, data)}"
                    )

                _, error = await agent.try_call(
                    "nobitex_place_spot_order",
                    type="buy",
                    src_currency="btc",
                    dst_currency="usdt",
                    amount="0.001",
                )
                print(
                    f"trade guard: {'BLOCKED -> ' + error[:100] if error else 'NOT BLOCKED'}"
                )
                return 0

            # Paper trading loop.
            market_buy = await agent.call(
                "nobitex_place_spot_order",
                type="buy",
                src_currency="btc",
                dst_currency="usdt",
                amount="0.001",
                execution="market",
            )
            print(
                f"market buy:  status={market_buy['order']['status']} "
                f"avg={market_buy['order']['averagePrice']} fee={market_buy['order']['fee']}"
            )

            sell_price = f"{best_ask * 1.015:.0f}"
            limit_sell = await agent.call(
                "nobitex_place_spot_order",
                type="sell",
                src_currency="btc",
                dst_currency="usdt",
                amount="0.001",
                execution="limit",
                price=sell_price,
            )
            print(
                f"limit sell:  id={limit_sell['order']['id']} "
                f"status={limit_sell['order']['status']} price={limit_sell['order']['price']}"
            )

            buy_price = f"{best_bid * 0.985:.0f}"
            limit_buy = await agent.call(
                "nobitex_place_spot_order",
                type="buy",
                src_currency="btc",
                dst_currency="usdt",
                amount="0.001",
                execution="limit",
                price=buy_price,
            )
            print(
                f"limit buy:   id={limit_buy['order']['id']} "
                f"status={limit_buy['order']['status']} price={limit_buy['order']['price']}"
            )

            open_orders = await agent.call("nobitex_list_orders", status="open")
            print(f"open orders: {_summary('nobitex_list_orders', open_orders)}")

            for order in (limit_sell["order"], limit_buy["order"]):
                canceled = await agent.call("nobitex_cancel_order", order=order["id"])
                print(
                    f"cancel {order['id']}:   status={canceled['status']} "
                    f"updated={canceled['updatedStatus']}"
                )

            trades = await agent.call("nobitex_list_user_trades")
            print(f"trades:      {_summary('nobitex_list_user_trades', trades)}")

            wallets = await agent.call("nobitex_get_wallets")
            print(f"wallets:     {_summary('nobitex_get_wallets', wallets)}")

            reset = await agent.call("nobitex_paper_reset")
            print(f"reset:       balances={reset['balances']}")
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["paper", "readonly"], default="paper")
    args = parser.parse_args()
    return asyncio.run(run(args.mode))


if __name__ == "__main__":
    raise SystemExit(main())
