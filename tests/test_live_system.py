"""Tests for YouTube livestream notification system, database operations, and alert logic."""

from unittest.mock import AsyncMock, MagicMock
import discord
import pytest

from src.database.db import DatabaseManager
from src.services.youtube_service import BroadcastMetadata
from src.ui.embeds import COLOR_YOUTUBE, create_live_notification_embed


@pytest.mark.asyncio
async def test_youtube_channel_db_operations(test_db: DatabaseManager) -> None:
    """Verify upserting and retrieving YouTube channels in the database."""
    guild_id = 11223344
    channel_id = "UC_GAMER_123"
    channel_name = "Super Creator"

    # 1. Initially none
    assert await test_db.get_youtube_channel(guild_id) is None

    # 2. Upsert channel
    await test_db.upsert_youtube_channel(guild_id, channel_id, channel_name)
    record = await test_db.get_youtube_channel(guild_id)
    assert record is not None
    assert record["channel_id"] == channel_id
    assert record["channel_name"] == channel_name
    assert record["is_active"] == 1

    # 3. Update last checked timestamp
    await test_db.update_youtube_last_checked(guild_id, channel_id)
    record = await test_db.get_youtube_channel(guild_id)
    assert record["last_checked_at"] is not None


@pytest.mark.asyncio
async def test_get_last_announced_broadcast(test_db: DatabaseManager) -> None:
    """Verify fetching the most recently announced broadcast for a guild."""
    guild_id = 998877
    # Initially None
    assert await test_db.get_last_announced_broadcast(guild_id) is None

    # Record two broadcasts
    await test_db.record_broadcast_notified("vid_1", "UC_1", guild_id, "Stream 1")
    await test_db.record_broadcast_notified("vid_2", "UC_1", guild_id, "Stream 2")

    last = await test_db.get_last_announced_broadcast(guild_id)
    assert last is not None
    assert last["broadcast_id"] == "vid_2"
    assert last["title"] == "Stream 2"


def test_create_live_notification_embed() -> None:
    """Verify live alert embed layout and branding."""
    embed = create_live_notification_embed(
        streamer_name="AceGamer",
        stream_title="Going for Rank 1 Radiance!",
        stream_url="https://youtube.com/watch?v=sample123",
        thumbnail_url="https://img.youtube.com/vi/sample123/maxresdefault.jpg",
        game_name="Valorant",
    )

    assert embed.color == COLOR_YOUTUBE
    assert "Going for Rank 1 Radiance!" in (embed.title or "")
    assert embed.url == "https://youtube.com/watch?v=sample123"
    assert embed.image.url == "https://img.youtube.com/vi/sample123/maxresdefault.jpg"

    # Check fields
    field_names = [f.name for f in embed.fields]
    assert "👤 Streamer" in field_names
    assert "🎮 Game / Category" in field_names


@pytest.mark.asyncio
async def test_duplicate_prevention_logic(test_db: DatabaseManager) -> None:
    """Verify that a broadcast is not notified twice across restarts."""
    broadcast_id = "unique_live_stream_456"
    guild_id = 778899

    # Check initially not notified
    assert not await test_db.is_broadcast_notified(broadcast_id)

    # First notification record
    await test_db.record_broadcast_notified(
        broadcast_id=broadcast_id,
        channel_id="UC_CH1",
        guild_id=guild_id,
        title="Live Now",
    )

    # Subsequent check detects duplicate
    assert await test_db.is_broadcast_notified(broadcast_id)
