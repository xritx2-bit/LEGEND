"""Tests for SQLite database manager and schema persistence."""

import pytest
from src.database.db import DatabaseManager


@pytest.mark.asyncio
async def test_guild_settings_default_creation(test_db: DatabaseManager) -> None:
    """Verify that querying an unknown guild creates a default row with sensible defaults."""
    settings = await test_db.get_guild_settings(guild_id=123456789)
    assert settings["guild_id"] == 123456789
    assert settings["welcome_enabled"] == 0
    assert settings["welcome_channel_id"] is None
    assert settings["live_allow_everyone"] == 0
    assert "Welcome to" in settings["welcome_message"]


@pytest.mark.asyncio
async def test_update_guild_settings(test_db: DatabaseManager) -> None:
    """Verify updating specific settings persists and returns updated dictionary."""
    guild_id = 987654321
    updated = await test_db.update_guild_settings(
        guild_id=guild_id,
        welcome_enabled=1,
        welcome_channel_id=555666777,
        live_channel_id=888999111,
        live_allow_everyone=1,
    )

    assert updated["welcome_enabled"] == 1
    assert updated["welcome_channel_id"] == 555666777
    assert updated["live_channel_id"] == 888999111
    assert updated["live_allow_everyone"] == 1

    # Verify persistence by fetching again from database
    refetched = await test_db.get_guild_settings(guild_id=guild_id)
    assert refetched["welcome_enabled"] == 1
    assert refetched["welcome_channel_id"] == 555666777


@pytest.mark.asyncio
async def test_broadcast_notification_tracking(test_db: DatabaseManager) -> None:
    """Verify broadcast tracking and duplicate notification prevention."""
    broadcast_id = "test_yt_video_id_999"
    channel_id = "UC_gaming_channel_123"
    guild_id = 123456

    # 1. Before recording, should be False
    assert not await test_db.is_broadcast_notified(broadcast_id)

    # 2. Record notification
    await test_db.record_broadcast_notified(
        broadcast_id=broadcast_id,
        channel_id=channel_id,
        guild_id=guild_id,
        title="Epic Gaming Stream",
    )

    # 3. After recording, should be True
    assert await test_db.is_broadcast_notified(broadcast_id)

    # 4. Duplicate insertion should not raise an error
    await test_db.record_broadcast_notified(
        broadcast_id=broadcast_id,
        channel_id=channel_id,
        guild_id=guild_id,
        title="Duplicate Attempt",
    )
    assert await test_db.is_broadcast_notified(broadcast_id)

