"""Interactive Discord UI views, buttons, select menus, and modals for /setup dashboard."""

import json
from typing import TYPE_CHECKING, Any, Dict, Optional
import discord
from discord import ui

from src.ui.embeds import (
    create_error_embed,
    create_info_embed,
    create_live_notification_embed,
    create_success_embed,
    create_welcome_embed,
)
from src.utils.validators import (
    render_template,
    resolve_image_url,
    validate_hex_color,
    validate_template_placeholders,
    validate_url,
)

if TYPE_CHECKING:
    from src.main import LegendBot

ALLOWED_WELCOME_VARS = {"user", "username", "server", "count"}
ALLOWED_LIVE_VARS = {"streamer", "title", "url", "game", "role"}


# -------------------------------------------------------------
# Modals for Text Configuration
# -------------------------------------------------------------

class EditWelcomeMessageModal(ui.Modal, title="Edit Welcome Message Template"):
    """Modal to edit the text template sent above welcome embeds."""
    template_input = ui.TextInput(
        label="Message Template",
        style=discord.TextStyle.paragraph,
        placeholder="Welcome to {server}, {user}! We are glad you are here.",
        required=True,
        max_length=500,
    )

    def __init__(self, bot: "LegendBot", current_template: str) -> None:
        super().__init__()
        self.bot = bot
        self.template_input.default = current_template

    async def on_submit(self, interaction: discord.Interaction) -> None:
        val = self.template_input.value.strip()
        is_valid, invalid = validate_template_placeholders(val, ALLOWED_WELCOME_VARS)
        if not is_valid:
            embed = create_error_embed(
                title="Invalid Variables",
                description=f"Unsupported variables: {', '.join(f'`{{{v}}}`' for v in invalid)}\n"
                            f"Supported variables: {', '.join(f'`{{{v}}}`' for v in ALLOWED_WELCOME_VARS)}",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await self.bot.db.update_guild_settings(interaction.guild_id, welcome_message=val)
        embed = create_success_embed("Welcome Template Saved", f"New template:\n>>> {val}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditWelcomeEmbedModal(ui.Modal, title="Customize Welcome Embed"):
    """Modal to edit welcome embed title, description, color, banner, and thumbnail."""
    embed_title = ui.TextInput(
        label="Embed Title",
        style=discord.TextStyle.short,
        placeholder="Welcome to the Community!",
        required=False,
        max_length=200,
    )
    embed_desc = ui.TextInput(
        label="Embed Description",
        style=discord.TextStyle.paragraph,
        placeholder="Hey {user}, welcome! Check out the channels.",
        required=False,
        max_length=1000,
    )
    embed_color = ui.TextInput(
        label="Hex Color (e.g. #5865F2)",
        style=discord.TextStyle.short,
        placeholder="#5865F2",
        required=False,
        max_length=7,
    )
    embed_image = ui.TextInput(
        label="Banner Image URL (Pinterest, Imgur, direct link)",
        style=discord.TextStyle.short,
        placeholder="https://... (Pinterest pin, Imgur, direct image URL)",
        required=False,
        max_length=500,
    )
    embed_thumb = ui.TextInput(
        label="Thumbnail URL (Leave blank for user avatar)",
        style=discord.TextStyle.short,
        placeholder="https://... (Optional custom thumbnail)",
        required=False,
        max_length=500,
    )

    def __init__(self, bot: "LegendBot", settings: Dict[str, Any]) -> None:
        super().__init__()
        self.bot = bot
        self.embed_title.default = settings.get("welcome_embed_title") or "Welcome to the Community!"
        self.embed_desc.default = settings.get("welcome_embed_description") or "Hey {user}, welcome!"
        self.embed_color.default = settings.get("welcome_embed_color") or "#5865F2"
        self.embed_image.default = settings.get("welcome_image_url") or ""
        self.embed_thumb.default = settings.get("welcome_thumbnail_url") or ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updates = {}
        t_val = self.embed_title.value.strip()
        if t_val:
            is_valid, inv = validate_template_placeholders(t_val, ALLOWED_WELCOME_VARS)
            if not is_valid:
                embed = create_error_embed("Invalid Title Variables", f"Unknown: {', '.join(inv)}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            updates["welcome_embed_title"] = t_val

        d_val = self.embed_desc.value.strip()
        if d_val:
            is_valid, inv = validate_template_placeholders(d_val, ALLOWED_WELCOME_VARS)
            if not is_valid:
                embed = create_error_embed("Invalid Description Variables", f"Unknown: {', '.join(inv)}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            updates["welcome_embed_description"] = d_val

        c_val = self.embed_color.value.strip()
        if c_val:
            is_valid, _ = validate_hex_color(c_val)
            if not is_valid:
                embed = create_error_embed("Invalid Color", "Please enter a valid 6-char hex code (e.g. `#5865F2`).")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            updates["welcome_embed_color"] = c_val.upper()

        img_val = self.embed_image.value.strip()
        if img_val:
            if img_val.lower() in {"none", "remove", "clear", "reset", "delete"}:
                updates["welcome_image_url"] = None
            else:
                resolved_img = await resolve_image_url(img_val)
                if not validate_url(resolved_img):
                    embed = create_error_embed(
                        "Invalid Banner Image",
                        "Could not parse this image link.\n\n"
                        "💡 **Tips:**\n"
                        "• Use a direct image URL (.png, .jpg, .webp, .gif) or Imgur/Discord link.\n"
                        "• For Pinterest: right-click the image and choose **'Copy image address'** (starts with `i.pinimg.com`).\n"
                        "• Or run `/welcome embed` with `image_file` to upload your image file directly!"
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                updates["welcome_image_url"] = resolved_img

        thumb_val = self.embed_thumb.value.strip()
        if thumb_val:
            if thumb_val.lower() in {"none", "remove", "clear", "reset", "delete"}:
                updates["welcome_thumbnail_url"] = None
            else:
                resolved_thumb = await resolve_image_url(thumb_val)
                if not validate_url(resolved_thumb):
                    embed = create_error_embed(
                        "Invalid Thumbnail Image",
                        "Could not parse this image link.\n\n"
                        "💡 **Tips:**\n"
                        "• Use a direct image URL (.png, .jpg, .webp, .gif) or Imgur/Discord link.\n"
                        "• For Pinterest: right-click the image and choose **'Copy image address'** (starts with `i.pinimg.com`).\n"
                        "• Or run `/welcome embed` with `thumbnail_file` to upload your image file directly!"
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                updates["welcome_thumbnail_url"] = resolved_thumb

        if updates:
            await self.bot.db.update_guild_settings(interaction.guild_id, **updates)
            embed = create_success_embed("Welcome Embed Saved", "Your welcome embed appearance settings have been updated.")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EditLiveTemplateModal(ui.Modal, title="Edit Livestream Message"):
    """Modal to edit livestream message template."""
    live_msg_input = ui.TextInput(
        label="Notification Message Template",
        style=discord.TextStyle.paragraph,
        placeholder="🔴 **{streamer}** is now LIVE!\nWatch here: {url}",
        required=True,
        max_length=500,
    )

    def __init__(self, bot: "LegendBot", current_template: str) -> None:
        super().__init__()
        self.bot = bot
        self.live_msg_input.default = current_template

    async def on_submit(self, interaction: discord.Interaction) -> None:
        val = self.live_msg_input.value.strip()
        is_valid, invalid = validate_template_placeholders(val, ALLOWED_LIVE_VARS)
        if not is_valid:
            embed = create_error_embed(
                title="Invalid Variables",
                description=f"Unsupported variables: {', '.join(f'`{{{v}}}`' for v in invalid)}\n"
                            f"Supported variables: {', '.join(f'`{{{v}}}`' for v in ALLOWED_LIVE_VARS)}",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await self.bot.db.update_guild_settings(interaction.guild_id, live_message_template=val)
        embed = create_success_embed("Livestream Template Saved", f"New alert template:\n>>> {val}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# -------------------------------------------------------------
# Category Dashboard View
# -------------------------------------------------------------

class SetupCategorySelect(ui.Select):
    """Dropdown menu to switch between dashboard categories."""

    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="YouTube Livestream Alerts", value="youtube", emoji="🔴", description="Configure livestream notifications, channels, and roles"),
            discord.SelectOption(label="Welcome Messages", value="welcome", emoji="👋", description="Configure automated greetings, templates, and embeds"),
            discord.SelectOption(label="Appearance & Branding", value="appearance", emoji="🎨", description="Embed colors, banners, and gaming theme"),
            discord.SelectOption(label="Backup & Data Management", value="backup", emoji="💾", description="Export configuration backups and restore defaults"),
        ]
        super().__init__(placeholder="Select a settings category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: "SetupDashboardView" = self.view  # type: ignore
        category = self.values[0]
        view.current_category = category
        view.update_components()
        embed = await view.build_category_embed(interaction.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)


class SetupDashboardView(ui.View):
    """Main interactive /setup control panel with dropdowns and buttons."""

    def __init__(self, bot: "LegendBot", guild_id: int, initial_category: str = "youtube") -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.current_category = initial_category
        self.update_components()

    def update_components(self) -> None:
        """Dynamically refresh buttons and select menus based on current category."""
        self.clear_items()
        self.add_item(SetupCategorySelect())

        if self.current_category == "youtube":
            btn_edit_msg = ui.Button(label="Edit Alert Message", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="btn_yt_msg")
            btn_edit_msg.callback = self.handle_edit_yt_msg
            self.add_item(btn_edit_msg)

            btn_toggle_everyone = ui.Button(label="Toggle @everyone", style=discord.ButtonStyle.secondary, emoji="🔔", custom_id="btn_yt_everyone")
            btn_toggle_everyone.callback = self.handle_toggle_everyone
            self.add_item(btn_toggle_everyone)

            btn_preview_yt = ui.Button(label="Preview Live Alert", style=discord.ButtonStyle.success, emoji="👁️", custom_id="btn_yt_prev")
            btn_preview_yt.callback = self.handle_preview_yt
            self.add_item(btn_preview_yt)

        elif self.current_category == "welcome":
            btn_toggle_welcome = ui.Button(label="Toggle Welcome (On/Off)", style=discord.ButtonStyle.secondary, emoji="🔘", custom_id="btn_w_toggle")
            btn_toggle_welcome.callback = self.handle_toggle_welcome
            self.add_item(btn_toggle_welcome)

            btn_edit_msg = ui.Button(label="Edit Welcome Message", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="btn_w_msg")
            btn_edit_msg.callback = self.handle_edit_welcome_msg
            self.add_item(btn_edit_msg)

            btn_edit_embed = ui.Button(label="Edit Welcome Embed", style=discord.ButtonStyle.primary, emoji="🎨", custom_id="btn_w_embed")
            btn_edit_embed.callback = self.handle_edit_welcome_embed
            self.add_item(btn_edit_embed)

            btn_preview_w = ui.Button(label="Preview Greeting", style=discord.ButtonStyle.success, emoji="👁️", custom_id="btn_w_prev")
            btn_preview_w.callback = self.handle_preview_welcome
            self.add_item(btn_preview_w)

        elif self.current_category == "appearance":
            btn_color = ui.Button(label="Edit Embed Colors", style=discord.ButtonStyle.primary, emoji="🎨", custom_id="btn_app_color")
            btn_color.callback = self.handle_edit_welcome_embed
            self.add_item(btn_color)

        elif self.current_category == "backup":
            btn_export = ui.Button(label="Export Config (JSON)", style=discord.ButtonStyle.primary, emoji="📥", custom_id="btn_b_export")
            btn_export.callback = self.handle_export_backup
            self.add_item(btn_export)

            btn_reset_w = ui.Button(label="Reset Welcome Settings", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="btn_b_reset_w")
            btn_reset_w.callback = self.handle_reset_welcome
            self.add_item(btn_reset_w)

    async def build_category_embed(self, guild_id: int) -> discord.Embed:
        """Construct the visual embed representing the chosen settings category."""
        settings = await self.bot.db.get_guild_settings(guild_id)

        if self.current_category == "youtube":
            yt_rec = await self.bot.db.get_youtube_channel(guild_id)
            c_id = settings.get("live_channel_id")
            r_id = settings.get("live_role_id")
            everyone = bool(settings.get("live_allow_everyone", 0))

            embed = discord.Embed(
                title="🔴 YouTube Livestream Notification Settings",
                description="Manage your YouTube channel live alerts, target Discord channel, and ping roles.",
                color=discord.Color.red(),
            )
            embed.add_field(name="YouTube Channel", value=f"`{yt_rec.get('channel_name') if yt_rec else 'Default from .env'}`\nID: `{yt_rec.get('channel_id') if yt_rec else self.bot.config.youtube_channel_id}`", inline=False)
            embed.add_field(name="Alert Channel", value=f"<#{c_id}>" if c_id else "*Not configured*", inline=True)
            embed.add_field(name="Ping Role", value=f"<@&{r_id}>" if r_id else "*None*", inline=True)
            embed.add_field(name="@everyone Pings", value="✅ Allowed" if everyone else "❌ Blocked", inline=True)
            embed.add_field(name="Current Template", value=f">>> {settings.get('live_message_template')}", inline=False)
            embed.set_footer(text="Use buttons below to modify template or toggle mentions.")
            return embed

        elif self.current_category == "welcome":
            enabled = bool(settings.get("welcome_enabled", 0))
            w_channel = settings.get("welcome_channel_id")

            embed = discord.Embed(
                title="👋 Welcome System Settings",
                description="Configure automated greetings for new members joining the server.",
                color=discord.Color.blurple(),
            )
            embed.add_field(name="System Status", value="🟢 **Enabled**" if enabled else "🔴 **Disabled**", inline=True)
            embed.add_field(name="Target Channel", value=f"<#{w_channel}>" if w_channel else "*Not configured*", inline=True)
            embed.add_field(name="Embed Color", value=f"`{settings.get('welcome_embed_color', '#5865F2')}`", inline=True)
            embed.add_field(name="Message Template", value=f">>> {settings.get('welcome_message')}", inline=False)
            embed.set_footer(text="Use buttons below to toggle status, edit templates, or preview.")
            return embed

        elif self.current_category == "appearance":
            embed = discord.Embed(
                title="🎨 Appearance & Branding",
                description="Customize colors and branding formats for your community embeds.",
                color=discord.Color.gold(),
            )
            embed.add_field(name="Welcome Color", value=f"`{settings.get('welcome_embed_color', '#5865F2')}`", inline=True)
            embed.add_field(name="YouTube Alert Color", value="`#FF0000` *(Standard YouTube Red)*", inline=True)
            embed.set_footer(text="Click 'Edit Embed Colors' to update theme codes.")
            return embed

        else:  # backup
            embed = discord.Embed(
                title="💾 Backup & Persistence Management",
                description="Export server configurations, download JSON snapshots, or reset to factory defaults.",
                color=discord.Color.dark_grey(),
            )
            embed.add_field(name="Storage Engine", value="`SQLite 3 (WAL Mode)`", inline=True)
            embed.add_field(name="Schema Version", value=f"`v{await self.bot.db.get_schema_version()}`", inline=True)
            embed.set_footer(text="Backups include all channel bindings and message templates.")
            return embed

    # Button Callbacks
    async def handle_edit_yt_msg(self, interaction: discord.Interaction) -> None:
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        current = settings.get("live_message_template") or "🔴 **{streamer}** is now LIVE!\nWatch here: {url}"
        await interaction.response.send_modal(EditLiveTemplateModal(self.bot, current))

    async def handle_toggle_everyone(self, interaction: discord.Interaction) -> None:
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        new_val = 0 if settings.get("live_allow_everyone", 0) else 1
        await self.bot.db.update_guild_settings(interaction.guild_id, live_allow_everyone=new_val)
        embed = await self.build_category_embed(interaction.guild_id)
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_preview_yt(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("YouTubeCog")
        if cog and hasattr(cog, "live_preview"):
            await cog.live_preview.callback(cog, interaction)
        else:
            await interaction.response.send_message("YouTube module not available.", ephemeral=True)

    async def handle_toggle_welcome(self, interaction: discord.Interaction) -> None:
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        new_val = 0 if settings.get("welcome_enabled", 0) else 1
        await self.bot.db.update_guild_settings(interaction.guild_id, welcome_enabled=new_val)
        embed = await self.build_category_embed(interaction.guild_id)
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_edit_welcome_msg(self, interaction: discord.Interaction) -> None:
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        current = settings.get("welcome_message") or "Welcome to {server}, {user}!"
        await interaction.response.send_modal(EditWelcomeMessageModal(self.bot, current))

    async def handle_edit_welcome_embed(self, interaction: discord.Interaction) -> None:
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        await interaction.response.send_modal(EditWelcomeEmbedModal(self.bot, settings))

    async def handle_preview_welcome(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("WelcomeCog")
        if cog and hasattr(cog, "welcome_preview"):
            await cog.welcome_preview.callback(cog, interaction)
        else:
            await interaction.response.send_message("Welcome module not available.", ephemeral=True)

    async def handle_export_backup(self, interaction: discord.Interaction) -> None:
        backup = await self.bot.db.export_guild_backup(interaction.guild_id)
        json_str = json.dumps(backup, indent=2)
        embed = create_success_embed(
            title="Configuration Backup Exported",
            description=f"```json\n{json_str[:1800]}\n```",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def handle_reset_welcome(self, interaction: discord.Interaction) -> None:
        await self.bot.db.reset_welcome_settings(interaction.guild_id)
        embed = await self.build_category_embed(interaction.guild_id)
        await interaction.response.edit_message(embed=embed, view=self)
