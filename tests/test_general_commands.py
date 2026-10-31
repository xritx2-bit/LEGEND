"""Tests for diagnostic commands (/ping and /botinfo)."""

from unittest.mock import AsyncMock, MagicMock
import discord
import pytest

from src.cogs.general import GeneralCog
from src.database.db import DatabaseManager


@pytest.mark.asyncio
async def test_ping_command_execution(test_db: DatabaseManager) -> None:
    """Verify /ping measures gateway and database roundtrip latency."""
    mock_bot = MagicMock()
    mock_bot.latency = 0.045  # 45ms
    mock_bot.db = test_db

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.response.send_message = AsyncMock()
    mock_interaction.user.display_name = "Creator"

    cog = GeneralCog(mock_bot)
    await cog.ping.callback(cog, mock_interaction)

    mock_interaction.response.send_message.assert_called_once()
    _, kwargs = mock_interaction.response.send_message.call_args
    embed = kwargs["embed"]

    assert isinstance(embed, discord.Embed)
    assert "Pong!" in (embed.title or "")
    field_names = [f.name for f in embed.fields]
    assert "📡 Gateway Latency" in field_names
    assert "💾 Database Latency" in field_names


@pytest.mark.asyncio
async def test_botinfo_command_execution() -> None:
    """Verify /botinfo displays server counts, python version, and uptime."""
    mock_bot = MagicMock()
    mock_bot.guilds = [MagicMock(), MagicMock()]
    mock_bot.users = [MagicMock()]
    mock_bot.cogs = {"General": MagicMock(), "YouTubeCog": MagicMock()}
    mock_bot.user = MagicMock()
    mock_bot.user.avatar = None

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.response.send_message = AsyncMock()

    cog = GeneralCog(mock_bot)
    await cog.botinfo.callback(cog, mock_interaction)

    mock_interaction.response.send_message.assert_called_once()
    _, kwargs = mock_interaction.response.send_message.call_args
    embed = kwargs["embed"]

    assert isinstance(embed, discord.Embed)
    assert "Bot Information" in (embed.title or "")
    field_dict = {f.name: f.value for f in embed.fields}
    assert "`2`" in field_dict["🌐 Servers"]
    assert "`2`" in field_dict["⚙️ Loaded Cogs"]
