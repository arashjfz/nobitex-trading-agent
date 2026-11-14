# AGENTS.md

Repository-specific notes for AI agents working on this project.

## What this is

A Nobitex crypto trading assistant: FastAPI backend using the OpenHands Agent SDK + a
vendored `nobitex-mcp` server, and an Angular 20 dashboard.

## Layout

- `backend/app/` — FastAPI app. `agent_factory.py` builds the agent and the default MCP
  config; `technical.py` is the indicator engine; `tools.py` defines `AnalyzeMarketTool`.
- `backend/tests/` — pytest suite (technical, API, agent config).
- `frontend/src/app/` — standalone Angular components + services.
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
