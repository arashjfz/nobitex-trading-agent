"""Build the OpenHands agent with the Nobitex MCP server wired in by default."""

from __future__ import annotations

import sys
from typing import Any

from openhands.sdk import LLM, Agent, Tool
from openhands.sdk.tool import register_tool

from .config import BACKEND_DIR, Settings
from .prompts import TRADING_SYSTEM_PROMPT
from .tools import AnalyzeMarketTool

_TOOL_REGISTERED = False

# MCP tools that move funds or change account security are hidden from the
# agent unless withdrawals are explicitly enabled.
_BLOCKED_MCP_TOOLS = (
    "withdraw",
    "confirm_withdraw",
    "cancel_withdraw",
    "request_rial_withdrawal",
    "cancel_rial_withdrawal",
    "create_address_book_item",
    "confirm_address_book_item",
    "add_address_book",
    "delete_address_book",
    "activate_whitelist",
    "deactivate_whitelist",
    "create_api_key",
    "delete_api_key",
    "update_api_key",
    "set_anti_phishing",
    "activate_emergency_cancel",
    "set_referrer",
    "login",
    "legacy_login",
    "logout",
    "resend_login_otp",
    "add_bank_card",
    "add_bank_account",
    "delete_bank_card",
    "delete_bank_account",
)


def _register_custom_tools() -> None:
    global _TOOL_REGISTERED
    if _TOOL_REGISTERED:
        return
    register_tool("AnalyzeMarketTool", AnalyzeMarketTool)
    _TOOL_REGISTERED = True


def _filter_regex(allow_withdrawals: bool) -> str | None:
    if allow_withdrawals:
        return None
    blocked = "|".join(_BLOCKED_MCP_TOOLS)
    return rf"^(?!nobitex_(?:{blocked})(?:_|$)).*$"


def build_mcp_config(settings: Settings) -> dict[str, dict[str, Any]]:
    """Return the default MCP configuration pointing at the vendored Nobitex server."""
    mcp_root = settings.mcp_nobitex_path
    src_dir = mcp_root / "src"
    env: dict[str, str] = {
        "PYTHONPATH": str(src_dir),
        "NOBITEX_ENV": settings.nobitex_env,
        "NOBITEX_BASE_URL": settings.resolved_nobitex_base_url,
        "NOBITEX_DRY_RUN": "true" if settings.nobitex_dry_run else "false",
        "NOBITEX_READ_ONLY": "true" if settings.nobitex_read_only else "false",
        "NOBITEX_TIMEOUT": str(settings.nobitex_timeout),
    }
    for key, value in (
        ("NOBITEX_TOKEN", settings.nobitex_token),
        ("NOBITEX_PUBLIC_KEY", settings.nobitex_public_key),
        ("NOBITEX_PRIVATE_KEY", settings.nobitex_private_key),
        ("NOBITEX_AUTH_MODE", settings.nobitex_auth_mode),
    ):
        if value:
            env[key] = value

    config: dict[str, dict[str, Any]] = {
        "nobitex": {
            "command": sys.executable,
            "args": ["-m", "nobitex_mcp"],
            "cwd": str(mcp_root),
            "env": env,
        }
    }
    if settings.scheduler_enabled:
        config["scheduler"] = {
            "command": sys.executable,
            "args": ["-m", "app.scheduler_mcp"],
            "cwd": str(BACKEND_DIR),
            "env": {
                "PYTHONPATH": str(BACKEND_DIR),
                "SCHEDULER_API_URL": settings.scheduler_api_url,
            },
        }
    return config


def build_llm(settings: Settings) -> LLM:
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
    }
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return LLM(**kwargs)


def build_agent(settings: Settings) -> Agent:
    _register_custom_tools()
    return Agent(
        llm=build_llm(settings),
        tools=[Tool(name="AnalyzeMarketTool")],
        mcp_config=build_mcp_config(settings),
        filter_tools_regex=_filter_regex(settings.allow_withdrawals),
        include_default_tools=[],
        system_prompt=TRADING_SYSTEM_PROMPT,
    )
