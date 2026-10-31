"""General purpose commands such as /ping and /botinfo."""

import platform
import time
from typing import TYPE_CHECKING
import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from src.main import LegendBot


class GeneralCog(commands.Cog, name="General"):
    """Core diagnostic and informational slash commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: "LegendBot" = bot  # type: ignore[assignment]
        self.start_time = time.time()

    @app_commands.command(name="ping", description="Check the bot's response time and system latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Measure gateway latency and database query latency."""
        # Measure Discord Gateway latency
        gateway_ms = round(self.bot.latency * 1000)

        # Measure Database roundtrip latency
        db_start = time.perf_counter()
        db_ok = False
        try:
            if hasattr(self.bot, "db"):
                conn = await self.bot.db.connect()
                await conn.execute("SELECT 1;")
                db_ok = True
        except Exception:
            db_ok = False
        db_ms = round((time.perf_counter() - db_start) * 1000, 2)

        # Determine health status color
        color = discord.Color.green() if gateway_ms < 200 else discord.Color.gold()

        embed = discord.Embed(
            title="🏓 Pong!",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="📡 Gateway Latency",
            value=f"`{gateway_ms} ms`",
            inline=True,
        )
        embed.add_field(
            name="💾 Database Latency",
            value=f"`{db_ms} ms` {'✅' if db_ok else '⚠️'}",
            inline=True,
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="View bot status, uptime, and system information.")
    async def botinfo(self, interaction: discord.Interaction) -> None:
        """Display operational details and identity of the bot."""
        uptime_seconds = int(time.time() - self.start_time)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        embed = discord.Embed(
            title="🎮 Bot Information",
            description="Production-ready Discord bot for gaming creator livestream alerts and welcome messages.",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(name="⏱️ Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="🌐 Servers", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="👥 Cached Users", value=f"`{len(self.bot.users)}`", inline=True)

        embed.add_field(name="🐍 Python", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="📦 discord.py", value=f"`{discord.__version__}`", inline=True)
        embed.add_field(name="⚙️ Loaded Cogs", value=f"`{len(self.bot.cogs)}`", inline=True)

        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        embed.set_footer(text="Legend Discord Bot • Built for Gaming Creators")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Extension entry point for GeneralCog."""
    await bot.add_cog(GeneralCog(bot))

