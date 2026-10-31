"""Permission checks and mention safety guards for application commands."""

import discord
from discord import app_commands


class NotGuildAdminError(app_commands.CheckFailure):
    """Raised when a user without administrative permissions attempts an admin command."""
    def __init__(self, message: str = "You need **Administrator** or **Manage Server** permissions to use this command."):
        super().__init__(message)


async def is_guild_admin_predicate(interaction: discord.Interaction) -> bool:
    """Predicate function verifying Administrator or Manage Server permissions."""
    # Commands must be executed within a guild
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        raise app_commands.NoPrivateMessage("This command can only be used inside a Discord server.")

    # Server owner always has permission
    if interaction.guild.owner_id == interaction.user.id:
        return True

    # Check Discord permissions
    perms = interaction.user.guild_permissions
    if perms.administrator or perms.manage_guild:
        return True

    raise NotGuildAdminError()


def is_guild_admin():
    """Application command check decorator requiring Administrator or Manage Server permissions."""
    return app_commands.check(is_guild_admin_predicate)


def get_safe_allowed_mentions(
    allow_everyone: bool = False,
    allowed_role_id: int | None = None,
) -> discord.AllowedMentions:
    """Construct an AllowedMentions policy preventing unintended mass mentions.

    - @everyone / @here is blocked unless allow_everyone is True.
    - Specific role mentions are strictly limited to the configured role.
    """
    roles = [discord.Object(id=allowed_role_id)] if allowed_role_id else []

    return discord.AllowedMentions(
        everyone=allow_everyone,
        roles=roles if not allow_everyone else True,
        users=True,
        replied_user=True,
    )
