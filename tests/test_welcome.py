"""Tests for custom welcome system, embed rendering, and database operations."""

from unittest.mock import AsyncMock, MagicMock
import discord
import pytest

from src.cogs.welcome import WelcomeCog
from src.database.db import DatabaseManager
from src.ui.embeds import create_welcome_embed


@pytest.mark.asyncio
async def test_reset_welcome_settings(test_db: DatabaseManager) -> None:
    """Verify that resetting welcome settings returns all values to factory defaults."""
    guild_id = 445566

    # 1. Customize settings first
    await test_db.update_guild_settings(
        guild_id,
        welcome_enabled=1,
        welcome_channel_id=12345,
        welcome_message="Custom Welcome {user}",
        welcome_embed_color="#00FF00",
    )

    customized = await test_db.get_guild_settings(guild_id)
    assert customized["welcome_enabled"] == 1
    assert customized["welcome_channel_id"] == 12345
    assert customized["welcome_embed_color"] == "#00FF00"

    # 2. Reset settings
    reset_data = await test_db.reset_welcome_settings(guild_id)
    assert reset_data["welcome_enabled"] == 0
    assert reset_data["welcome_channel_id"] is None
    assert reset_data["welcome_embed_color"] == "#5865F2"
    assert "Welcome to {server}" in reset_data["welcome_message"]


def test_create_welcome_embed() -> None:
    """Verify welcome embed structure, color parsing, and attachments."""
    embed = create_welcome_embed(
        title="Welcome to the Guild!",
        description="Have fun and check the rules.",
        color_int=0xFF00FF,
        footer_text="Member #50",
        thumbnail_url="https://images.example.com/thumb.png",
        image_url="https://images.example.com/banner.png",
    )

    assert embed.title == "Welcome to the Guild!"
    assert embed.description == "Have fun and check the rules."
    assert embed.color == discord.Color(0xFF00FF)
    assert embed.footer.text == "Member #50"
    assert embed.thumbnail.url == "https://images.example.com/thumb.png"
    assert embed.image.url == "https://images.example.com/banner.png"


@pytest.mark.asyncio
async def test_on_member_join_ignores_bot() -> None:
    """Verify bots joining the server do not trigger welcome messages."""
    mock_bot = MagicMock()
    mock_member = MagicMock(spec=discord.Member)
    mock_member.bot = True

    cog = WelcomeCog(mock_bot)
    # on_member_join should exit immediately without accessing database
    await cog.on_member_join(mock_member)
    mock_bot.db.get_guild_settings.assert_not_called()


@pytest.mark.asyncio
async def test_on_member_join_dispatches_when_enabled(test_db: DatabaseManager) -> None:
    """Verify welcome message is properly delivered when enabled."""
    guild_id = 998811
    channel_id = 776655

    await test_db.update_guild_settings(
        guild_id,
        welcome_enabled=1,
        welcome_channel_id=channel_id,
        welcome_message="Hello {user}, welcome to {server}!",
    )

    # Setup mock bot and member
    mock_bot = MagicMock()
    mock_bot.db = test_db

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.send = AsyncMock()

    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.id = guild_id
    mock_guild.name = "Test Guild"
    mock_guild.member_count = 100
    mock_guild.get_channel.return_value = mock_channel

    mock_member = MagicMock(spec=discord.Member)
    mock_member.bot = False
    mock_member.guild = mock_guild
    mock_member.mention = "<@123>"
    mock_member.display_name = "NewPlayer"
    mock_member.display_avatar.url = "https://avatar.url/avatar.png"

    cog = WelcomeCog(mock_bot)
    await cog.on_member_join(mock_member)

    # Verify channel.send was called
    mock_channel.send.assert_called_once()
    args, kwargs = mock_channel.send.call_args
    assert "Hello <@123>, welcome to Test Guild!" in kwargs["content"]
    assert isinstance(kwargs["embed"], discord.Embed)
    assert kwargs["allowed_mentions"].users == [mock_member]
