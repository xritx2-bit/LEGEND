"""Main entry point for the Legend Discord Bot."""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import List

# Ensure project root is in sys.path regardless of how the script is invoked
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import discord
from discord import app_commands
from discord.ext import commands

from src.config import Config, redact_secret
from src.database.db import DatabaseManager
from src.ui.embeds import create_error_embed, create_warning_embed
from src.utils.logger import setup_logger
from src.utils.permissions import NotGuildAdminError

logger = logging.getLogger("LegendBot")

# List of extension cogs to load at startup
INITIAL_EXTENSIONS: List[str] = [
    "src.cogs.general",
    "src.cogs.youtube",
    "src.cogs.welcome",
]


class LegendBot(commands.Bot):
    """Custom bot class with modular extension loading and database management."""

    def __init__(self, config: Config) -> None:
        self.config = config

        # Configure intents: Server Members is required for welcome events
        intents = discord.Intents.default()
        intents.members = True

        # Restrict mentions by default to prevent unintended @everyone pings
        allowed_mentions = discord.AllowedMentions(
            everyone=False,
            roles=False,
            users=True,
            replied_user=True,
        )

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            allowed_mentions=allowed_mentions,
            help_command=None,
        )

        self.db = DatabaseManager(config.database_path)
        # Register centralized application command error handler
        self.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Centralized handler for all slash command errors."""
        # Unpack CommandInvokeError if present
        if isinstance(error, app_commands.CommandInvokeError):
            original = error.original
        else:
            original = error

        if isinstance(original, NotGuildAdminError):
            embed = create_error_embed(
                title="Permission Denied",
                description=str(original),
            )
        elif isinstance(original, app_commands.MissingPermissions):
            missing = ", ".join(f"`{p}`" for p in original.missing_permissions)
            embed = create_error_embed(
                title="Missing Permissions",
                description=f"You need the following permissions to run this command: {missing}",
            )
        elif isinstance(original, app_commands.BotMissingPermissions):
            missing = ", ".join(f"`{p}`" for p in original.missing_permissions)
            embed = create_error_embed(
                title="Bot Permission Error",
                description=f"I am missing necessary server permissions to run this: {missing}",
            )
        elif isinstance(original, app_commands.NoPrivateMessage):
            embed = create_error_embed(
                title="Server Only",
                description="This command cannot be used in Direct Messages. Please run it inside a server.",
            )
        elif isinstance(original, app_commands.CommandOnCooldown):
            embed = create_warning_embed(
                title="Command on Cooldown",
                description=f"Please wait `{original.retry_after:.1f}s` before trying again.",
            )
        elif isinstance(original, app_commands.CheckFailure):
            embed = create_error_embed(
                title="Access Denied",
                description="You do not have permission to execute this command.",
            )
        else:
            cmd_name = interaction.command.name if interaction.command else "Unknown"
            logger.error("Unhandled slash command error in /%s: %s", cmd_name, original, exc_info=True)
            embed = create_error_embed(
                title="Command Execution Error",
                description="An unexpected error occurred while executing this command. The issue has been recorded.",
            )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as send_err:
            logger.warning("Could not deliver error response to user: %s", send_err)

    async def setup_hook(self) -> None:
        """Asynchronous initialization called before login."""
        # 1. Initialize persistent SQLite database
        logger.info("Initializing SQLite database at %s...", self.config.database_path)
        await self.db.initialize_schema()

        # 2. Load cogs / extensions
        for extension in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("Loaded extension: %s", extension)
            except Exception as e:
                logger.error("Failed to load extension %s: %s", extension, e, exc_info=True)

        # 3. Synchronize Application Commands (Slash Commands)
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Synced %d slash commands instantly to dev guild ID: %s",
                len(synced),
                self.config.guild_id,
            )
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d slash commands globally.", len(synced))

    async def on_ready(self) -> None:
        """Called when the bot is connected and ready."""
        if self.user:
            logger.info("=" * 60)
            logger.info("🤖 Logged in as: %s (ID: %s)", self.user.name, self.user.id)
            logger.info("🌐 Connected to %d guilds", len(self.guilds))
            logger.info("📦 Python %s | discord.py %s", sys.version.split()[0], discord.__version__)
            logger.info("=" * 60)

            # Set a dynamic activity status
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name="for YouTube livestreams 🔴",
            )
            await self.change_presence(activity=activity)

    async def close(self) -> None:
        """Clean shutdown hook to safely close database connections."""
        logger.info("Shutting down bot and closing database connections...")
        await self.db.close()
        await super().close()
        logger.info("Bot shutdown complete.")


async def main() -> None:
    """Load configuration and start the bot event loop."""
    config = Config.load()
    setup_logger(log_level=config.log_level)

    logger.info("Starting Legend Discord Bot...")
    logger.info("Token: %s", redact_secret(config.discord_token))
    logger.info("Database Path: %s", config.database_path)
    logger.info("YouTube Configured: %s", config.is_youtube_configured)

    # Validate configuration before attempting to log in
    try:
        config.validate_for_start()
    except ValueError as e:
        logger.error("Configuration Error: %s", e)
        logger.error("Please create or edit your .env file based on .env.example.")
        return

    bot = LegendBot(config)

    # Handle OS termination signals gracefully
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.close()))
        except NotImplementedError:
            # Signal handlers are partially unsupported on Windows event loops
            pass

    try:
        async with bot:
            await bot.start(config.discord_token)
    except discord.LoginFailure:
        logger.critical("Failed to log in: Invalid Discord bot token.")
    except Exception as e:
        logger.critical("Unexpected error while running bot: %s", e, exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
