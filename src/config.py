"""Configuration loader and validator for the Discord Bot."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


def _get_env_int(key: str, default: int, min_val: Optional[int] = None) -> int:
    """Safely parse integer from environment with fallback and validation."""
    val_str = os.getenv(key)
    if not val_str:
        return default
    try:
        val = int(val_str)
        if min_val is not None and val < min_val:
            return default
        return val
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Strongly typed application configuration."""
    discord_token: str
    discord_client_id: Optional[str]
    guild_id: Optional[int]
    youtube_api_key: str
    youtube_channel_id: str
    youtube_poll_interval: int
    database_path: Path
    log_level: str

    @classmethod
    def load(cls, env_path: Optional[str] = None) -> "Config":
        """Load configuration from environment or specified .env file."""
        if env_path:
            load_dotenv(dotenv_path=env_path, override=True)

        token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        client_id = os.getenv("DISCORD_CLIENT_ID", "").strip() or None

        guild_id_str = os.getenv("DISCORD_GUILD_ID", "").strip()
        guild_id = int(guild_id_str) if guild_id_str.isdigit() else None

        yt_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        yt_channel = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()

        # Minimum poll interval: 60 seconds to protect API quotas
        poll_interval = _get_env_int("YOUTUBE_POLL_INTERVAL", default=300, min_val=60)

        db_path_str = os.getenv("DATABASE_PATH", "data/bot_database.db").strip()
        db_path = Path(db_path_str)

        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            log_level = "INFO"

        return cls(
            discord_token=token,
            discord_client_id=client_id,
            guild_id=guild_id,
            youtube_api_key=yt_key,
            youtube_channel_id=yt_channel,
            youtube_poll_interval=poll_interval,
            database_path=db_path,
            log_level=log_level,
        )

    def validate_for_start(self) -> None:
        """Validate critical configuration before starting the bot."""
        if not self.discord_token or self.discord_token == "your_discord_bot_token_here":
            raise ValueError(
                "DISCORD_BOT_TOKEN is missing or set to placeholder. "
                "Please configure a valid bot token in your .env file."
            )

    @property
    def is_youtube_configured(self) -> bool:
        """Check if YouTube API credentials and channel are configured."""
        return bool(
            self.youtube_api_key
            and self.youtube_api_key != "your_youtube_api_key_here"
            and self.youtube_channel_id
            and self.youtube_channel_id != "your_youtube_channel_id_here"
        )


def redact_secret(secret: str, visible_chars: int = 4) -> str:
    """Mask sensitive string leaving only the last few characters visible."""
    if not secret:
        return "[NOT SET]"
    if len(secret) <= visible_chars:
        return "****"
    return f"{'*' * (len(secret) - visible_chars)}{secret[-visible_chars:]}"

