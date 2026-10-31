"""Tests for permission checks and safe mention policies."""

from unittest.mock import MagicMock
import discord
from discord import app_commands
import pytest

from src.utils.permissions import (
    NotGuildAdminError,
    get_safe_allowed_mentions,
    is_guild_admin,
    is_guild_admin_predicate,
)


def test_safe_allowed_mentions_defaults() -> None:
    """Verify that default mentions restrict @everyone and @here."""
    mentions = get_safe_allowed_mentions(allow_everyone=False)
    assert not mentions.everyone
    assert mentions.roles == []
    assert mentions.users is True


def test_safe_allowed_mentions_with_role() -> None:
    """Verify role pings are constrained to the single configured role ID."""
    role_id = 99887766
    mentions = get_safe_allowed_mentions(allow_everyone=False, allowed_role_id=role_id)
    assert not mentions.everyone
    assert len(mentions.roles) == 1
    assert mentions.roles[0].id == role_id


def test_safe_allowed_mentions_allow_everyone() -> None:
    """Verify @everyone is enabled when explicitly authorized."""
    mentions = get_safe_allowed_mentions(allow_everyone=True)
    assert mentions.everyone is True


@pytest.mark.asyncio
async def test_is_guild_admin_rejects_dm() -> None:
    """Verify check rejects DM invocations."""
    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild = None

    with pytest.raises(app_commands.NoPrivateMessage):
        await is_guild_admin_predicate(mock_interaction)


@pytest.mark.asyncio
async def test_is_guild_admin_allows_server_owner() -> None:
    """Verify server owner always passes check."""
    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.owner_id = 12345

    mock_user = MagicMock(spec=discord.Member)
    mock_user.id = 12345

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild = mock_guild
    mock_interaction.user = mock_user

    result = await is_guild_admin_predicate(mock_interaction)
    assert result is True


@pytest.mark.asyncio
async def test_is_guild_admin_allows_administrator() -> None:
    """Verify member with Administrator permission passes check."""
    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.owner_id = 99999

    mock_user = MagicMock(spec=discord.Member)
    mock_user.id = 12345
    mock_user.guild_permissions = discord.Permissions(administrator=True)

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild = mock_guild
    mock_interaction.user = mock_user

    result = await is_guild_admin_predicate(mock_interaction)
    assert result is True


@pytest.mark.asyncio
async def test_is_guild_admin_allows_manage_guild() -> None:
    """Verify member with Manage Guild permission passes check."""
    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.owner_id = 99999

    mock_user = MagicMock(spec=discord.Member)
    mock_user.id = 12345
    mock_user.guild_permissions = discord.Permissions(manage_guild=True)

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild = mock_guild
    mock_interaction.user = mock_user

    result = await is_guild_admin_predicate(mock_interaction)
    assert result is True


@pytest.mark.asyncio
async def test_is_guild_admin_rejects_regular_member() -> None:
    """Verify non-admin member is rejected with NotGuildAdminError."""
    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.owner_id = 99999

    mock_user = MagicMock(spec=discord.Member)
    mock_user.id = 12345
    mock_user.guild_permissions = discord.Permissions(send_messages=True)

    mock_interaction = MagicMock(spec=discord.Interaction)
    mock_interaction.guild = mock_guild
    mock_interaction.user = mock_user

    with pytest.raises(NotGuildAdminError):
        await is_guild_admin_predicate(mock_interaction)


def test_is_guild_admin_decorator_appends_check() -> None:
    """Verify the @is_guild_admin() decorator properly registers the check predicate."""
    decorator = is_guild_admin()

    async def sample_command(interaction: discord.Interaction):
        pass

    decorated = decorator(sample_command)
    assert hasattr(decorated, "__discord_app_commands_checks__")
    assert is_guild_admin_predicate in decorated.__discord_app_commands_checks__
