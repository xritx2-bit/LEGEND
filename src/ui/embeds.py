"""Standardized embed builders for consistent bot presentation."""

from typing import Optional
import discord


# Brand palette for the gaming bot
COLOR_PRIMARY = discord.Color.blurple()
COLOR_SUCCESS = discord.Color.green()
COLOR_WARNING = discord.Color.gold()
COLOR_ERROR = discord.Color.red()
COLOR_YOUTUBE = discord.Color.from_rgb(255, 0, 0)


def create_info_embed(
    title: str,
    description: str,
    footer: Optional[str] = "Legend Bot",
    thumbnail_url: Optional[str] = None,
) -> discord.Embed:
    """Build a standard informative embed with primary branding."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLOR_PRIMARY,
        timestamp=discord.utils.utcnow(),
    )
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if footer:
        embed.set_footer(text=footer)
    return embed


def create_success_embed(
    title: str,
    description: str,
    footer: Optional[str] = "Legend Bot • Success",
) -> discord.Embed:
    """Build a success confirmation embed with green accent."""
    embed = discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=COLOR_SUCCESS,
        timestamp=discord.utils.utcnow(),
    )
    if footer:
        embed.set_footer(text=footer)
    return embed


def create_warning_embed(
    title: str,
    description: str,
    footer: Optional[str] = "Legend Bot • Warning",
) -> discord.Embed:
    """Build an alert/warning embed with amber accent."""
    embed = discord.Embed(
        title=f"⚠️ {title}",
        description=description,
        color=COLOR_WARNING,
        timestamp=discord.utils.utcnow(),
    )
    if footer:
        embed.set_footer(text=footer)
    return embed


def create_error_embed(
    title: str,
    description: str,
    footer: Optional[str] = "Legend Bot • Error",
) -> discord.Embed:
    """Build a user-facing error embed with red accent."""
    embed = discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=COLOR_ERROR,
        timestamp=discord.utils.utcnow(),
    )
    if footer:
        embed.set_footer(text=footer)
    return embed
