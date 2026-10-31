"""Interactive /setup command and control panel."""

import logging
from typing import TYPE_CHECKING
import discord
from discord import app_commands
from discord.ext import commands

from src.ui.views import SetupDashboardView
from src.utils.permissions import is_guild_admin

if TYPE_CHECKING:
    from src.main import LegendBot

logger = logging.getLogger("LegendBot.SetupPanel")


class SetupPanelCog(commands.Cog, name="SetupPanel"):
    """Cog handling the interactive /setup administration panel."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: "LegendBot" = bot  # type: ignore[assignment]

    @app_commands.command(name="setup", description="Open the interactive configuration dashboard.")
    @is_guild_admin()
    async def setup_panel(self, interaction: discord.Interaction) -> None:
        """Launch the categorized interactive settings dashboard."""
        await interaction.response.defer(ephemeral=True)

        view = SetupDashboardView(bot=self.bot, guild_id=interaction.guild_id, initial_category="youtube")
        embed = await view.build_category_embed(interaction.guild_id)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Extension entry point for SetupPanelCog."""
    await bot.add_cog(SetupPanelCog(bot))
