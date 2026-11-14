"""FastAPI application exposing the trading agent and market endpoints."""

from __future__ import annotations

import asyncio
import queue
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from nobitex_mcp import NobitexError

from . import nobitex
from .agent_factory import _BLOCKED_MCP_TOOLS, build_mcp_config
from .config import get_settings
from .schemas import (
    CancelRequest,
    ChatRequest,
    CronRequest,
    OrderRequest,
    ScheduleCreate,
    ScheduleUpdate,
    SessionResponse,
)
from .scheduler import Scheduler
from .sessions import SessionManager

settings = get_settings()
manager = SessionManager(settings)
scheduler = Scheduler(settings, manager)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    if settings.scheduler_enabled:
        scheduler.start()
    yield
    if settings.scheduler_enabled:
        scheduler.stop()
    manager.close_all()


app = FastAPI(
    title="Nobitex Trading Agent",
    version="0.1.0",
    description="OpenHands-powered trading assistant for the Nobitex exchange",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error(exc: Exception) -> HTTPException:
    detail: Any = str(exc)
    to_dict = getattr(exc, "to_dict", None)
    if callable(to_dict):
        try:
            detail = to_dict()
        except Exception:  # noqa: BLE001
            pass
    return HTTPException(status_code=400, detail=detail)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Nobitex Trading Agent", "docs": "/docs"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "llm": {
            "model": settings.llm_model,
            "configured": settings.has_llm_credentials,
        },
        "nobitex": nobitex.server_info(),
        "mcp": {
            "server": "nobitex",
            "path": str(settings.mcp_nobitex_path),
            "exists": (settings.mcp_nobitex_path / "src" / "nobitex_mcp").is_dir(),
            "blocked_tools": [] if settings.allow_withdrawals else list(_BLOCKED_MCP_TOOLS),
        },
        "agent": {
            "max_iterations": settings.agent_max_iterations,
            "allow_withdrawals": settings.allow_withdrawals,
        },
        "scheduler": {
            "enabled": settings.scheduler_enabled,
            "timezone": scheduler.timezone_name,
            "tasks": len(scheduler.list()),
        },
    }


@app.get("/api/config")
def config() -> dict[str, Any]:
    cfg = build_mcp_config(settings)
    return {
        "llm_model": settings.llm_model,
        "nobitex_env": settings.nobitex_env,
        "nobitex_base_url": settings.resolved_nobitex_base_url,
        "dry_run": settings.nobitex_dry_run,
        "read_only": settings.nobitex_read_only,
        "allow_withdrawals": settings.allow_withdrawals,
        "mcp_servers": {name: {"command": spec["command"], "args": spec["args"]} for name, spec in cfg.items()},
    }


# --------------------------------------------------------------------------
# Sessions & chat
# --------------------------------------------------------------------------


@app.post("/api/sessions", response_model=SessionResponse)
def create_session() -> SessionResponse:
    session = manager.create()
    return SessionResponse(session_id=session.id, created_at=session.created_at)


@app.get("/api/sessions")
def list_sessions() -> list[dict[str, Any]]:
    return [
        {"session_id": s.id, "status": s.status, "created_at": s.created_at, "events": len(s.history)}
        for s in manager.list()
    ]


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    session = manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return {
        "session_id": session.id,
        "status": session.status,
        "created_at": session.created_at,
        "history": session.history,
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    session = manager.get_or_create(request.session_id)
    try:
        session.send(request.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"session_id": session.id, "status": "running"}


@app.websocket("/ws/chat/{session_id}")
async def chat_socket(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session = manager.get(session_id)
    if session is None:
        await websocket.send_json({"type": "Error", "error": "Unknown session"})
        await websocket.close()
        return

    await websocket.send_json({"type": "Ready", "session_id": session_id})
    try:
        while True:
            data = await websocket.receive_json()
            message = str((data or {}).get("message", "")).strip()
            if not message:
                continue
            try:
                session.send(message)
            except RuntimeError as exc:
                await websocket.send_json({"type": "Error", "error": str(exc)})
                continue

            while True:
                try:
                    event = await asyncio.to_thread(session.queue.get, True, 0.5)
                except queue.Empty:
                    continue
                await websocket.send_json(event)
                if event.get("type") == "Done":
                    break
    except WebSocketDisconnect:
        return


# --------------------------------------------------------------------------
# Market data & analysis
# --------------------------------------------------------------------------


@app.get("/api/market/stats")
def market_stats(
    src: str = Query("btc"), dst: str = Query("usdt")
) -> dict[str, Any]:
    try:
        payload = nobitex.fetch_market_stats(src, dst)
        return {"raw": payload, "markets": nobitex.normalize_stats(payload)}
    except NobitexError as exc:
        raise _error(exc) from exc


@app.get("/api/markets")
def markets() -> dict[str, Any]:
    try:
        items = nobitex.fetch_all_markets()
    except NobitexError as exc:
        raise _error(exc) from exc

    quote_priority = {"USDT": 0, "IRT": 1, "USD": 2, "EUR": 3, "BTC": 4, "ETH": 5}

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        symbol = item["symbol"]
        for quote, rank in quote_priority.items():
            if symbol.endswith(quote):
                return rank, symbol
        return len(quote_priority), symbol

    items = [item for item in items if item["price"]]
    items.sort(key=sort_key)
    return {"markets": items}


@app.get("/api/market/orderbook/{symbol}")
def market_orderbook(symbol: str) -> dict[str, Any]:
    try:
        return nobitex.fetch_orderbook(symbol)
    except NobitexError as exc:
        raise _error(exc) from exc


@app.get("/api/market/ohlc/{symbol}")
def market_ohlc(
    symbol: str,
    resolution: str = Query("60"),
    countback: int = Query(200, ge=30, le=500),
) -> dict[str, Any]:
    try:
        candles = nobitex.fetch_candles(symbol, resolution=resolution, countback=countback)
        return {"symbol": symbol.upper(), "resolution": resolution, "candles": candles}
    except (NobitexError, ValueError) as exc:
        raise _error(exc) from exc


@app.get("/api/analysis/{symbol}")
def analysis(
    symbol: str,
    resolution: str = Query("60"),
    countback: int = Query(200, ge=30, le=500),
) -> dict[str, Any]:
    try:
        return nobitex.analyze_symbol(symbol, resolution=resolution, countback=countback)
    except (NobitexError, ValueError) as exc:
        raise _error(exc) from exc


@app.get("/api/opportunities")
def opportunities(
    symbols: str | None = Query(None, description="Comma-separated symbols"),
    resolution: str = Query("60"),
) -> dict[str, Any]:
    parsed = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None
    try:
        return nobitex.scan_symbols(parsed, resolution=resolution)
    except (NobitexError, ValueError) as exc:
        raise _error(exc) from exc


# --------------------------------------------------------------------------
# Trading
# --------------------------------------------------------------------------


@app.get("/api/orders")
def orders() -> dict[str, Any]:
    try:
        return nobitex.list_orders()
    except NobitexError as exc:
        raise _error(exc) from exc


@app.post("/api/orders")
def place_order(request: OrderRequest) -> dict[str, Any]:
    if request.execution in ("limit", "stop_limit") and not request.price:
        raise HTTPException(status_code=422, detail="price is required for limit orders")
    try:
        return nobitex.place_spot_order(
            symbol=request.symbol,
            side=request.side,
            amount=request.amount,
            execution=request.execution,
            price=request.price,
        )
    except NobitexError as exc:
        raise _error(exc) from exc


@app.post("/api/orders/cancel")
def cancel_order(request: CancelRequest) -> dict[str, Any]:
    try:
        return nobitex.cancel_order(request.order_id)
    except NobitexError as exc:
        raise _error(exc) from exc


@app.get("/api/schedules")
def list_schedules() -> dict[str, Any]:
    return {
        "timezone": scheduler.timezone_name,
        "tasks": scheduler.list(),
    }


@app.post("/api/schedules")
def create_schedule(request: ScheduleCreate) -> dict[str, Any]:
    try:
        return scheduler.create(
            prompt=request.prompt,
            cron=request.cron,
            name=request.name,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.patch("/api/schedules/{task_id}")
def update_schedule(task_id: str, request: ScheduleUpdate) -> dict[str, Any]:
    try:
        task = scheduler.update(task_id, **request.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return task


@app.delete("/api/schedules/{task_id}")
def delete_schedule(task_id: str) -> dict[str, Any]:
    if not scheduler.delete(task_id):
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return {"deleted": task_id}


@app.post("/api/schedules/{task_id}/run")
def run_schedule(task_id: str) -> dict[str, Any]:
    if scheduler.get(task_id) is None:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    started = scheduler.run_now(task_id)
    return {"task_id": task_id, "started": started}


@app.post("/api/schedules/validate")
def validate_schedule(request: CronRequest) -> dict[str, Any]:
    try:
        return {
            "valid": True,
            "timezone": scheduler.timezone_name,
            "next_runs": scheduler.preview(request.cron, 3),
        }
    except ValueError as exc:
        return {"valid": False, "error": str(exc)}


@app.get("/api/wallets")
def wallets() -> dict[str, Any]:
    try:
        return nobitex.get_wallets()
    except NobitexError as exc:
        raise _error(exc) from exc
