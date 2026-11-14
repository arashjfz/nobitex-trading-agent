"""Tests for SDK event serialization used by the chat websocket."""

from __future__ import annotations

import json

from openhands.sdk.llm.message import TextContent

from app.sessions import _blocks_text, _json_safe


def test_blocks_text_flattens_text_content() -> None:
    assert _blocks_text([TextContent(text="first"), TextContent(text="second")]) == "first\nsecond"
    assert _blocks_text("plain") == "plain"
    assert _blocks_text(None) == ""


def test_json_safe_serializes_text_content() -> None:
    payload = {"thought": [TextContent(text="reasoning")], "count": 1}
    encoded = json.dumps(_json_safe(payload))
    assert "reasoning" in encoded
    assert '"count": 1' in encoded
