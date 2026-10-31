"""Customizable Welcome System cog, on_member_join listener, and /welcome commands."""

import logging
from typing import TYPE_CHECKING, Optional
import discord
from discord import app_commands
from discord.ext import commands

from src.ui.embeds import (
    create_error_embed,
    create_info_embed,
    create_success_embed,
    create_warning_embed,
    create_welcome_embed,
)
from src.utils.permissions import is_guild_admin
from src.utils.validators import (
    render_template,
    resolve_image_url,
    validate_hex_color,
    validate_template_placeholders,
    validate_url,
)

if TYPE_CHECKING:
    from src.main import LegendBot

logger = logging.getLogger("LegendBot.WelcomeCog")

ALLOWED_WELCOME_PLACEHOLDERS = {"user", "username", "server", "count"}


class WelcomeCog(commands.GroupCog, group_name="welcome", group_description="Custom welcome message and embed configuration"):
    """Cog handling automated new member greetings, custom embeds, and /welcome commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: "LegendBot" = bot  # type: ignore[assignment]

    # -------------------------------------------------------------
    # Event Listener (on_member_join)
    # -------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Triggered automatically whenever a new user joins a Discord server."""
        if member.bot:
            return

        settings = await self.bot.db.get_guild_settings(member.guild.id)
        if not settings.get("welcome_enabled", 0):
            return

        channel_id = settings.get("welcome_channel_id")
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Configured welcome channel %s not found in %s", channel_id, member.guild.name)
            return

        # Prepare dynamic placeholder context
        context = {
            "user": member.mention,
            "username": member.display_name,
            "server": member.guild.name,
            "count": str(member.guild.member_count or len(member.guild.members)),
        }

        # Render message text and embed fields
        msg_template = settings.get("welcome_message") or "Welcome to {server}, {user}!"
        rendered_message = render_template(msg_template, context)

        title = render_template(settings.get("welcome_embed_title") or "Welcome to the Community!", context)
        description = render_template(settings.get("welcome_embed_description") or "Hey {user}, welcome!", context)
        footer = render_template(settings.get("welcome_footer") or "Member #{count}", context)

        # Parse color
        color_str = settings.get("welcome_embed_color", "#5865F2")
        valid_color, color_int = validate_hex_color(color_str)
        if not valid_color or color_int is None:
            color_int = 0x5865F2

        # Determine thumbnail and banner image
        custom_thumb = settings.get("welcome_thumbnail_url")
        thumbnail_url = custom_thumb if custom_thumb else member.display_avatar.url
        image_url = settings.get("welcome_image_url")

        embed = create_welcome_embed(
            title=title,
            description=description,
            color_int=color_int,
            footer_text=footer,
            thumbnail_url=thumbnail_url,
            image_url=image_url,
        )

        # Restrict mentions so welcome messages only ping the joined member
        allowed_mentions = discord.AllowedMentions(
            users=[member],
            roles=False,
            everyone=False,
        )

        try:
            await channel.send(
                content=rendered_message,
                embed=embed,
                allowed_mentions=allowed_mentions,
            )
            logger.info("Sent welcome message for %s in #%s (%s)", member.name, channel.name, member.guild.name)
        except discord.Forbidden:
            logger.error("Missing permissions to send welcome message in #%s (%d)", channel.name, channel.id)
        except Exception as e:
            logger.error("Error sending welcome message: %s", e, exc_info=True)

    # -------------------------------------------------------------
    # Slash Commands (/welcome ...)
    # -------------------------------------------------------------

    @app_commands.command(name="channel", description="Set the channel where welcome messages are posted.")
    @app_commands.describe(channel="The Discord text channel to send welcome messages to")
    @is_guild_admin()
    async def welcome_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        """Configure the welcome channel and enable greetings."""
        await interaction.response.defer(ephemeral=True)

        await self.bot.db.update_guild_settings(
            interaction.guild_id,
            welcome_channel_id=channel.id,
            welcome_enabled=1,
        )

        embed = create_success_embed(
            title="Welcome Channel Configured",
            description=f"Welcome messages will now be posted in {channel.mention}.\nWelcome system has been **enabled** automatically.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="enable", description="Enable automated welcome messages for new members.")
    @is_guild_admin()
    async def welcome_enable(self, interaction: discord.Interaction) -> None:
        """Turn on welcome messages."""
        await interaction.response.defer(ephemeral=True)

        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        if not settings.get("welcome_channel_id"):
            embed = create_warning_embed(
                title="Channel Not Set",
                description="Please configure a welcome channel first using `/welcome channel`.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await self.bot.db.update_guild_settings(interaction.guild_id, welcome_enabled=1)
        embed = create_success_embed(
            title="Welcome System Enabled",
            description="New members will now receive greeting messages and embeds.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="disable", description="Disable automated welcome messages.")
    @is_guild_admin()
    async def welcome_disable(self, interaction: discord.Interaction) -> None:
        """Turn off welcome messages."""
        await interaction.response.defer(ephemeral=True)

        await self.bot.db.update_guild_settings(interaction.guild_id, welcome_enabled=0)
        embed = create_info_embed(
            title="Welcome System Disabled",
            description="Welcome messages have been turned off. You can re-enable them anytime with `/welcome enable`.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="message", description="Customize the text message template sent above the welcome embed.")
    @app_commands.describe(template="Message template. Supported variables: {user}, {username}, {server}, {count}")
    @is_guild_admin()
    async def welcome_message(self, interaction: discord.Interaction, template: str) -> None:
        """Set custom text template for welcome messages."""
        await interaction.response.defer(ephemeral=True)

        is_valid, invalid_tokens = validate_template_placeholders(template, ALLOWED_WELCOME_PLACEHOLDERS)
        if not is_valid:
            embed = create_error_embed(
                title="Invalid Template Placeholders",
                description=(
                    f"Unsupported variables: {', '.join(f'`{{{t}}}`' for t in invalid_tokens)}\n"
                    f"Supported variables: {', '.join(f'`{{{t}}}`' for t in ALLOWED_WELCOME_PLACEHOLDERS)}"
                ),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await self.bot.db.update_guild_settings(interaction.guild_id, welcome_message=template)
        embed = create_success_embed(
            title="Welcome Message Template Updated",
            description=f"**New Template:**\n>>> {template}",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="embed", description="Customize the welcome embed appearance (title, description, color, images).")
    @app_commands.describe(
        title="(Optional) Embed title. Supports: {user}, {username}, {server}, {count}",
        description="(Optional) Embed body text. Supports variables",
        color="(Optional) Hex color code (e.g. #5865F2, #FF0000)",
        thumbnail_url="(Optional) Direct HTTPS image URL for embed thumbnail",
        image_url="(Optional) Direct HTTPS banner image URL",
        footer="(Optional) Embed footer text. Supports: {count}",
    )
    @is_guild_admin()
    async def welcome_embed(
        self,
        interaction: discord.Interaction,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        image_url: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> None:
        """Configure welcome embed attributes."""
        await interaction.response.defer(ephemeral=True)

        updates = {}

        if title:
            is_valid, inv = validate_template_placeholders(title, ALLOWED_WELCOME_PLACEHOLDERS)
            if not is_valid:
                embed = create_error_embed("Invalid Title Variables", f"Unknown variables: {', '.join(inv)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            updates["welcome_embed_title"] = title

        if description:
            is_valid, inv = validate_template_placeholders(description, ALLOWED_WELCOME_PLACEHOLDERS)
            if not is_valid:
                embed = create_error_embed("Invalid Description Variables", f"Unknown variables: {', '.join(inv)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            updates["welcome_embed_description"] = description

        if footer:
            is_valid, inv = validate_template_placeholders(footer, ALLOWED_WELCOME_PLACEHOLDERS)
            if not is_valid:
                embed = create_error_embed("Invalid Footer Variables", f"Unknown variables: {', '.join(inv)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            updates["welcome_footer"] = footer

        if color:
            is_valid, _ = validate_hex_color(color)
            if not is_valid:
                embed = create_error_embed(
                    "Invalid Hex Color",
                    "Please provide a valid 6-character hex color code (e.g. `#5865F2` or `FF0055`).",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            updates["welcome_embed_color"] = color.upper()

        if thumbnail_url:
            clean_t = thumbnail_url.strip()
            if clean_t.lower() in {"none", "remove", "clear", "reset", "delete"}:
                updates["welcome_thumbnail_url"] = None
            else:
                resolved_thumb = await resolve_image_url(clean_t)
                if not validate_url(resolved_thumb):
                    embed = create_error_embed("Invalid Thumbnail URL", "Could not parse this image link. Please provide a direct image URL, Pinterest link, or Imgur link.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                updates["welcome_thumbnail_url"] = resolved_thumb

        if image_url:
            clean_i = image_url.strip()
            if clean_i.lower() in {"none", "remove", "clear", "reset", "delete"}:
                updates["welcome_image_url"] = None
            else:
                resolved_img = await resolve_image_url(clean_i)
                if not validate_url(resolved_img):
                    embed = create_error_embed("Invalid Banner URL", "Could not parse this image link. Please provide a direct image URL, Pinterest link, or Imgur link.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                updates["welcome_image_url"] = resolved_img

        if not updates:
            embed = create_warning_embed("No Changes Specified", "Please provide at least one field to update.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await self.bot.db.update_guild_settings(interaction.guild_id, **updates)
        embed = create_success_embed(
            title="Welcome Embed Updated",
            description=f"Successfully updated {len(updates)} embed attribute(s). Use `/welcome preview` to view the changes.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="preview", description="Preview what the welcome message and embed will look like.")
    async def welcome_preview(self, interaction: discord.Interaction) -> None:
        """Generate an ephemeral preview of the configured welcome greeting."""
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)

        context = {
            "user": interaction.user.mention,
            "username": interaction.user.display_name,
            "server": interaction.guild.name if interaction.guild else "Gaming Guild",
            "count": str(interaction.guild.member_count if interaction.guild else 100),
        }

        msg_template = settings.get("welcome_message") or "Welcome to {server}, {user}!"
        rendered_message = render_template(msg_template, context)

        title = render_template(settings.get("welcome_embed_title") or "Welcome to the Community!", context)
        description = render_template(settings.get("welcome_embed_description") or "Hey {user}, welcome!", context)
        footer = render_template(settings.get("welcome_footer") or "Member #{count}", context)

        color_str = settings.get("welcome_embed_color", "#5865F2")
        valid_color, color_int = validate_hex_color(color_str)
        if not valid_color or color_int is None:
            color_int = 0x5865F2

        custom_thumb = settings.get("welcome_thumbnail_url")
        thumbnail_url = custom_thumb if custom_thumb else (interaction.user.avatar.url if interaction.user.avatar else None)
        image_url = settings.get("welcome_image_url")

        embed = create_welcome_embed(
            title=title,
            description=description,
            color_int=color_int,
            footer_text=footer,
            thumbnail_url=thumbnail_url,
            image_url=image_url,
        )

        status_text = "🟢 **Enabled**" if settings.get("welcome_enabled", 0) else "🔴 **Disabled**"
        channel_id = settings.get("welcome_channel_id")
        channel_text = f"<#{channel_id}>" if channel_id else "*Not configured*"

        await interaction.response.send_message(
            content=f"**[Welcome Preview]** (Status: {status_text} | Channel: {channel_text})\n{rendered_message}",
            embed=embed,
            ephemeral=True,
        )

    @app_commands.command(name="reset", description="Reset welcome configuration back to default settings.")
    @is_guild_admin()
    async def welcome_reset(self, interaction: discord.Interaction) -> None:
        """Reset all welcome parameters for this server."""
        await interaction.response.defer(ephemeral=True)

        await self.bot.db.reset_welcome_settings(interaction.guild_id)
        embed = create_success_embed(
            title="Welcome Settings Reset",
            description="Welcome settings have been restored to their original factory defaults. The system is currently disabled.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Extension entry point for WelcomeCog."""
    await bot.add_cog(WelcomeCog(bot))
