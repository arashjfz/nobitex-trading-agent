"""Tests for SDK event serialization used by the chat websocket."""

from __future__ import annotations

import json

from openhands.sdk.event import ObservationEvent
from openhands.sdk.llm.message import TextContent

from app.sessions import _blocks_text, _content_text, _json_safe, _with_language, serialize_event
from app.tools import AnalyzeMarketObservation


def test_blocks_text_flattens_text_content() -> None:
    assert _blocks_text([TextContent(text="first"), TextContent(text="second")]) == "first\nsecond"
    assert _blocks_text("plain") == "plain"
    assert _blocks_text(None) == ""


def test_with_language_prefixes_supported_locales() -> None:
    assert _with_language("analyze BTC", "fa").startswith("[Reply in Persian (Farsi).")
    assert _with_language("analyze BTC", "de").endswith("analyze BTC")
    assert _with_language("analyze BTC", None) == "analyze BTC"
    assert _with_language("analyze BTC", "xx") == "analyze BTC"


def test_json_safe_serializes_text_content() -> None:
    payload = {"thought": [TextContent(text="reasoning")], "count": 1}
    encoded = json.dumps(_json_safe(payload))
    assert "reasoning" in encoded
    assert '"count": 1' in encoded


def test_custom_observation_uses_llm_content_and_exposes_analysis() -> None:
    observation = AnalyzeMarketObservation(
        symbol="BTCUSDT",
        signal="HOLD",
        summary="BTCUSDT @ 60m — HOLD",
        analysis={"symbol": "BTCUSDT", "signal": "HOLD", "score": -0.2, "candles": [1, 2]},
    )
    assert _content_text(observation).startswith("BTCUSDT @ 60m — HOLD")

    event = ObservationEvent(
        tool_name="analyze_market",
        tool_call_id="call-1",
        action_id="action-1",
        observation=observation,
    )
    payload = serialize_event(event)
    assert payload is not None
    assert payload["data"]["signal"] == "HOLD"
    assert payload["data"]["candles"] == [1, 2]
    assert payload["observation"].startswith("BTCUSDT @ 60m — HOLD")
