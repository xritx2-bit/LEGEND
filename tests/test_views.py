"""Tests for interactive setup UI components, views, and modals."""

from unittest.mock import MagicMock
import discord
import pytest

from src.database.db import DatabaseManager
from src.ui.views import SetupCategorySelect, SetupDashboardView


def test_setup_category_select_options() -> None:
    """Verify that all required settings categories exist in the selector."""
    select = SetupCategorySelect()
    values = [opt.value for opt in select.options]
    assert "youtube" in values
    assert "welcome" in values
    assert "appearance" in values
    assert "backup" in values


@pytest.mark.asyncio
async def test_setup_dashboard_view_build_embeds(test_db: DatabaseManager) -> None:
    """Verify setup view generates accurate embeds for every category."""
    guild_id = 991122

    mock_bot = MagicMock()
    mock_bot.db = test_db
    mock_bot.config.youtube_channel_id = "UC_GLOBAL_DEFAULT"

    view = SetupDashboardView(bot=mock_bot, guild_id=guild_id)

    # 1. YouTube category
    view.current_category = "youtube"
    view.update_components()
    embed = await view.build_category_embed(guild_id)
    assert "YouTube" in (embed.title or "")
    # Check that category-specific buttons are loaded
    btn_custom_ids = [item.custom_id for item in view.children if isinstance(item, discord.ui.Button)]
    assert "btn_yt_msg" in btn_custom_ids
    assert "btn_yt_everyone" in btn_custom_ids

    # 2. Welcome category
    view.current_category = "welcome"
    view.update_components()
    embed = await view.build_category_embed(guild_id)
    assert "Welcome" in (embed.title or "")
    btn_custom_ids = [item.custom_id for item in view.children if isinstance(item, discord.ui.Button)]
    assert "btn_w_toggle" in btn_custom_ids
    assert "btn_w_msg" in btn_custom_ids

    # 3. Appearance category
    view.current_category = "appearance"
    view.update_components()
    embed = await view.build_category_embed(guild_id)
    assert "Appearance" in (embed.title or "")

    # 4. Backup category
    view.current_category = "backup"
    view.update_components()
    embed = await view.build_category_embed(guild_id)
    assert "Backup" in (embed.title or "")
    btn_custom_ids = [item.custom_id for item in view.children if isinstance(item, discord.ui.Button)]
    assert "btn_b_export" in btn_custom_ids
