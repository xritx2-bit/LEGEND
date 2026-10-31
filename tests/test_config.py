"""Tests for configuration loading and validation."""

import pytest
from src.config import Config, redact_secret


def test_config_defaults(clean_env: None) -> None:
    """Verify sensible defaults when no environment variables are set."""
    cfg = Config.load()
    assert cfg.discord_token == ""
    assert cfg.guild_id is None
    assert cfg.youtube_poll_interval == 300
    assert str(cfg.database_path) == "data\\bot_database.db" or str(cfg.database_path) == "data/bot_database.db"
    assert cfg.log_level == "INFO"
    assert not cfg.is_youtube_configured


def test_config_custom_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify custom environment values are properly parsed."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "mock_bot_token_12345")
    monkeypatch.setenv("DISCORD_GUILD_ID", "987654321")
    monkeypatch.setenv("YOUTUBE_API_KEY", "mock_yt_key_abcde")
    monkeypatch.setenv("YOUTUBE_CHANNEL_ID", "UC1234567890")
    monkeypatch.setenv("YOUTUBE_POLL_INTERVAL", "120")
    monkeypatch.setenv("DATABASE_PATH", "custom/db.sqlite")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    cfg = Config.load()
    assert cfg.discord_token == "mock_bot_token_12345"
    assert cfg.guild_id == 987654321
    assert cfg.youtube_api_key == "mock_yt_key_abcde"
    assert cfg.youtube_channel_id == "UC1234567890"
    assert cfg.youtube_poll_interval == 120
    assert cfg.log_level == "DEBUG"
    assert cfg.is_youtube_configured


def test_poll_interval_minimum_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure poll interval cannot be set lower than 60 seconds to protect quotas."""
    monkeypatch.setenv("YOUTUBE_POLL_INTERVAL", "10")  # too low
    cfg = Config.load()
    assert cfg.youtube_poll_interval == 300  # falls back to safe default


def test_validate_for_start_raises_on_empty(clean_env: None) -> None:
    """Ensure validation fails when token is empty or placeholder."""
    cfg = Config.load()
    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN is missing"):
        cfg.validate_for_start()


def test_redact_secret() -> None:
    """Ensure secrets are masked properly without leaking credentials."""
    assert redact_secret("") == "[NOT SET]"
    assert redact_secret("abc") == "****"
    assert redact_secret("my_super_secret_token_1234") == f"{'*' * 22}1234"
