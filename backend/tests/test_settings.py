"""Tests for runtime configuration updates and .env persistence."""

from __future__ import annotations

import pytest

from app import runtime_settings
from app.config import Settings
from app.runtime_settings import apply_settings_update, masked_settings


def test_masked_settings_hides_secrets() -> None:
    settings = Settings(
        llm_api_key="sk-secret",
        nobitex_token="nobitex-token",
        nobitex_private_key="private-key",
    )
    masked = masked_settings(settings)
    rendered = str(masked)
    assert masked["llm"]["api_key_set"] is True
    assert masked["nobitex"]["token_set"] is True
    assert "sk-secret" not in rendered
    assert "nobitex-token" not in rendered
    assert "private-key" not in rendered


def test_update_persists_and_applies(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("LLM_MODEL=old\n# keep me\nOTHER=1\n", encoding="utf-8")
    monkeypatch.setattr(runtime_settings, "ENV_PATH", env)

    settings = Settings(llm_model="old", llm_api_key="secret")
    apply_settings_update(
        settings,
        {
            "llm_model": "new-model",
            "llm_temperature": 0.5,
            "nobitex_dry_run": False,
            "llm_api_key": "",
        },
    )

    assert settings.llm_model == "new-model"
    assert settings.llm_temperature == 0.5
    assert settings.nobitex_dry_run is False
    assert settings.llm_api_key is None

    text = env.read_text(encoding="utf-8")
    assert "LLM_MODEL=new-model" in text
    assert "NOBITEX_DRY_RUN=false" in text
    assert "LLM_API_KEY=\n" in text
    assert "# keep me" in text
    assert "OTHER=1" in text
    assert oct(env.stat().st_mode)[-3:] == "600"


def test_optional_urls_can_be_cleared(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime_settings, "ENV_PATH", tmp_path / ".env")
    settings = Settings()

    apply_settings_update(settings, {"llm_base_url": "https://example.test/v1"})
    assert settings.llm_base_url == "https://example.test/v1"

    apply_settings_update(settings, {"llm_base_url": ""})
    assert settings.llm_base_url is None


def test_invalid_timezone_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime_settings, "ENV_PATH", tmp_path / ".env")
    settings = Settings()
    with pytest.raises(ValueError):
        apply_settings_update(settings, {"scheduler_timezone": "Not/AZone"})
    assert settings.scheduler_timezone == "Asia/Tehran"
