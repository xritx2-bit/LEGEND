"""YouTube livestream notification cog, background polling loop, and /live commands."""

import asyncio
import logging
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.services.youtube_service import (
    BroadcastMetadata,
    YouTubeAPIError,
    YouTubeChannelNotFoundError,
    YouTubeInvalidKeyError,
    YouTubeQuotaExceededError,
    YouTubeService,
)
from src.ui.embeds import (
    create_error_embed,
    create_info_embed,
    create_live_notification_embed,
    create_success_embed,
    create_warning_embed,
)
from src.utils.permissions import get_safe_allowed_mentions, is_guild_admin
from src.utils.validators import render_template, validate_template_placeholders

logger = logging.getLogger("LegendBot.YouTubeCog")

ALLOWED_LIVE_PLACEHOLDERS = {"streamer", "title", "url", "game", "role"}


class YouTubeCog(commands.GroupCog, group_name="live", group_description="YouTube livestream notification management"):
    """Cog handling YouTube livestream monitoring, alerts, and /live slash commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.yt_service = YouTubeService(
            api_key=bot.config.youtube_api_key,
            default_channel_id=bot.config.youtube_channel_id,
        )
        self.poll_interval = bot.config.youtube_poll_interval

        # Start background polling loop if YouTube API is configured
        if bot.config.is_youtube_configured:
            self.live_monitor_loop.change_interval(seconds=self.poll_interval)
            self.live_monitor_loop.start()
            logger.info("YouTube livestream background polling started (interval: %ds).", self.poll_interval)
        else:
            logger.warning("YouTube API is not fully configured in .env. Live polling loop is idle.")

    def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        self.live_monitor_loop.cancel()
        asyncio_task = asyncio.create_task(self.yt_service.close())
        asyncio_task.add_done_callback(lambda _: None)

    # -------------------------------------------------------------
    # Background Polling Loop
    # -------------------------------------------------------------

    @tasks.loop(seconds=300)
    async def live_monitor_loop(self) -> None:
        """Background loop that periodically polls YouTube channels for active livestreams."""
        for guild in self.bot.guilds:
            try:
                await self.check_guild_livestreams(guild)
            except Exception as e:
                logger.error("Error checking livestreams for guild %s (%d): %s", guild.name, guild.id, e, exc_info=True)

    @live_monitor_loop.before_loop
    async def before_live_monitor_loop(self) -> None:
        """Wait until the bot gateway is ready before starting the polling loop."""
        await self.bot.wait_until_ready()

    async def check_guild_livestreams(self, guild: discord.Guild) -> Optional[BroadcastMetadata]:
        """Check YouTube channel for a single guild and send alert if a new livestream is found."""
        settings = await self.bot.db.get_guild_settings(guild.id)
        target_channel_id = settings.get("live_channel_id")
        if not target_channel_id:
            return None

        # Determine YouTube channel ID: Guild specific or global default
        yt_record = await self.bot.db.get_youtube_channel(guild.id)
        yt_channel_id = yt_record.get("channel_id") if yt_record else self.bot.config.youtube_channel_id
        if not yt_channel_id or yt_channel_id == "your_youtube_channel_id_here":
            return None

        # Query YouTube API for active stream
        try:
            broadcast = await self.yt_service.fetch_active_livestream(yt_channel_id)
            await self.bot.db.update_youtube_last_checked(guild.id, yt_channel_id)
        except YouTubeQuotaExceededError:
            logger.error("Skipping livestream check: YouTube API quota exceeded.")
            return None
        except YouTubeAPIError as api_err:
            logger.warning("YouTube API error while checking channel %s: %s", yt_channel_id, api_err)
            return None

        if not broadcast:
            return None

        # Check if already notified
        already_notified = await self.bot.db.is_broadcast_notified(broadcast.broadcast_id)
        if already_notified:
            logger.debug("Broadcast %s already notified. Skipping.", broadcast.broadcast_id)
            return None

        # Deliver notification to Discord
        await self.send_livestream_alert(guild=guild, settings=settings, broadcast=broadcast)
        return broadcast

    async def send_livestream_alert(
        self,
        guild: discord.Guild,
        settings: dict,
        broadcast: BroadcastMetadata,
    ) -> bool:
        """Format and send the livestream notification to the target Discord channel."""
        target_channel_id = settings.get("live_channel_id")
        if not target_channel_id:
            return False

        channel = guild.get_channel(target_channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Configured live channel %s not found in guild %s", target_channel_id, guild.name)
            return False

        # Prepare role ping and content
        role_id = settings.get("live_role_id")
        allow_everyone = bool(settings.get("live_allow_everyone", 0))

        role_mention = ""
        if allow_everyone:
            role_mention = "@everyone"
        elif role_id:
            role_mention = f"<@&{role_id}>"

        context = {
            "streamer": broadcast.channel_title,
            "title": broadcast.title,
            "url": broadcast.url,
            "game": broadcast.game_name or "Gaming",
            "role": role_mention,
        }

        template = settings.get("live_message_template") or "🔴 **{streamer}** is now LIVE!\n{url}"
        message_text = render_template(template, context)
        if role_mention and role_mention not in message_text:
            message_text = f"{role_mention} {message_text}"

        embed = create_live_notification_embed(
            streamer_name=broadcast.channel_title,
            stream_title=broadcast.title,
            stream_url=broadcast.url,
            thumbnail_url=broadcast.thumbnail_url,
            game_name=broadcast.game_name,
        )

        allowed_mentions = get_safe_allowed_mentions(
            allow_everyone=allow_everyone,
            allowed_role_id=role_id,
        )

        try:
            await channel.send(
                content=message_text,
                embed=embed,
                allowed_mentions=allowed_mentions,
            )
            # Record notification in SQLite database to prevent duplicates
            await self.bot.db.record_broadcast_notified(
                broadcast_id=broadcast.broadcast_id,
                channel_id=broadcast.channel_id,
                guild_id=guild.id,
                title=broadcast.title,
                published_at=broadcast.published_at,
            )
            logger.info(
                "Livestream alert sent to #%s in %s for broadcast %s (%s)",
                channel.name,
                guild.name,
                broadcast.broadcast_id,
                broadcast.title,
            )
            return True
        except discord.Forbidden:
            logger.error("Missing permissions to send livestream alert in #%s (%d)", channel.name, channel.id)
            return False
        except Exception as e:
            logger.error("Failed to send livestream alert: %s", e, exc_info=True)
            return False

    # -------------------------------------------------------------
    # Slash Commands (/live ...)
    # -------------------------------------------------------------

    @app_commands.command(name="setup", description="Configure YouTube livestream notification channel, role, and template.")
    @app_commands.describe(
        youtube_channel_id="Your YouTube Channel ID (starts with UC...)",
        discord_channel="Discord text channel where alerts will be posted",
        notification_role="(Optional) Role to ping when stream starts",
        allow_everyone="Allow @everyone pings (requires administrator confirmation)",
        message_template="(Optional) Custom message text above embed. Variables: {streamer}, {title}, {url}, {game}",
    )
    @is_guild_admin()
    async def live_setup(
        self,
        interaction: discord.Interaction,
        youtube_channel_id: str,
        discord_channel: discord.TextChannel,
        notification_role: Optional[discord.Role] = None,
        allow_everyone: bool = False,
        message_template: Optional[str] = None,
    ) -> None:
        """Configure live alert settings for this server."""
        await interaction.response.defer(ephemeral=True)

        # Validate template if provided
        if message_template:
            is_valid, invalid_tokens = validate_template_placeholders(message_template, ALLOWED_LIVE_PLACEHOLDERS)
            if not is_valid:
                embed = create_error_embed(
                    title="Invalid Template Tokens",
                    description=f"The following tokens are not supported: {', '.join(f'`{{{t}}}`' for t in invalid_tokens)}\n"
                                f"Supported tokens: {', '.join(f'`{{{t}}}`' for t in ALLOWED_LIVE_PLACEHOLDERS)}",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # Attempt to verify YouTube channel details
        channel_name = None
        if self.bot.config.is_youtube_configured:
            try:
                details = await self.yt_service.fetch_channel_details(youtube_channel_id.strip())
                channel_name = details.get("title")
            except YouTubeChannelNotFoundError:
                embed = create_warning_embed(
                    title="Channel Not Found",
                    description=f"Could not find YouTube channel `{youtube_channel_id}` on YouTube. "
                                f"Please verify the ID (e.g. `UC...`). The settings have not been saved.",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            except Exception as e:
                logger.warning("Could not pre-verify YouTube channel: %s", e)

        # Update database settings
        update_data = {
            "live_channel_id": discord_channel.id,
            "live_role_id": notification_role.id if notification_role else None,
            "live_allow_everyone": 1 if allow_everyone else 0,
        }
        if message_template:
            update_data["live_message_template"] = message_template

        await self.bot.db.update_guild_settings(interaction.guild_id, **update_data)
        await self.bot.db.upsert_youtube_channel(
            guild_id=interaction.guild_id,
            channel_id=youtube_channel_id.strip(),
            channel_name=channel_name or "YouTube Channel",
        )

        embed = create_success_embed(
            title="Livestream Notifications Configured",
            description=(
                f"**YouTube Channel:** `{channel_name or youtube_channel_id}`\n"
                f"**Notification Channel:** {discord_channel.mention}\n"
                f"**Notification Role:** {notification_role.mention if notification_role else 'None'}\n"
                f"**Allow @everyone:** `{'Enabled' if allow_everyone else 'Disabled'}`\n"
            ),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="test", description="Send a mock livestream notification to test the alert appearance.")
    @is_guild_admin()
    async def live_test(self, interaction: discord.Interaction) -> None:
        """Send a sample livestream notification to the configured channel."""
        await interaction.response.defer(ephemeral=True)

        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        target_channel_id = settings.get("live_channel_id")
        if not target_channel_id:
            embed = create_warning_embed(
                title="Channel Not Configured",
                description="Please configure a notification channel first using `/live setup`.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        yt_record = await self.bot.db.get_youtube_channel(interaction.guild_id)
        channel_name = yt_record.get("channel_name") if yt_record else "Legend Gaming"

        # Generate mock broadcast
        mock_broadcast = self.yt_service.generate_mock_broadcast(
            channel_id=yt_record.get("channel_id") if yt_record else self.bot.config.youtube_channel_id,
            channel_title=channel_name,
            title="🔴 [TEST] Weekend Community Games & Live Ranked Matchmaking!",
            game_name="Valorant",
        )

        success = await self.send_livestream_alert(
            guild=interaction.guild,
            settings=settings,
            broadcast=mock_broadcast,
        )

        if success:
            embed = create_success_embed(
                title="Test Alert Sent",
                description=f"A sample notification has been dispatched to <#{target_channel_id}>.",
            )
        else:
            embed = create_error_embed(
                title="Delivery Failed",
                description="Failed to deliver the test notification. Ensure the bot has permissions in that channel.",
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="preview", description="Preview what the livestream notification will look like.")
    async def live_preview(self, interaction: discord.Interaction) -> None:
        """Show an ephemeral preview of the notification without posting to public channels."""
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        yt_record = await self.bot.db.get_youtube_channel(interaction.guild_id)
        channel_name = yt_record.get("channel_name") if yt_record else "Creator Name"

        mock_broadcast = self.yt_service.generate_mock_broadcast(
            channel_title=channel_name,
            title="🔴 [PREVIEW] Epic Livestream Gaming Session!",
            game_name="Apex Legends",
        )

        role_id = settings.get("live_role_id")
        allow_everyone = bool(settings.get("live_allow_everyone", 0))
        role_mention = "@everyone" if allow_everyone else (f"<@&{role_id}>" if role_id else "@Role")

        context = {
            "streamer": mock_broadcast.channel_title,
            "title": mock_broadcast.title,
            "url": mock_broadcast.url,
            "game": mock_broadcast.game_name or "Gaming",
            "role": role_mention,
        }

        template = settings.get("live_message_template") or "🔴 **{streamer}** is now LIVE!\n{url}"
        message_text = render_template(template, context)

        embed = create_live_notification_embed(
            streamer_name=mock_broadcast.channel_title,
            stream_title=mock_broadcast.title,
            stream_url=mock_broadcast.url,
            thumbnail_url=mock_broadcast.thumbnail_url,
            game_name=mock_broadcast.game_name,
        )

        await interaction.response.send_message(
            content=f"**[Notification Preview]**\n{message_text}",
            embed=embed,
            ephemeral=True,
        )

    @app_commands.command(name="check", description="Manually check YouTube right now for an active livestream.")
    async def live_check(self, interaction: discord.Interaction) -> None:
        """Trigger an immediate check of the configured YouTube channel."""
        await interaction.response.defer(ephemeral=True)

        if not self.bot.config.is_youtube_configured:
            embed = create_warning_embed(
                title="YouTube API Not Configured",
                description="The YouTube API key has not been configured in the bot's `.env`.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        yt_record = await self.bot.db.get_youtube_channel(interaction.guild_id)
        yt_channel_id = yt_record.get("channel_id") if yt_record else self.bot.config.youtube_channel_id

        if not yt_channel_id or yt_channel_id == "your_youtube_channel_id_here":
            embed = create_warning_embed(
                title="Channel Not Set",
                description="No YouTube channel configured. Set one with `/live setup`.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            broadcast = await self.yt_service.fetch_active_livestream(yt_channel_id)
            await self.bot.db.update_youtube_last_checked(interaction.guild_id, yt_channel_id)

            if broadcast:
                embed = create_live_notification_embed(
                    streamer_name=broadcast.channel_title,
                    stream_title=broadcast.title,
                    stream_url=broadcast.url,
                    thumbnail_url=broadcast.thumbnail_url,
                    game_name=broadcast.game_name,
                )
                await interaction.followup.send(
                    content=f"🟢 **{broadcast.channel_title}** is currently LIVE!",
                    embed=embed,
                    ephemeral=True,
                )
            else:
                embed = create_info_embed(
                    title="Channel Offline",
                    description=f"Channel `{yt_record.get('channel_name') if yt_record else yt_channel_id}` is not currently streaming.",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except YouTubeQuotaExceededError:
            embed = create_error_embed(
                title="Quota Exceeded",
                description="YouTube API daily quota is currently exceeded.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = create_error_embed(
                title="Check Failed",
                description=f"Error checking channel status: {e}",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="status", description="Show the current YouTube monitoring configuration and status.")
    async def live_status(self, interaction: discord.Interaction) -> None:
        """Display configuration and operational status for live notifications."""
        await interaction.response.defer(ephemeral=True)

        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        yt_record = await self.bot.db.get_youtube_channel(interaction.guild_id)
        last_announced = await self.bot.db.get_last_announced_broadcast(interaction.guild_id)

        target_channel_id = settings.get("live_channel_id")
        role_id = settings.get("live_role_id")
        allow_everyone = bool(settings.get("live_allow_everyone", 0))

        channel_display = f"<#{target_channel_id}>" if target_channel_id else "*Not configured*"
        role_display = f"<@&{role_id}>" if role_id else "*None*"
        everyone_display = "✅ Enabled" if allow_everyone else "❌ Disabled"

        yt_name = yt_record.get("channel_name") if yt_record else "*Default from .env*"
        yt_id = yt_record.get("channel_id") if yt_record else (self.bot.config.youtube_channel_id or "*Not set*")
        last_checked = yt_record.get("last_checked_at") if yt_record else "*Never*"

        last_stream = (
            f"**Title:** {last_announced.get('title')}\n**Notified:** `{last_announced.get('notified_at')}`"
            if last_announced
            else "*None recorded*"
        )

        embed = discord.Embed(
            title="🔴 YouTube Live Notification Status",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(name="📺 YouTube Channel", value=f"`{yt_name}`\nID: `{yt_id}`", inline=False)
        embed.add_field(name="📢 Discord Channel", value=channel_display, inline=True)
        embed.add_field(name="🔔 Notification Role", value=role_display, inline=True)
        embed.add_field(name="👥 @everyone Allowed", value=everyone_display, inline=True)
        embed.add_field(name="⏱️ Polling Interval", value=f"`{self.poll_interval}s`", inline=True)
        embed.add_field(name="🕒 Last Checked", value=f"`{last_checked}`", inline=True)
        embed.add_field(name="📡 Last Announced Stream", value=last_stream, inline=False)

        embed.set_footer(text="Legend Bot • YouTube Livestream System")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Extension entry point for YouTubeCog."""
    await bot.add_cog(YouTubeCog(bot))
