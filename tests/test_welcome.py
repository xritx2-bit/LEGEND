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
async def test_on_member_join_ignores_self() -> None:
    """Verify the bot does not send a welcome message to itself."""
    mock_bot = MagicMock()
    mock_bot.user.id = 999
    mock_member = MagicMock(spec=discord.Member)
    mock_member.id = 999
    mock_member.bot = True

    cog = WelcomeCog(mock_bot)
    await cog.on_member_join(mock_member)
    mock_bot.db.get_guild_settings.assert_not_called()


@pytest.mark.asyncio
async def test_on_member_join_welcomes_bot_accounts(test_db: DatabaseManager) -> None:
    """Verify other bots joining the server are welcomed."""
    guild_id = 998811
    channel_id = 776655

    await test_db.update_guild_settings(
        guild_id,
        welcome_enabled=1,
        welcome_channel_id=channel_id,
        welcome_message="Welcome bot {user} to {server}!",
    )

    mock_bot = MagicMock()
    mock_bot.user.id = 12345
    mock_bot.db = test_db

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.send = AsyncMock()

    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.id = guild_id
    mock_guild.name = "Test Guild"
    mock_guild.member_count = 100
    mock_guild.get_channel.return_value = mock_channel

    mock_member = MagicMock(spec=discord.Member)
    mock_member.id = 88888  # Different bot
    mock_member.bot = True
    mock_member.guild = mock_guild
    mock_member.mention = "<@88888>"
    mock_member.display_name = "MusicBot"
    mock_member.display_avatar.url = "https://avatar.url/musicbot.png"

    cog = WelcomeCog(mock_bot)
    await cog.on_member_join(mock_member)

    mock_channel.send.assert_called_once()
    _, kwargs = mock_channel.send.call_args
    assert "Welcome bot <@88888> to Test Guild!" in kwargs["content"]


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


@pytest.mark.asyncio
async def test_welcome_embed_with_avatar_placeholder(test_db: DatabaseManager) -> None:
    """Test /welcome embed using {user_avatar} placeholder and verify on_member_join renders it."""
    guild_id = 998877

    mock_bot = MagicMock()
    mock_bot.db = test_db

    cog = WelcomeCog(mock_bot)

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild_id = guild_id
    mock_interaction.user.name = "AdminUser"
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()

    # 1. Configure welcome embed with {user_avatar} and {server_banner}
    await cog.welcome_embed.callback(
        cog,
        mock_interaction,
        thumbnail="{user_avatar}",
        image="{server_banner}",
    )

    settings = await test_db.get_guild_settings(guild_id)
    assert settings["welcome_thumbnail_url"] == "{user_avatar}"
    assert settings["welcome_image_url"] == "{server_banner}"
    mock_interaction.followup.send.assert_called_once()

    # 2. Enable welcome channel and test member join rendering
    channel_id = 555111
    await test_db.update_guild_settings(
        guild_id,
        welcome_enabled=1,
        welcome_channel_id=channel_id,
    )

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.send = AsyncMock()

    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.id = guild_id
    mock_guild.name = "Placeholder Guild"
    mock_guild.member_count = 150
    mock_guild.icon.url = "https://cdn.discordapp.com/icons/guild.png"
    mock_guild.banner.url = "https://cdn.discordapp.com/banners/guild.png"
    mock_guild.get_channel.return_value = mock_channel

    mock_member = MagicMock(spec=discord.Member)
    mock_member.bot = False
    mock_member.guild = mock_guild
    mock_member.mention = "<@777>"
    mock_member.display_name = "AvatarTester"
    mock_member.display_avatar.url = "https://cdn.discordapp.com/avatars/777/pic.png"

    await cog.on_member_join(mock_member)

    mock_channel.send.assert_called_once()
    _, kwargs = mock_channel.send.call_args
    sent_embed: discord.Embed = kwargs["embed"]
    assert sent_embed.thumbnail.url == "https://cdn.discordapp.com/avatars/777/pic.png"
    assert sent_embed.image.url == "https://cdn.discordapp.com/banners/guild.png"


@pytest.mark.asyncio
async def test_welcome_upload_command(test_db: DatabaseManager) -> None:
    """Test /welcome upload for direct file uploads."""
    guild_id = 998877

    mock_bot = MagicMock()
    mock_bot.db = test_db

    cog = WelcomeCog(mock_bot)

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild_id = guild_id
    mock_interaction.user.name = "AdminUser"
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()

    mock_file = MagicMock(spec=discord.Attachment)
    mock_file.filename = "uploaded.png"
    mock_file.content_type = "image/png"
    mock_file.url = "https://cdn.discordapp.com/attachments/100/uploaded.png"

    # Upload thumbnail
    await cog.welcome_upload.callback(
        cog,
        mock_interaction,
        target="thumbnail",
        file=mock_file,
    )

    settings = await test_db.get_guild_settings(guild_id)
    assert settings["welcome_thumbnail_url"] == "https://cdn.discordapp.com/attachments/100/uploaded.png"

    # Upload banner
    mock_banner_file = MagicMock(spec=discord.Attachment)
    mock_banner_file.filename = "banner.webp"
    mock_banner_file.content_type = "image/webp"
    mock_banner_file.url = "https://cdn.discordapp.com/attachments/200/banner.webp"

    await cog.welcome_upload.callback(
        cog,
        mock_interaction,
        target="banner",
        file=mock_banner_file,
    )

    settings = await test_db.get_guild_settings(guild_id)
    assert settings["welcome_image_url"] == "https://cdn.discordapp.com/attachments/200/banner.webp"


@pytest.mark.asyncio
async def test_welcome_test_command(test_db: DatabaseManager) -> None:
    """Test /welcome test simulates welcome greeting to configured channel."""
    guild_id = 998877
    channel_id = 771122

    await test_db.update_guild_settings(
        guild_id,
        welcome_enabled=1,
        welcome_channel_id=channel_id,
        welcome_thumbnail_url="{user_avatar}",
    )

    mock_bot = MagicMock()
    mock_bot.db = test_db

    cog = WelcomeCog(mock_bot)

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.send = AsyncMock()

    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.id = guild_id
    mock_guild.name = "Test Server"
    mock_guild.member_count = 50
    mock_guild.get_channel.return_value = mock_channel

    mock_user = MagicMock(spec=discord.Member)
    mock_user.name = "TestAdmin"
    mock_user.mention = "<@111>"
    mock_user.display_name = "TestAdmin"
    mock_user.display_avatar.url = "https://cdn.discordapp.com/avatars/111/admin.png"

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild_id = guild_id
    mock_interaction.guild = mock_guild
    mock_interaction.user = mock_user
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()

    await cog.welcome_test.callback(cog, mock_interaction)

    mock_channel.send.assert_called_once()
    _, kwargs = mock_channel.send.call_args
    sent_embed: discord.Embed = kwargs["embed"]
    assert sent_embed.thumbnail.url == "https://cdn.discordapp.com/avatars/111/admin.png"
    mock_interaction.followup.send.assert_called_once()
