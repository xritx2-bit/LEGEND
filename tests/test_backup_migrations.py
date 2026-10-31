"""Tests for SQLite database schema migrations, backups, and configuration restore."""

from pathlib import Path
import aiosqlite
import pytest

from src.database.db import CURRENT_SCHEMA_VERSION, DatabaseManager


@pytest.mark.asyncio
async def test_schema_version_tracking(test_db: DatabaseManager) -> None:
    """Verify that the database tracks schema version accurately."""
    version = await test_db.get_schema_version()
    assert version == CURRENT_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_create_database_backup(test_db: DatabaseManager, tmp_path: Path) -> None:
    """Verify atomic database backup creation via VACUUM INTO."""
    # Write some initial state
    await test_db.update_guild_settings(12345, welcome_enabled=1, welcome_channel_id=999)

    backup_dir = tmp_path / "backups"
    backup_file = await test_db.create_database_backup(backup_dir)

    assert backup_file.exists()
    assert backup_file.stat().st_size > 0

    # Verify the backup file is a valid independent SQLite database
    async with aiosqlite.connect(backup_file) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM guild_settings WHERE guild_id = 12345;") as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["welcome_enabled"] == 1
            assert row["welcome_channel_id"] == 999


@pytest.mark.asyncio
async def test_export_and_restore_guild_backup(test_db: DatabaseManager) -> None:
    """Verify exporting and restoring guild configuration."""
    guild_id = 887766
    yt_channel = "UC_BACKUP_TEST"

    # Configure guild
    await test_db.update_guild_settings(
        guild_id,
        welcome_enabled=1,
        welcome_message="Custom Welcome Text",
        live_allow_everyone=1,
    )
    await test_db.upsert_youtube_channel(guild_id, yt_channel, "Channel Name")

    # Export backup
    backup = await test_db.export_guild_backup(guild_id)
    assert backup["guild_id"] == guild_id
    assert backup["settings"]["welcome_message"] == "Custom Welcome Text"
    assert backup["youtube_channel"]["channel_id"] == yt_channel

    # Reset or clear settings
    await test_db.reset_welcome_settings(guild_id)
    cleared = await test_db.get_guild_settings(guild_id)
    assert cleared["welcome_enabled"] == 0

    # Restore from backup
    success = await test_db.restore_guild_backup(guild_id, backup)
    assert success is True

    restored = await test_db.get_guild_settings(guild_id)
    assert restored["welcome_enabled"] == 1
    assert restored["welcome_message"] == "Custom Welcome Text"
