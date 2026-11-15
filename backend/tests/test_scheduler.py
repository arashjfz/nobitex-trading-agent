"""Tests for the cron scheduler (no network, no LLM)."""

from __future__ import annotations

import time

import pytest

from app.config import Settings
from app.scheduler import Scheduler


class FakeSession:
    def __init__(self) -> None:
        self.id = "fake-session"
        self.status = "idle"
        self.history: list[dict] = []

    def send(self, message: str) -> None:
        self.status = "running"
        self.history = [
            {"type": "MessageEvent", "source": "user", "text": message},
            {
                "type": "ActionEvent",
                "tool_name": "analyze_market",
                "thought": "checking the market",
                "action": {"symbol": "BTCUSDT"},
            },
            {
                "type": "ObservationEvent",
                "tool_name": "analyze_market",
                "observation": '{"signal": "BUY"}',
                "data": {"signal": "BUY"},
            },
            {"type": "MessageEvent", "source": "assistant", "text": f"done: {message}"},
        ]
        self.status = "idle"


class FakeManager:
    def __init__(self) -> None:
        self.created: list[FakeSession] = []
        self.removed: list[str] = []

    def create(self) -> FakeSession:
        session = FakeSession()
        self.created.append(session)
        return session

    def remove(self, session_id: str) -> None:
        self.removed.append(session_id)


def _scheduler(tmp_path, manager=None) -> Scheduler:
    settings = Settings(
        scheduler_db_path=tmp_path / "scheduler.db",
        scheduler_timezone="UTC",
        scheduler_enabled=False,
    )
    return Scheduler(settings, manager or FakeManager())


def test_crud_roundtrip(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    task = scheduler.create(prompt="scan the market", cron="0 9 * * *", name="morning")
    assert task["enabled"] is True
    assert task["next_run_at"] is not None
    assert task["name"] == "morning"
    assert len(scheduler.list()) == 1

    updated = scheduler.update(task["id"], cron="*/30 * * * *", enabled=False)
    assert updated is not None
    assert updated["cron"] == "*/30 * * * *"
    assert updated["enabled"] is False
    assert updated["next_run_at"] is None

    assert scheduler.delete(task["id"]) is True
    assert scheduler.list() == []


def test_invalid_cron_is_rejected(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    with pytest.raises(ValueError):
        scheduler.create(prompt="x", cron="not a cron")
    with pytest.raises(ValueError):
        scheduler.preview("61 * * * *")


def test_preview_returns_future_runs(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    runs = scheduler.preview("0 9 * * *", 3)
    assert len(runs) == 3
    assert runs == sorted(runs)


def test_run_due_advances_and_spawns(tmp_path, monkeypatch) -> None:
    scheduler = _scheduler(tmp_path)
    task = scheduler.create(prompt="scan", cron="*/5 * * * *")
    scheduler._record(task["id"], next_run_at=time.time() - 60)

    spawned: list[str] = []
    monkeypatch.setattr(scheduler, "_spawn", lambda task_id: spawned.append(task_id) or True)

    assert scheduler.run_due() == 1
    assert spawned == [task["id"]]
    refreshed = scheduler.get(task["id"])
    assert refreshed is not None and refreshed["next_run_at"] > time.time()


def test_execute_records_result(tmp_path) -> None:
    manager = FakeManager()
    scheduler = _scheduler(tmp_path, manager)
    task = scheduler.create(prompt="find opportunities", cron="0 9 * * *")

    assert scheduler.run_now(task["id"]) is True
    deadline = time.time() + 10
    while time.time() < deadline:
        current = scheduler.get(task["id"])
        if current and current["last_status"] not in (None, "running"):
            break
        time.sleep(0.05)

    current = scheduler.get(task["id"])
    assert current is not None
    assert current["last_status"] == "ok"
    assert current["last_result"] == "done: find opportunities"
    assert current["run_count"] == 1
    assert current["last_run_id"]
    assert manager.removed == ["fake-session"]

    runs = scheduler.list_runs(task["id"])
    assert len(runs) == 1
    assert runs[0]["status"] == "ok"
    assert runs[0]["trigger"] == "manual"
    assert runs[0]["event_count"] == 4

    detail = scheduler.get_run(current["last_run_id"])
    assert detail is not None
    assert [event["type"] for event in detail["events"]] == [
        "MessageEvent",
        "ActionEvent",
        "ObservationEvent",
        "MessageEvent",
    ]
    assert detail["events"][0]["source"] == "user"


def test_deleting_task_removes_its_runs(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    task = scheduler.create(prompt="scan", cron="0 9 * * *")
    scheduler.run_now(task["id"])
    deadline = time.time() + 10
    while time.time() < deadline:
        runs = scheduler.list_runs(task["id"])
        if runs and runs[0]["status"] != "running":
            break
        time.sleep(0.05)

    assert scheduler.delete(task["id"]) is True
    assert scheduler.list_runs(task["id"]) == []
