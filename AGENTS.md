# AGENTS.md

Repository-specific notes for AI agents working on this project.

## What this is

A Nobitex crypto trading assistant: FastAPI backend using the OpenHands Agent SDK + a
vendored `nobitex-mcp` server, and an Angular 20 dashboard.

## Layout

- `backend/app/` — FastAPI app. `agent_factory.py` builds the agent and the default MCP
  config; `technical.py` is the indicator engine; `tools.py` defines `AnalyzeMarketTool`;
  `scheduler.py` is the SQLite cron scheduler and run-history store; `scheduler_mcp.py`
  exposes it to the agent as an MCP server.
- `backend/tests/` — pytest suite (technical, API, agent config, scheduler).
- `frontend/src/app/` — standalone Angular components + services. `schedule-runs/` renders
  saved scheduler transcripts; `services/chat-events.ts` maps SDK events to chat messages
  for both live chat and run history.
- `mcp/nobitex-mcp/` — vendored Nobitex MCP server (do not edit unless updating the vendor).

## Commands

```bash
# backend
cd backend && source .venv/bin/activate && pytest
uvicorn app.main:app --reload --port 8011

# frontend
cd frontend && npm start        # ng serve + proxy.conf.json
npx ng build                    # production build
```

Port **8011** is the project default because 8000 is often occupied by Agent Canvas. The
frontend proxy (`frontend/proxy.conf.json`) must match the backend port.

## Gotchas

- The MCP server is launched with `sys.executable`, `cwd=<repo>/mcp/nobitex-mcp`, and
  `PYTHONPATH=<repo>/mcp/nobitex-mcp/src`. If you move the vendor directory, update
  `Settings.mcp_nobitex_path`.
- `_filter_regex` blocks fund-moving tools with `nobitex_(?:...)(?:_|$)`. A `\b` boundary
  does **not** work because `_` is a word character.
- `NOBITEX_DRY_RUN=true` and `ALLOW_WITHDRAWALS=false` are deliberate defaults. Do not flip
  them in tests or examples.
- `Settings` is cached with `lru_cache`; tests that need different env values should
  instantiate `Settings(...)` directly or clear `get_settings.cache_clear()`.
- The SDK's `Agent` accepts `mcp_config` as a dict of server name → config; MCP tools are
  filtered by `filter_tools_regex` after discovery.
- `backend/workspace/` is agent scratch space and is gitignored.
- `backend/scheduler.db` is gitignored runtime state. Scheduler tests build their own
  `Scheduler` with `Settings(scheduler_db_path=tmp_path/...)`; never point tests at the
  real DB.
- The scheduler MCP server is a separate process that calls the FastAPI app over HTTP
  (`SCHEDULER_API_URL`, default `http://127.0.0.1:8011`). If you change the backend port,
  update that env var or the agent's scheduling tools will fail.
- Cron expressions are evaluated in `SCHEDULER_TIMEZONE` (default `Asia/Tehran`). Runs
  missed while the API was down are skipped on startup, and stale `running` statuses are
  marked `interrupted`.
- Every scheduler execution is stored in `scheduled_runs` with its full serialized event
  list (newest 50 per task). Deleting a task deletes its runs. The UI reads
  `GET /api/runs` and `GET /api/runs/{id}`; keep those payloads JSON-safe because they are
  persisted before being served.
- `candle-chart.component.ts` keeps its view window in `range` (absolute candle indices)
  and optional `yDomain` for box-select zoom. Pointer drags map client coordinates through
  the SVG viewBox, so keep `preserveAspectRatio="none"` and the `width`/`height` constants
  in sync when changing the chart layout.
- `tool-view.component.ts` renders tool-specific views (order book, analysis, wallets,
  stats, margin markets, orders, trades). Margin market results are parsed from structured
  `data.markets` when present and fall back to the line-based text format emitted by the
  MCP server; keep both paths working when changing that view.
- Schedule deletion is confirmed in an in-app modal before `DELETE /api/schedules/{id}` is
  called; do not replace it with `window.confirm`.
- Scheduled prompts run unattended with the same safety flags as chat; keep
  `NOBITEX_DRY_RUN=true` unless the operator explicitly opts in.
- `ActionEvent.thought` is a `Sequence[TextContent]`, not a string. Always run websocket
  payloads through `sessions._blocks_text` / `_json_safe`; a raw `send_json` raises
  `TypeError` and closes the chat socket.
- `PUT /api/settings` mutates the cached `Settings` object and writes `.env`. It clears
  `nobitex.get_client` so new calls use the new credentials. Tests must monkeypatch
  `runtime_settings.ENV_PATH` to a temp file so they never touch the real `.env`.
- The settings panel intentionally uses default change detection: it updates plain
  properties from async HTTP callbacks, which `OnPush` would not render.
- `ToolViewComponent` owns tool-result rendering; `ChatService` strips the
  `[Tool '…' executed.]` prefix and parses JSON into `ChatMessage.data`. Custom tools must
  expose structured data through `serialize_event` (see `analysis` on
  `AnalyzeMarketObservation`) so the UI can render cards instead of raw JSON.
- `MarkdownPipe` is a deliberately small renderer (headings, lists, tables, code, bold,
  links). It escapes HTML before emitting tags, so do not bypass Angular sanitization.
