"""In-memory paper-trading broker used when NOBITEX_DRY_RUN=true.

The broker intercepts authenticated/trading paths and returns responses shaped
like the real Nobitex API, while public market-data paths still go to the live
API so paper fills use real prices. No orders or withdrawals ever leave the
machine.

This exists because the Nobitex testnet is currently disabled (per Nobitex
support), so it is the safest way to exercise a trading agent end to end.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

_PUBLIC_PREFIXES = (
    "/v3/orderbook",
    "/v2/depth",
    "/v2/trades",
    "/market/stats",
    "/market/udf/history",
    "/v2/options",
    "/margin/markets/list",
    "/liquidity-pools/list",
)

_DEFAULT_BALANCES = {"usdt": "10000", "rls": "100000000", "btc": "0.5", "eth": "5"}


class PaperError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _dec(value: Any, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise PaperError("InvalidAmount", f"{field_name} must be a decimal string") from exc
    if result <= 0:
        raise PaperError("InvalidAmount", f"{field_name} must be positive")
    return result


def _s(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PaperOrder:
    id: int
    type: str
    execution: str
    src_currency: str
    dst_currency: str
    amount: Decimal
    price: Decimal | None
    status: str = "Active"
    matched_amount: Decimal = Decimal("0")
    average_price: Decimal | None = None
    fee: Decimal = Decimal("0")
    client_order_id: str | None = None
    stop_price: Decimal | None = None
    created_at: str = field(default_factory=_now_iso)

    @property
    def market(self) -> str:
        return f"{self.src_currency.upper()}-{self.dst_currency.upper()}"

    def to_dict(self) -> dict[str, Any]:
        total_order = None
        if self.price is not None:
            total_order = self.price * self.amount
        elif self.average_price is not None:
            total_order = self.average_price * self.amount
        total_price = (self.average_price or Decimal("0")) * self.matched_amount
        return {
            "id": self.id,
            "type": self.type,
            "execution": self.execution,
            "tradeType": "Spot",
            "market": self.market,
            "srcCurrency": self.src_currency,
            "dstCurrency": self.dst_currency,
            "price": _s(self.price) if self.price is not None else "market",
            "amount": _s(self.amount),
            "totalPrice": _s(total_price),
            "totalOrderPrice": _s(total_order) if total_order is not None else "0",
            "matchedAmount": _s(self.matched_amount),
            "unmatchedAmount": _s(self.amount - self.matched_amount),
            "status": self.status,
            "partial": Decimal("0") < self.matched_amount < self.amount,
            "fee": _s(self.fee),
            "created_at": self.created_at,
            "averagePrice": _s(self.average_price) if self.average_price is not None else "0",
            "clientOrderId": self.client_order_id,
            "param1": _s(self.stop_price) if self.stop_price is not None else None,
            "paper": True,
        }


@dataclass
class PaperPosition:
    id: int
    type: str
    market: str
    src_currency: str
    dst_currency: str
    amount: Decimal
    entry_price: Decimal
    leverage: Decimal
    collateral: Decimal
    status: str = "active"
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "market": self.market,
            "srcCurrency": self.src_currency,
            "dstCurrency": self.dst_currency,
            "amount": _s(self.amount),
            "entryPrice": _s(self.entry_price),
            "leverage": _s(self.leverage),
            "collateral": _s(self.collateral),
            "status": self.status,
            "created_at": self.created_at,
            "paper": True,
        }


class PaperBroker:
    def __init__(self) -> None:
        self.spot: dict[str, Decimal] = self._load_balances()
        self.margin: dict[str, Decimal] = {}
        self.orders: dict[int, PaperOrder] = {}
        self.trades: list[dict[str, Any]] = []
        self.positions: dict[int, PaperPosition] = {}
        self.fee_rate = Decimal(os.getenv("NOBITEX_PAPER_FEE_RATE") or "0.001")
        self._next_order_id = 1
        self._next_trade_id = 1
        self._next_position_id = 1
        self.market_price: Callable[[str, str], Decimal | None] | None = None

    @staticmethod
    def _load_balances() -> dict[str, Decimal]:
        raw = os.getenv("NOBITEX_PAPER_BALANCES")
        data = _DEFAULT_BALANCES
        if raw:
            try:
                data = json.loads(raw)
            except ValueError as exc:
                raise PaperError(
                    "InvalidPaperBalances", "NOBITEX_PAPER_BALANCES must be valid JSON"
                ) from exc
        return {str(k).lower(): Decimal(str(v)) for k, v in data.items()}

    # ------------------------------------------------------------------ entry
    def handle(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any] | None,
        body: Mapping[str, Any] | None,
        market_price: Callable[[str, str], Decimal | None] | None = None,
    ) -> Any | None:
        """Return a simulated response, or None to let the request hit the API."""
        self.market_price = market_price or self.market_price
        body = dict(body or {})
        params = dict(params or {})

        if path.startswith(_PUBLIC_PREFIXES):
            return None

        handler = self._route(method, path)
        if handler is None:
            raise PaperError(
                "PaperModeUnsupported",
                f"{method} {path} is not simulated in paper mode. Use a read-only "
                "public endpoint or disable NOBITEX_DRY_RUN.",
            )
        return handler(params, body)

    def _route(self, method: str, path: str):
        routes: dict[tuple[str, str], Callable[[dict, dict], Any]] = {
            ("GET", "/users/profile"): self._profile,
            ("POST", "/users/wallets/list"): self._wallets,
            ("POST", "/v2/wallets"): self._wallets,
            ("POST", "/users/wallets/balance"): self._balance,
            ("POST", "/users/limitations"): self._limitations,
            ("GET", "/users/wallets/transactions/list"): self._empty_transactions,
            ("GET", "/users/transactions-history"): self._empty_transactions,
            ("GET", "/users/wallets/deposits/list"): self._empty_transactions,
            ("GET", "/users/wallets/withdraws/list"): self._empty_transactions,
            ("POST", "/users/portfolio/last-week-daily-profit"): self._profit,
            ("POST", "/users/portfolio/last-week-daily-total-profit"): self._profit,
            ("POST", "/users/portfolio/last-month-total-profit"): self._profit,
            ("POST", "/market/orders/add"): self._place_order,
            ("POST", "/market/orders/status"): self._order_status,
            ("GET", "/market/orders/list"): self._list_orders,
            ("POST", "/market/orders/update-status"): self._cancel_order,
            ("POST", "/market/orders/cancel-old"): self._cancel_old,
            ("GET", "/market/trades/list"): self._list_trades,
            ("POST", "/wallets/transfer"): self._transfer,
            ("POST", "/margin/orders/add"): self._place_margin_order,
            ("GET", "/positions/list"): self._list_positions,
            ("GET", "/margin/v2/delegation-limit"): self._delegation_limit,
        }
        if path.startswith("/positions/") and path.endswith("/status"):
            return lambda params, body: self._position_status(path, params, body)
        if path.startswith("/positions/") and path.endswith("/close"):
            return lambda params, body: self._close_position(path, params, body)
        if path.startswith("/positions/") and path.endswith("/edit-collateral"):
            return lambda params, body: self._edit_collateral(path, params, body)
        return routes.get((method, path))

    # --------------------------------------------------------------- account
    def _profile(self, params, body):
        return {
            "status": "ok",
            "profile": {
                "email": "paper@example.invalid",
                "firstName": "Paper",
                "lastName": "Trader",
                "level": 2,
                "paper": True,
            },
            "paper": True,
        }

    def _wallets(self, params, body):
        wallets = [
            {
                "currency": currency,
                "balance": _s(balance),
                "activeBalance": _s(balance),
                "blockedBalance": "0",
            }
            for currency, balance in sorted(self.spot.items())
        ]
        return {"status": "ok", "wallets": wallets, "paper": True}

    def _balance(self, params, body):
        currency = str(body.get("currency") or "").lower()
        if not currency:
            raise PaperError("InvalidCurrency", "currency is required")
        return {
            "status": "ok",
            "currency": currency,
            "balance": _s(self.spot.get(currency, Decimal("0"))),
            "paper": True,
        }

    def _limitations(self, params, body):
        return {"status": "ok", "limitations": {}, "paper": True}

    def _empty_transactions(self, params, body):
        return {"status": "ok", "transactions": [], "hasNext": False, "paper": True}

    def _profit(self, params, body):
        return {"status": "ok", "profit": {"total": "0", "daily": []}, "paper": True}

    # ----------------------------------------------------------------- orders
    def _place_order(self, params, body):
        side = body.get("type")
        if side not in ("buy", "sell"):
            raise PaperError("InvalidOrder", "type must be 'buy' or 'sell'")
        execution = str(body.get("execution") or "limit").lower()
        if execution not in ("limit", "market", "stop_limit", "stop_market"):
            raise PaperError("InvalidOrder", "unsupported execution type")
        src = str(body.get("srcCurrency") or "").lower()
        dst = str(body.get("dstCurrency") or "").lower()
        if not src or not dst:
            raise PaperError("InvalidOrder", "srcCurrency and dstCurrency are required")
        amount = _dec(body.get("amount"), "amount")
        price = Decimal(str(body["price"])) if body.get("price") is not None else None
        stop_price = Decimal(str(body["stopPrice"])) if body.get("stopPrice") is not None else None
        if execution in ("limit", "stop_limit") and price is None:
            raise PaperError("InvalidOrder", f"price is required for {execution} orders")
        if execution in ("stop_limit", "stop_market") and stop_price is None:
            raise PaperError("InvalidOrder", "stopPrice is required for stop orders")

        order = PaperOrder(
            id=self._next_order_id,
            type=side,
            execution={
                "limit": "Limit",
                "market": "Market",
                "stop_limit": "StopLimit",
                "stop_market": "StopMarket",
            }[execution],
            src_currency=src,
            dst_currency=dst,
            amount=amount,
            price=price,
            client_order_id=body.get("clientOrderId"),
            stop_price=stop_price,
        )
        self._next_order_id += 1
        self.orders[order.id] = order

        if execution in ("limit", "market"):
            try:
                self._try_fill(order)
            except PaperError:
                self.orders.pop(order.id, None)
                raise
        return {"status": "ok", "order": order.to_dict(), "paper": True}

    def _try_fill(self, order: PaperOrder) -> None:
        if order.status not in ("Open", "Active"):
            return
        symbol = f"{order.src_currency.upper()}{order.dst_currency.upper()}"
        side = "ask" if order.type == "buy" else "bid"
        market = self.market_price(symbol, side) if self.market_price else None
        if market is None:
            if order.execution == "Market":
                raise PaperError(
                    "PaperNoMarketData",
                    f"No market data for {symbol}; market orders need a live orderbook",
                )
            return

        if order.execution == "Market":
            fill_price = market
        elif order.type == "buy" and order.price is not None and market <= order.price:
            fill_price = market
        elif order.type == "sell" and order.price is not None and market >= order.price:
            fill_price = market
        else:
            return

        self._execute_fill(order, order.amount, fill_price)

    def _execute_fill(self, order: PaperOrder, amount: Decimal, price: Decimal) -> None:
        gross = amount * price
        fee = gross * self.fee_rate
        if order.type == "buy":
            cost = gross + fee
            if self.spot.get(order.dst_currency, Decimal("0")) < cost:
                raise PaperError(
                    "InsufficientBalance",
                    f"insufficient {order.dst_currency} balance for this paper order",
                )
            self.spot[order.dst_currency] = self.spot.get(order.dst_currency, Decimal("0")) - cost
            self.spot[order.src_currency] = self.spot.get(order.src_currency, Decimal("0")) + amount
        else:
            if self.spot.get(order.src_currency, Decimal("0")) < amount:
                raise PaperError(
                    "InsufficientBalance",
                    f"insufficient {order.src_currency} balance for this paper order",
                )
            self.spot[order.src_currency] = self.spot.get(order.src_currency, Decimal("0")) - amount
            self.spot[order.dst_currency] = self.spot.get(order.dst_currency, Decimal("0")) + (
                gross - fee
            )

        order.matched_amount += amount
        order.average_price = price
        order.fee += fee
        order.status = "Done" if order.matched_amount >= order.amount else "Active"
        self.trades.append(
            {
                "id": self._next_trade_id,
                "orderId": order.id,
                "srcCurrency": order.src_currency,
                "dstCurrency": order.dst_currency,
                "market": order.market,
                "timestamp": _now_iso(),
                "type": order.type,
                "price": _s(price),
                "amount": _s(amount),
                "total": _s(gross),
                "fee": _s(fee),
                "paper": True,
            }
        )
        self._next_trade_id += 1

    def _find_order(self, params, body) -> PaperOrder:
        order_id = body.get("id") if body else None
        if order_id is None and body:
            order_id = body.get("order")
        client_id = body.get("clientOrderId") if body else None
        if order_id is not None:
            order = self.orders.get(int(order_id))
        elif client_id is not None:
            order = next(
                (o for o in self.orders.values() if o.client_order_id == client_id), None
            )
        else:
            order = None
        if order is None:
            raise PaperError("OrderNotFound", "order not found in paper book")
        return order

    def _order_status(self, params, body):
        order = self._find_order(params, body)
        return {"status": "ok", "order": order.to_dict(), "paper": True}

    def _list_orders(self, params, body):
        orders = list(self.orders.values())
        status = params.get("status")
        if status and status != "all":
            if status == "open":
                orders = [o for o in orders if o.status in ("Open", "Active", "New")]
            elif status == "done":
                orders = [o for o in orders if o.matched_amount > 0]
            elif status == "close":
                orders = [o for o in orders if o.status in ("Done", "Canceled")]
        return {
            "status": "ok",
            "orders": [o.to_dict() for o in reversed(orders)],
            "hasNext": False,
            "paper": True,
        }

    def _cancel_order(self, params, body):
        order = self._find_order(params, body)
        if order.status in ("Done", "Canceled"):
            return {
                "status": "failed",
                "updatedStatus": order.status,
                "order": order.to_dict(),
                "paper": True,
            }
        order.status = "Canceled"
        return {
            "status": "ok",
            "updatedStatus": "Canceled",
            "order": order.to_dict(),
            "paper": True,
        }

    def _cancel_old(self, params, body):
        hours = float(body.get("hours") or 0)
        cutoff = time.time() - hours * 3600
        canceled = 0
        for order in self.orders.values():
            if order.status in ("Open", "Active") and _parse_iso(order.created_at) <= cutoff:
                order.status = "Canceled"
                canceled += 1
        return {"status": "ok", "canceled": canceled, "paper": True}

    def _list_trades(self, params, body):
        return {
            "status": "ok",
            "trades": list(reversed(self.trades)),
            "hasNext": False,
            "paper": True,
        }

    # --------------------------------------------------------------- transfers
    def _transfer(self, params, body):
        currency = str(body.get("currency") or "").lower()
        amount = _dec(body.get("amount"), "amount")
        src = body.get("src")
        dst = body.get("dst")
        if src == dst or {src, dst} != {"spot", "margin"}:
            raise PaperError("InvalidTransfer", "src and dst must be 'spot' and 'margin'")
        source = self.spot if src == "spot" else self.margin
        target = self.spot if dst == "spot" else self.margin
        if source.get(currency, Decimal("0")) < amount:
            raise PaperError("InsufficientBalance", f"insufficient {currency} in {src}")
        source[currency] = source.get(currency, Decimal("0")) - amount
        target[currency] = target.get(currency, Decimal("0")) + amount
        return {"status": "ok", "paper": True}

    # ----------------------------------------------------------------- margin
    def _place_margin_order(self, params, body):
        side = body.get("type")
        if side not in ("buy", "sell"):
            raise PaperError("InvalidOrder", "type must be 'buy' or 'sell'")
        src = str(body.get("srcCurrency") or "").lower()
        dst = str(body.get("dstCurrency") or "").lower()
        amount = _dec(body.get("amount"), "amount")
        leverage = Decimal(str(body.get("leverage") or "1"))
        execution = str(body.get("execution") or "limit").lower()
        price = Decimal(str(body["price"])) if body.get("price") is not None else None
        if execution == "market":
            market = (
                self.market_price(f"{src.upper()}{dst.upper()}", "ask" if side == "buy" else "bid")
                if self.market_price
                else None
            )
            if market is None:
                raise PaperError("PaperNoMarketData", "no market data for margin order")
            price = market
        if price is None:
            raise PaperError("InvalidOrder", "price is required for limit margin orders")
        position = PaperPosition(
            id=self._next_position_id,
            type=side,
            market=f"{src.upper()}-{dst.upper()}",
            src_currency=src,
            dst_currency=dst,
            amount=amount,
            entry_price=price,
            leverage=leverage,
            collateral=amount * price / leverage,
        )
        self._next_position_id += 1
        self.positions[position.id] = position
        return {"status": "ok", "position": position.to_dict(), "paper": True}

    def _list_positions(self, params, body):
        status = params.get("status")
        positions = list(self.positions.values())
        if status:
            positions = [p for p in positions if p.status == status]
        return {"status": "ok", "positions": [p.to_dict() for p in positions], "paper": True}

    def _position_id(self, path: str) -> int:
        parts = path.strip("/").split("/")
        try:
            return int(parts[1])
        except (IndexError, ValueError) as exc:
            raise PaperError("PositionNotFound", "invalid position id") from exc

    def _get_position(self, path: str) -> PaperPosition:
        position = self.positions.get(self._position_id(path))
        if position is None:
            raise PaperError("PositionNotFound", "position not found in paper book")
        return position

    def _position_status(self, path, params, body):
        return {"status": "ok", "position": self._get_position(path).to_dict(), "paper": True}

    def _close_position(self, path, params, body):
        position = self._get_position(path)
        position.status = "closed"
        return {"status": "ok", "position": position.to_dict(), "paper": True}

    def _edit_collateral(self, path, params, body):
        position = self._get_position(path)
        position.collateral = _dec(body.get("collateral"), "collateral")
        return {"status": "ok", "position": position.to_dict(), "paper": True}

    def _delegation_limit(self, params, body):
        return {"status": "ok", "limit": "1000000000", "paper": True}

    # ------------------------------------------------------------------ utils
    def reset(self) -> None:
        self.spot = self._load_balances()
        self.margin = {}
        self.orders = {}
        self.trades = []
        self.positions = {}
        self._next_order_id = 1
        self._next_trade_id = 1
        self._next_position_id = 1

    def match_open_orders(self) -> int:
        filled = 0
        for order in list(self.orders.values()):
            before = order.matched_amount
            self._try_fill(order)
            if order.matched_amount > before:
                filled += 1
        return filled


def _parse_iso(value: str) -> float:
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0
