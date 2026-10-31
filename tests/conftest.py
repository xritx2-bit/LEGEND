"""Shared test fixtures."""

import os
from pathlib import Path
from typing import AsyncGenerator
import pytest
import pytest_asyncio

from src.database.db import DatabaseManager


@pytest_asyncio.fixture
async def test_db(tmp_path: Path) -> AsyncGenerator[DatabaseManager, None]:
    """Provide a fresh, temporary SQLite database for each test."""
    db_file = tmp_path / "test_bot.db"
    manager = DatabaseManager(db_file)
    await manager.initialize_schema()
    try:
        yield manager
    finally:
        await manager.close()


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear relevant environment variables to test defaults."""
    keys = [
        "DISCORD_BOT_TOKEN",
        "DISCORD_GUILD_ID",
        "YOUTUBE_API_KEY",
        "YOUTUBE_CHANNEL_ID",
        "YOUTUBE_POLL_INTERVAL",
        "DATABASE_PATH",
        "LOG_LEVEL",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
