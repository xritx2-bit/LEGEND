"""Customizable Welcome System cog, on_member_join listener, and /welcome commands."""

import logging
from typing import TYPE_CHECKING, List, Optional
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
    ALLOWED_WELCOME_PLACEHOLDERS,
    render_template,
    resolve_image_url,
    validate_hex_color,
    validate_template_placeholders,
    validate_url,
)

if TYPE_CHECKING:
    from src.main import LegendBot

logger = logging.getLogger("LegendBot.WelcomeCog")


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
        logger.info(
            "on_member_join event received: member=%s (ID: %d, bot=%s) guild=%s (ID: %d)",
            member.name,
            member.id,
            member.bot,
            member.guild.name,
            member.guild.id,
        )

        # Do not welcome self if the bot itself joined
        if getattr(self.bot, "user", None) and member.id == self.bot.user.id:
            logger.info("Ignoring join event for self (%s)", member.name)
            return

        settings = await self.bot.db.get_guild_settings(member.guild.id)
        if not settings.get("welcome_enabled", 0):
            logger.info("Welcome greetings are disabled for %s", member.guild.name)
            return

        channel_id = settings.get("welcome_channel_id")
        if not channel_id:
            logger.warning("No welcome_channel_id configured in guild %s", member.guild.name)
            return

        channel = member.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                logger.error("Could not fetch welcome channel %s in %s: %s", channel_id, member.guild.name, e)
                return

        if not hasattr(channel, "send"):
            logger.warning("Configured welcome channel %s in %s does not support sending messages", channel_id, member.guild.name)
            return

        # Extract avatar, guild icon, and guild banner URLs
        avatar_url = member.display_avatar.url
        icon_url = member.guild.icon.url if member.guild.icon else avatar_url
        banner_url = member.guild.banner.url if member.guild.banner else ""

        # Prepare dynamic placeholder context
        context = {
            "user": member.mention,
            "username": member.display_name,
            "server": member.guild.name,
            "count": str(member.guild.member_count or len(member.guild.members)),
            "user_avatar": avatar_url,
            "avatar": avatar_url,
            "server_icon": icon_url,
            "icon": icon_url,
            "server_banner": banner_url,
            "banner": banner_url,
            "user_banner": member.banner.url if getattr(member, "banner", None) else "",
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

        # Determine thumbnail and banner image (supports {user_avatar}, {server_icon}, and URLs)
        raw_thumb = settings.get("welcome_thumbnail_url")
        if raw_thumb:
            rendered_thumb = render_template(raw_thumb, context).strip()
            thumbnail_url = rendered_thumb if rendered_thumb else avatar_url
        else:
            thumbnail_url = avatar_url

        raw_image = settings.get("welcome_image_url")
        if raw_image:
            rendered_image = render_template(raw_image, context).strip()
            image_url = rendered_image if rendered_image else None
        else:
            image_url = None

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
            msg = await channel.send(
                content=rendered_message,
                embed=embed,
                allowed_mentions=allowed_mentions,
            )
            logger.info("Successfully sent welcome message (ID: %d) for %s in #%s (%s)", msg.id, member.name, getattr(channel, "name", "channel"), member.guild.name)
        except discord.Forbidden:
            logger.error("Missing permissions to send welcome message in #%s (%d)", getattr(channel, "name", "channel"), channel_id)
        except Exception as e:
            logger.error("Error sending welcome message in #%s: %s", getattr(channel, "name", "channel"), e, exc_info=True)

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

    @app_commands.command(name="embed", description="Customize welcome embed (title, description, color, thumbnail, banner, footer).")
    @app_commands.describe(
        title="(Optional) Embed title. Supports: {user}, {username}, {server}, {count}",
        description="(Optional) Embed body text. Supports variables",
        color="(Optional) Hex color code (e.g. #5865F2, #FF0000)",
        thumbnail="(Optional) URL, photo link, or embed variable ({user_avatar}, {server_icon})",
        image="(Optional) Banner URL, photo link, or embed variable ({server_banner})",
        footer="(Optional) Embed footer text. Supports: {count}",
    )
    @is_guild_admin()
    async def welcome_embed(
        self,
        interaction: discord.Interaction,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        thumbnail: Optional[str] = None,
        image: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> None:
        """Configure welcome embed attributes."""
        await interaction.response.defer(ephemeral=True)

        logger.info(
            "welcome_embed called by %s (guild: %s): title=%r, color=%r, thumb=%r, img=%r",
            interaction.user.name,
            interaction.guild_id,
            title,
            color,
            thumbnail,
            image,
        )

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

        # Handle Thumbnail (accepts: {user_avatar}, {server_icon}, image links, or "none")
        if thumbnail is not None:
            clean_t = thumbnail.strip()
            if clean_t.lower() in {"none", "remove", "clear", "reset", "delete"}:
                updates["welcome_thumbnail_url"] = None
            elif any(f"{{{token}}}" in clean_t for token in ALLOWED_WELCOME_PLACEHOLDERS):
                is_valid, inv = validate_template_placeholders(clean_t, ALLOWED_WELCOME_PLACEHOLDERS)
                if not is_valid:
                    embed = create_error_embed(
                        "Invalid Thumbnail Variables",
                        f"Unknown variables: {', '.join(inv)}\n"
                        f"Supported variables: `{{user_avatar}}`, `{{server_icon}}`, `{{server_banner}}`",
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                updates["welcome_thumbnail_url"] = clean_t
            else:
                resolved_thumb = await resolve_image_url(clean_t)
                if not validate_url(resolved_thumb):
                    embed = create_error_embed(
                        "Invalid Thumbnail",
                        "Could not parse this thumbnail value.\n\n"
                        "💡 **Supported Options:**\n"
                        "• **Embed Variables**: `{{user_avatar}}` (new member's avatar), `{{server_icon}}`\n"
                        "• **Image Links**: Direct image URL (.png, .jpg, .webp), Pinterest link, or Discord image link\n"
                        "• **Direct Upload**: Use `/welcome upload target:Thumbnail` to upload from your device\n"
                        "• **Reset**: Type `none` to revert to member avatar",
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                updates["welcome_thumbnail_url"] = resolved_thumb

        # Handle Banner Image (accepts: {server_banner}, {server_icon}, image links, or "none")
        if image is not None:
            clean_i = image.strip()
            if clean_i.lower() in {"none", "remove", "clear", "reset", "delete"}:
                updates["welcome_image_url"] = None
            elif any(f"{{{token}}}" in clean_i for token in ALLOWED_WELCOME_PLACEHOLDERS):
                is_valid, inv = validate_template_placeholders(clean_i, ALLOWED_WELCOME_PLACEHOLDERS)
                if not is_valid:
                    embed = create_error_embed(
                        "Invalid Banner Variables",
                        f"Unknown variables: {', '.join(inv)}\n"
                        f"Supported variables: `{{server_banner}}`, `{{server_icon}}`, `{{user_avatar}}`",
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                updates["welcome_image_url"] = clean_i
            else:
                resolved_img = await resolve_image_url(clean_i)
                if not validate_url(resolved_img):
                    embed = create_error_embed(
                        "Invalid Banner Image",
                        "Could not parse this banner value.\n\n"
                        "💡 **Supported Options:**\n"
                        "• **Embed Variables**: `{{server_banner}}`, `{{server_icon}}`\n"
                        "• **Image Links**: Direct image URL (.png, .jpg, .webp), Pinterest link, or Discord image link\n"
                        "• **Direct Upload**: Use `/welcome upload target:Banner` to upload from your device\n"
                        "• **Reset**: Type `none` to remove the banner",
                    )
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

    @welcome_embed.autocomplete("thumbnail")
    async def thumbnail_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Smart autocomplete suggestions for welcome embed thumbnail."""
        choices = [
            app_commands.Choice(name="👤 {user_avatar} - New member's profile avatar", value="{user_avatar}"),
            app_commands.Choice(name="🏰 {server_icon} - Server icon", value="{server_icon}"),
            app_commands.Choice(name="🚩 {server_banner} - Server banner", value="{server_banner}"),
            app_commands.Choice(name="❌ none - Revert to member avatar", value="none"),
        ]
        if not current:
            return choices
        return [c for c in choices if current.lower() in c.name.lower() or current.lower() in c.value.lower()]

    @welcome_embed.autocomplete("image")
    async def image_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Smart autocomplete suggestions for welcome embed banner."""
        choices = [
            app_commands.Choice(name="🚩 {server_banner} - Server banner", value="{server_banner}"),
            app_commands.Choice(name="🏰 {server_icon} - Server icon", value="{server_icon}"),
            app_commands.Choice(name="👤 {user_avatar} - Member's avatar", value="{user_avatar}"),
            app_commands.Choice(name="❌ none - Remove banner", value="none"),
        ]
        if not current:
            return choices
        return [c for c in choices if current.lower() in c.name.lower() or current.lower() in c.value.lower()]

    @app_commands.command(name="upload", description="Upload an image file directly from your device for the thumbnail or banner.")
    @app_commands.describe(
        target="Choose whether to set this image as the thumbnail or banner",
        file="Select an image file from your device (PNG, JPG, WEBP, GIF)",
    )
    @app_commands.choices(
        target=[
            app_commands.Choice(name="Thumbnail (Top-right avatar/icon)", value="thumbnail"),
            app_commands.Choice(name="Banner (Large bottom embed image)", value="banner"),
        ]
    )
    @is_guild_admin()
    async def welcome_upload(
        self,
        interaction: discord.Interaction,
        target: str,
        file: discord.Attachment,
    ) -> None:
        """Upload an image file directly from device for thumbnail or banner."""
        await interaction.response.defer(ephemeral=True)

        if file.content_type and not file.content_type.startswith("image/"):
            embed = create_error_embed(
                "Invalid File Type",
                "Please upload a valid image file (PNG, JPG, WEBP, or GIF).",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if target == "thumbnail":
            await self.bot.db.update_guild_settings(interaction.guild_id, welcome_thumbnail_url=file.url)
            embed = create_success_embed(
                title="Thumbnail Uploaded",
                description="Your uploaded image has been set as the welcome embed thumbnail.\nUse `/welcome preview` to see it in action.",
            )
        else:
            await self.bot.db.update_guild_settings(interaction.guild_id, welcome_image_url=file.url)
            embed = create_success_embed(
                title="Banner Uploaded",
                description="Your uploaded image has been set as the welcome embed banner.\nUse `/welcome preview` to see it in action.",
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="preview", description="Preview what the welcome message and embed will look like.")
    async def welcome_preview(self, interaction: discord.Interaction) -> None:
        """Generate an ephemeral preview of the configured welcome greeting."""
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)

        avatar_url = interaction.user.display_avatar.url
        icon_url = interaction.guild.icon.url if (interaction.guild and interaction.guild.icon) else avatar_url
        banner_url = interaction.guild.banner.url if (interaction.guild and interaction.guild.banner) else ""

        context = {
            "user": interaction.user.mention,
            "username": interaction.user.display_name,
            "server": interaction.guild.name if interaction.guild else "Gaming Guild",
            "count": str(interaction.guild.member_count if interaction.guild else 100),
            "user_avatar": avatar_url,
            "avatar": avatar_url,
            "server_icon": icon_url,
            "icon": icon_url,
            "server_banner": banner_url,
            "banner": banner_url,
            "user_banner": interaction.user.banner.url if getattr(interaction.user, "banner", None) else "",
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

        raw_thumb = settings.get("welcome_thumbnail_url")
        if raw_thumb:
            rendered_thumb = render_template(raw_thumb, context).strip()
            thumbnail_url = rendered_thumb if rendered_thumb else avatar_url
        else:
            thumbnail_url = avatar_url

        raw_image = settings.get("welcome_image_url")
        if raw_image:
            rendered_image = render_template(raw_image, context).strip()
            image_url = rendered_image if rendered_image else None
        else:
            image_url = None

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

    @app_commands.command(name="test", description="Send a test welcome greeting to your configured welcome channel right now.")
    @is_guild_admin()
    async def welcome_test(self, interaction: discord.Interaction) -> None:
        """Simulate a new member join and send a real welcome message to the welcome channel."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            embed = create_error_embed("Server Only", "This command can only be used in a server.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        channel_id = settings.get("welcome_channel_id")
        if not channel_id:
            embed = create_warning_embed(
                "Welcome Channel Not Set",
                "Please configure a welcome channel first using `/welcome channel #channel`.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                embed = create_error_embed("Channel Error", f"Could not find or access configured welcome channel (`{channel_id}`): {e}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        if not hasattr(channel, "send"):
            embed = create_error_embed("Invalid Channel", f"<#{channel_id}> does not support sending text messages.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Prepare dynamic context using interaction user
        member = interaction.user
        avatar_url = member.display_avatar.url
        icon_url = interaction.guild.icon.url if interaction.guild.icon else avatar_url
        banner_url = interaction.guild.banner.url if interaction.guild.banner else ""

        context = {
            "user": member.mention,
            "username": member.display_name,
            "server": interaction.guild.name,
            "count": str(interaction.guild.member_count or len(interaction.guild.members)),
            "user_avatar": avatar_url,
            "avatar": avatar_url,
            "server_icon": icon_url,
            "icon": icon_url,
            "server_banner": banner_url,
            "banner": banner_url,
            "user_banner": member.banner.url if getattr(member, "banner", None) else "",
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

        raw_thumb = settings.get("welcome_thumbnail_url")
        if raw_thumb:
            rendered_thumb = render_template(raw_thumb, context).strip()
            thumbnail_url = rendered_thumb if rendered_thumb else avatar_url
        else:
            thumbnail_url = avatar_url

        raw_image = settings.get("welcome_image_url")
        if raw_image:
            rendered_image = render_template(raw_image, context).strip()
            image_url = rendered_image if rendered_image else None
        else:
            image_url = None

        embed = create_welcome_embed(
            title=title,
            description=description,
            color_int=color_int,
            footer_text=footer,
            thumbnail_url=thumbnail_url,
            image_url=image_url,
        )

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
            success_embed = create_success_embed(
                "Welcome Message Test Sent",
                f"✅ A test welcome message and embed were successfully posted to <#{channel_id}>!\nHead over to <#{channel_id}> to view your live embed.",
            )
            await interaction.followup.send(embed=success_embed, ephemeral=True)
        except discord.Forbidden:
            error_embed = create_error_embed(
                "Missing Permissions in Welcome Channel",
                f"I don't have permission to send messages or embeds in <#{channel_id}>.\n"
                f"Please ensure the bot has **View Channel**, **Send Messages**, and **Embed Links** permissions in that channel.",
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = create_error_embed(
                "Error Sending Test Message",
                f"An error occurred while posting to <#{channel_id}>:\n```{e}```",
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

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
