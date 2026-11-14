"""Conversation sessions: one OpenHands agent per chat, streamed over a queue."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from typing import Any

from openhands.sdk import Conversation
from openhands.sdk.event import ActionEvent, AgentErrorEvent, MessageEvent, ObservationEvent

from .agent_factory import build_agent
from .config import Settings

_EVENT_TYPES = (MessageEvent, ActionEvent, ObservationEvent, AgentErrorEvent)


def _content_text(message: Any) -> str:
    parts: list[str] = []
    for block in getattr(message, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _safe_dump(value: Any) -> Any:
    if value is None:
        return None
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json", exclude_none=True)
        except Exception:  # noqa: BLE001 - best-effort serialization
            return str(value)
    return str(value)


def serialize_event(event: Any) -> dict[str, Any] | None:
    """Convert an SDK event into a JSON-friendly payload for the browser."""
    if not isinstance(event, _EVENT_TYPES):
        return None

    payload: dict[str, Any] = {
        "type": type(event).__name__,
        "id": str(getattr(event, "id", "")),
        "timestamp": getattr(event, "timestamp", None),
    }

    if isinstance(event, MessageEvent):
        payload["source"] = event.source
        payload["text"] = _content_text(event.llm_message)
        return payload

    if isinstance(event, ActionEvent):
        payload["tool_name"] = event.tool_name
        payload["thought"] = event.thought
        payload["action"] = _safe_dump(event.action)
        return payload

    if isinstance(event, ObservationEvent):
        payload["tool_name"] = event.tool_name
        payload["is_error"] = bool(event.observation.is_error)
        payload["observation"] = _content_text(event.observation)
        return payload

    if isinstance(event, AgentErrorEvent):
        payload["error"] = getattr(event, "error", str(event))
        return payload

    return None


class AgentSession:
    def __init__(self, session_id: str, settings: Settings) -> None:
        self.id = session_id
        self.settings = settings
        self.created_at = time.time()
        self.status = "idle"
        self.history: list[dict[str, Any]] = []
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._lock = threading.Lock()
        self._conversation: Conversation | None = None

    def _ensure_conversation(self) -> Conversation:
        if self._conversation is not None:
            return self._conversation
        workspace = self.settings.workspace_root / "sessions" / self.id
        workspace.mkdir(parents=True, exist_ok=True)
        self._conversation = Conversation(
            agent=build_agent(self.settings),
            workspace=str(workspace),
            callbacks=[self._on_event],
            delete_on_close=False,
            max_iteration_per_run=self.settings.agent_max_iterations,
            max_budget_per_run=self.settings.agent_max_budget,
        )
        return self._conversation

    def _on_event(self, event: Any) -> None:
        payload = serialize_event(event)
        if payload is None:
            return
        self.history.append(payload)
        self.queue.put(payload)

    def send(self, message: str) -> None:
        with self._lock:
            if self.status == "running":
                raise RuntimeError("This session is already processing a message")
            self.status = "running"
        thread = threading.Thread(target=self._run, args=(message,), daemon=True)
        thread.start()

    def _run(self, message: str) -> None:
        try:
            conversation = self._ensure_conversation()
            conversation.send_message(message)
            conversation.run()
        except Exception as exc:  # noqa: BLE001 - surface to the client
            payload = {"type": "Error", "error": str(exc)}
            self.history.append(payload)
            self.queue.put(payload)
        finally:
            with self._lock:
                self.status = "idle"
            self.queue.put({"type": "Done"})

    def close(self) -> None:
        if self._conversation is not None:
            try:
                self._conversation.close()
            except Exception:  # noqa: BLE001 - best effort
                pass
            self._conversation = None


class SessionManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sessions: dict[str, AgentSession] = {}
        self._lock = threading.Lock()

    def create(self) -> AgentSession:
        session_id = uuid.uuid4().hex
        with self._lock:
            session = AgentSession(session_id, self.settings)
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> AgentSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def get_or_create(self, session_id: str | None) -> AgentSession:
        if session_id:
            existing = self.get(session_id)
            if existing is not None:
                return existing
        return self.create()

    def list(self) -> list[AgentSession]:
        with self._lock:
            return list(self._sessions.values())

    def remove(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            session.close()

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()
