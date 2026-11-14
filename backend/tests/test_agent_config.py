"""Tests that the Nobitex MCP server is wired in by default and guarded."""

from __future__ import annotations

import re
import sys

from app.agent_factory import _filter_regex, build_agent, build_mcp_config
from app.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "llm_api_key": "test-key",
        "nobitex_env": "mainnet",
        "nobitex_dry_run": True,
    }
    base.update(overrides)
    return Settings(**base)


def test_mcp_config_points_at_vendored_server() -> None:
    config = build_mcp_config(_settings())
    assert "nobitex" in config
    server = config["nobitex"]
    assert server["command"] == sys.executable
    assert server["args"] == ["-m", "nobitex_mcp"]
    assert server["env"]["NOBITEX_DRY_RUN"] == "true"
    assert server["env"]["PYTHONPATH"].endswith("mcp/nobitex-mcp/src")


def test_mcp_config_forwards_credentials() -> None:
    config = build_mcp_config(
        _settings(nobitex_token="secret-token", nobitex_env="testnet")
    )
    env = config["nobitex"]["env"]
    assert env["NOBITEX_TOKEN"] == "secret-token"
    assert env["NOBITEX_ENV"] == "testnet"
    assert "testnet" in env["NOBITEX_BASE_URL"]


def test_filter_blocks_fund_moving_tools() -> None:
    pattern = re.compile(_filter_regex(allow_withdrawals=False))
    assert pattern.match("nobitex_place_spot_order")
    assert pattern.match("nobitex_get_orderbook")
    assert pattern.match("analyze_market")
    assert not pattern.match("nobitex_withdraw_crypto")
    assert not pattern.match("nobitex_create_api_key")
    assert not pattern.match("nobitex_add_address_book")


def test_filter_allows_everything_when_enabled() -> None:
    assert _filter_regex(allow_withdrawals=True) is None


def test_agent_has_custom_tool_and_mcp() -> None:
    agent = build_agent(_settings())
    assert [tool.name for tool in agent.tools] == ["AnalyzeMarketTool"]
    assert list(agent.mcp_config) == ["nobitex"]
