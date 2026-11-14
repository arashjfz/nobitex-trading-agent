"""Runtime configuration: read masked settings and persist updates to .env."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import REPO_ROOT, Settings

ENV_PATH = REPO_ROOT / ".env"

ENV_KEYS: dict[str, str] = {
    "llm_model": "LLM_MODEL",
    "llm_api_key": "LLM_API_KEY",
    "llm_base_url": "LLM_BASE_URL",
    "llm_temperature": "LLM_TEMPERATURE",
    "nobitex_env": "NOBITEX_ENV",
    "nobitex_base_url": "NOBITEX_BASE_URL",
    "nobitex_token": "NOBITEX_TOKEN",
    "nobitex_public_key": "NOBITEX_PUBLIC_KEY",
    "nobitex_private_key": "NOBITEX_PRIVATE_KEY",
    "nobitex_auth_mode": "NOBITEX_AUTH_MODE",
    "nobitex_dry_run": "NOBITEX_DRY_RUN",
    "nobitex_read_only": "NOBITEX_READ_ONLY",
    "allow_withdrawals": "ALLOW_WITHDRAWALS",
    "agent_max_iterations": "AGENT_MAX_ITERATIONS",
    "scheduler_enabled": "SCHEDULER_ENABLED",
    "scheduler_timezone": "SCHEDULER_TIMEZONE",
}

SECRET_FIELDS = {
    "llm_api_key",
    "nobitex_token",
    "nobitex_public_key",
    "nobitex_private_key",
}

CLEARABLE_STRINGS = {"llm_base_url", "nobitex_base_url", "nobitex_auth_mode"}


def masked_settings(settings: Settings) -> dict[str, Any]:
    return {
        "llm": {
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
            "temperature": settings.llm_temperature,
            "api_key_set": bool(settings.llm_api_key),
        },
        "nobitex": {
            "env": settings.nobitex_env,
            "base_url": settings.resolved_nobitex_base_url,
            "base_url_override": settings.nobitex_base_url,
            "token_set": bool(settings.nobitex_token),
            "public_key_set": bool(settings.nobitex_public_key),
            "private_key_set": bool(settings.nobitex_private_key),
            "auth_mode": settings.nobitex_auth_mode,
            "dry_run": settings.nobitex_dry_run,
            "read_only": settings.nobitex_read_only,
        },
        "agent": {
            "max_iterations": settings.agent_max_iterations,
            "allow_withdrawals": settings.allow_withdrawals,
        },
        "scheduler": {
            "enabled": settings.scheduler_enabled,
            "timezone": settings.scheduler_timezone,
        },
    }


def _format(value: Any) -> str:
    if value is None or value == "":
        return ""
    text = "true" if value is True else "false" if value is False else str(value)
    if any(char in text for char in ' #"\'\n\t'):
        return json.dumps(text)
    return text


def write_env(path: Path, updates: dict[str, Any]) -> None:
    """Update keys in .env in place, preserving comments and unrelated keys."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if key in updates:
            output.append(f"{key}={_format(updates[key])}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={_format(value)}")

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)


def _normalize(field: str, value: Any) -> Any:
    if field in SECRET_FIELDS:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
    if isinstance(value, str):
        text = value.strip()
        if field == "llm_model" and not text:
            raise ValueError("LLM model is required")
        if field in CLEARABLE_STRINGS and not text:
            return None
        return text
    return value


def apply_settings_update(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate, persist, then apply settings so new agents use them."""
    normalized: dict[str, Any] = {}
    for field, value in payload.items():
        if field not in ENV_KEYS:
            continue
        value = _normalize(field, value)
        if value is None and field not in SECRET_FIELDS and field not in CLEARABLE_STRINGS:
            continue
        normalized[field] = value

    if "llm_temperature" in normalized:
        temperature = float(normalized["llm_temperature"])
        if not 0 <= temperature <= 2:
            raise ValueError("LLM temperature must be between 0 and 2")
        normalized["llm_temperature"] = temperature
    if "agent_max_iterations" in normalized:
        iterations = int(normalized["agent_max_iterations"])
        if not 1 <= iterations <= 500:
            raise ValueError("Agent max iterations must be between 1 and 500")
        normalized["agent_max_iterations"] = iterations
    if "scheduler_timezone" in normalized:
        try:
            ZoneInfo(str(normalized["scheduler_timezone"]))
        except Exception as exc:  # noqa: BLE001 - invalid timezone name
            raise ValueError(f"Unknown timezone: {normalized['scheduler_timezone']}") from exc

    env_updates = {ENV_KEYS[field]: value for field, value in normalized.items()}
    if env_updates:
        write_env(ENV_PATH, env_updates)
    for field, value in normalized.items():
        setattr(settings, field, value)
    if normalized:
        # The Nobitex client is cached; rebuild it with the new credentials/URL.
        from . import nobitex

        nobitex.get_client.cache_clear()
    return masked_settings(settings)
