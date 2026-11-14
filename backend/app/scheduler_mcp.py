"""MCP server that exposes the prompt scheduler to the trading agent.

The server is intentionally thin: every tool calls the FastAPI scheduler API so
that scheduled work runs inside the API process, where the agent sessions and
the Nobitex MCP server already live.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

API_URL = os.environ.get("SCHEDULER_API_URL", "http://127.0.0.1:8011").rstrip("/")

mcp = MCPServer(
    name="scheduler",
    title="Prompt Scheduler",
    version="1.0.0",
    instructions=(
        "Schedule recurring agent prompts with cron expressions. Use "
        "schedule_task to create a task, list_scheduled_tasks to inspect them, "
        "and cancel_scheduled_task to remove one. Cron uses five fields: "
        "minute hour day-of-month month day-of-week."
    ),
)


def _call(method: str, path: str, **kwargs: Any) -> Any:
    try:
        response = httpx.request(method, f"{API_URL}{path}", timeout=30, **kwargs)
    except httpx.HTTPError as exc:
        raise ToolError(f"Scheduler API unreachable at {API_URL}: {exc}") from exc
    if response.status_code >= 400:
        raise ToolError(f"Scheduler API error {response.status_code}: {response.text[:500]}")
    return response.json()


@mcp.tool(structured_output=False)
def get_scheduler_info() -> Any:
    """Return the scheduler timezone, current time and task count.

    Call this before converting a natural-language schedule ("every day at 9")
    into a cron expression so you know which timezone the cron is evaluated in.
    """
    return _call("GET", "/api/schedules")


@mcp.tool(structured_output=False)
def schedule_task(
    prompt: str,
    cron: str,
    name: str | None = None,
    enabled: bool = True,
) -> Any:
    """Create a recurring task that runs a prompt through the trading agent.

    Args:
        prompt: The instruction to run, e.g. "Find the best opportunities and
            buy or sell up to 50 dollars, respecting the stop-loss".
        cron: Five-field cron expression in the scheduler timezone, e.g.
            "0 9 * * *" for every day at 09:00, "*/30 * * * *" for every 30
            minutes, "0 9 * * 1-5" for weekdays at 09:00.
        name: Optional short label shown in the UI.
        enabled: Whether the task starts running immediately.
    """
    return _call(
        "POST",
        "/api/schedules",
        json={"prompt": prompt, "cron": cron, "name": name, "enabled": enabled},
    )


@mcp.tool(structured_output=False)
def list_scheduled_tasks() -> Any:
    """List all scheduled tasks with their cron, next run and last result."""
    return _call("GET", "/api/schedules")


@mcp.tool(structured_output=False)
def update_scheduled_task(
    task_id: str,
    prompt: str | None = None,
    cron: str | None = None,
    name: str | None = None,
    enabled: bool | None = None,
) -> Any:
    """Update a scheduled task. Only the provided fields are changed."""
    body = {
        key: value
        for key, value in {
            "prompt": prompt,
            "cron": cron,
            "name": name,
            "enabled": enabled,
        }.items()
        if value is not None
    }
    if not body:
        raise ToolError("Provide at least one field to update")
    return _call("PATCH", f"/api/schedules/{task_id}", json=body)


@mcp.tool(structured_output=False)
def cancel_scheduled_task(task_id: str) -> Any:
    """Delete a scheduled task by id."""
    return _call("DELETE", f"/api/schedules/{task_id}")


@mcp.tool(structured_output=False)
def run_scheduled_task_now(task_id: str) -> Any:
    """Run a scheduled task immediately without changing its cron schedule."""
    return _call("POST", f"/api/schedules/{task_id}/run")


@mcp.tool(structured_output=False)
def validate_cron_expression(cron: str) -> Any:
    """Validate a cron expression and return the next three run times."""
    return _call("POST", "/api/schedules/validate", json={"cron": cron})


if __name__ == "__main__":
    mcp.run()
