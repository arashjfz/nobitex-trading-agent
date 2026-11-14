"""Cron-based prompt scheduler backed by SQLite.

Each task stores a natural-language prompt and a cron expression. A background
thread wakes up on a fixed interval, runs due tasks through a fresh agent
session, and records the assistant's final answer.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter

from .config import Settings
from .sessions import SessionManager

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    cron TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    next_run_at REAL,
    last_run_at REAL,
    last_status TEXT,
    last_result TEXT,
    run_count INTEGER NOT NULL DEFAULT 0
)
"""


def _iso(timestamp: float | None, tz: ZoneInfo) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz).isoformat()


class Scheduler:
    def __init__(self, settings: Settings, manager: SessionManager) -> None:
        self.settings = settings
        self.manager = manager
        self.tz = ZoneInfo(settings.scheduler_timezone)
        self.db_path = settings.scheduler_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._db_lock = threading.Lock()
        self._running: set[str] = set()
        self._running_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        with self._db_lock:
            self._conn.execute(_SCHEMA)
            # A crash can leave a task marked running; nothing is running now.
            self._conn.execute(
                "UPDATE scheduled_tasks SET last_status = 'interrupted' "
                "WHERE last_status = 'running'"
            )
            # Skip runs missed while the server was down instead of firing them
            # late: for trading, a stale signal is worse than a skipped one.
            now = time.time()
            due = self._conn.execute(
                "SELECT id, cron FROM scheduled_tasks "
                "WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?",
                (now,),
            ).fetchall()
            for row in due:
                self._conn.execute(
                    "UPDATE scheduled_tasks SET next_run_at = ? WHERE id = ?",
                    (self.next_run(row["cron"], now), row["id"]),
                )
            self._conn.commit()

    # -- cron helpers ------------------------------------------------------
    @property
    def timezone_name(self) -> str:
        return self.settings.scheduler_timezone

    def validate_cron(self, expression: str) -> None:
        if not expression or not expression.strip():
            raise ValueError("cron expression is required")
        if not croniter.is_valid(expression):
            raise ValueError(f"invalid cron expression: {expression!r}")

    def next_run(self, expression: str, base: float | None = None) -> float:
        self.validate_cron(expression)
        start = datetime.fromtimestamp(base or time.time(), self.tz)
        return float(croniter(expression, start).get_next(float))

    def preview(self, expression: str, count: int = 3) -> list[str]:
        self.validate_cron(expression)
        iterator = croniter(expression, datetime.now(self.tz))
        return [
            datetime.fromtimestamp(iterator.get_next(float), self.tz).isoformat()
            for _ in range(max(1, count))
        ]

    # -- CRUD --------------------------------------------------------------
    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["enabled"] = bool(item["enabled"])
        item["next_run"] = _iso(item["next_run_at"], self.tz)
        item["last_run"] = _iso(item["last_run_at"], self.tz)
        return item

    def list(self) -> list[dict[str, Any]]:
        with self._db_lock:
            rows = self._conn.execute(
                "SELECT * FROM scheduled_tasks ORDER BY created_at"
            ).fetchall()
        return [self._row(row) for row in rows]

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._db_lock:
            row = self._conn.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._row(row) if row else None

    def create(
        self,
        prompt: str,
        cron: str,
        name: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt is required")
        self.validate_cron(cron)
        task_id = uuid.uuid4().hex
        now = time.time()
        label = (name or "Scheduled task").strip()[:80]
        next_at = self.next_run(cron, now) if enabled else None
        with self._db_lock:
            self._conn.execute(
                "INSERT INTO scheduled_tasks "
                "(id, name, prompt, cron, enabled, created_at, next_run_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, label, prompt, cron, int(enabled), now, next_at),
            )
            self._conn.commit()
        return self.get(task_id)  # type: ignore[return-value]

    def update(self, task_id: str, **fields: Any) -> dict[str, Any] | None:
        task = self.get(task_id)
        if task is None:
            return None
        updates: dict[str, Any] = {}
        if fields.get("name") is not None:
            updates["name"] = str(fields["name"]).strip()[:80]
        if fields.get("prompt") is not None:
            prompt = str(fields["prompt"]).strip()
            if not prompt:
                raise ValueError("prompt cannot be empty")
            updates["prompt"] = prompt
        if fields.get("cron") is not None:
            self.validate_cron(str(fields["cron"]))
            updates["cron"] = str(fields["cron"])
        if fields.get("enabled") is not None:
            updates["enabled"] = int(bool(fields["enabled"]))

        enabled = updates.get("enabled", int(task["enabled"]))
        cron = updates.get("cron", task["cron"])
        updates["next_run_at"] = self.next_run(cron) if enabled else None

        assignments = ", ".join(f"{key} = ?" for key in updates)
        with self._db_lock:
            self._conn.execute(
                f"UPDATE scheduled_tasks SET {assignments} WHERE id = ?",
                (*updates.values(), task_id),
            )
            self._conn.commit()
        return self.get(task_id)

    def delete(self, task_id: str) -> bool:
        with self._db_lock:
            cursor = self._conn.execute(
                "DELETE FROM scheduled_tasks WHERE id = ?", (task_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    # -- execution ---------------------------------------------------------
    def run_now(self, task_id: str) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        return self._spawn(task_id)

    def _spawn(self, task_id: str) -> bool:
        with self._running_lock:
            if task_id in self._running:
                return False
            self._running.add(task_id)
        threading.Thread(target=self._execute, args=(task_id,), daemon=True).start()
        return True

    def _record(self, task_id: str, **fields: Any) -> None:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self._db_lock:
            self._conn.execute(
                f"UPDATE scheduled_tasks SET {assignments} WHERE id = ?",
                (*fields.values(), task_id),
            )
            self._conn.commit()

    def _final_text(self, history: list[dict[str, Any]]) -> str:
        for item in reversed(history):
            if item.get("type") == "MessageEvent" and item.get("source") != "user":
                return str(item.get("text") or "")
        return ""

    def _execute(self, task_id: str) -> None:
        session = None
        started = time.time()
        try:
            task = self.get(task_id)
            if task is None:
                return
            self._record(task_id, last_status="running")
            session = self.manager.create()
            session.send(task["prompt"])
            deadline = started + self.settings.scheduler_run_timeout
            while session.status == "running" and time.time() < deadline:
                time.sleep(2)
            timed_out = session.status == "running"
            text = self._final_text(session.history)
            errors = [e for e in session.history if e.get("type") == "Error"]
            if timed_out:
                status = "timeout"
                result = text or f"Timed out after {self.settings.scheduler_run_timeout:.0f}s"
            elif errors and not text:
                status = "error"
                result = str(errors[-1].get("error") or "agent error")
            else:
                status = "ok"
                result = text or "(no assistant message)"
            self._record(
                task_id,
                last_run_at=time.time(),
                last_status=status,
                last_result=result[:8000],
                run_count=int(task["run_count"]) + 1,
            )
        except Exception as exc:  # noqa: BLE001 - a failed task must not stop the loop
            self._record(
                task_id,
                last_run_at=time.time(),
                last_status="error",
                last_result=str(exc)[:8000],
            )
        finally:
            if session is not None:
                self.manager.remove(session.id)
            with self._running_lock:
                self._running.discard(task_id)

    def run_due(self) -> int:
        now = time.time()
        with self._db_lock:
            rows = self._conn.execute(
                "SELECT * FROM scheduled_tasks "
                "WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?",
                (now,),
            ).fetchall()
        started = 0
        for row in rows:
            task = self._row(row)
            self._record(task["id"], next_run_at=self.next_run(task["cron"], now))
            if self._spawn(task["id"]):
                started += 1
        return started

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_due()
            except Exception:  # noqa: BLE001 - keep the scheduler alive
                pass
            self._stop.wait(self.settings.scheduler_poll_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
