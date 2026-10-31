"""Asynchronous SQLite database manager."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiosqlite

logger = logging.getLogger("LegendBot.Database")


class DatabaseManager:
    """Manages SQLite database connections and queries asynchronously."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> aiosqlite.Connection:
        """Open database connection with WAL mode enabled."""
        if self._connection is None:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row

            # Optimize for reliability and concurrency
            await self._connection.execute("PRAGMA journal_mode=WAL;")
            await self._connection.execute("PRAGMA busy_timeout=5000;")
            await self._connection.execute("PRAGMA foreign_keys=ON;")
            await self._connection.commit()

        return self._connection

    async def initialize_schema(self, schema_file: Optional[Path] = None) -> None:
        """Run initial database schema creation."""
        conn = await self.connect()
        if schema_file is None:
            schema_file = Path(__file__).parent / "schema.sql"

        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found at: {schema_file}")

        schema_sql = schema_file.read_text(encoding="utf-8")
        await conn.executescript(schema_sql)
        await conn.commit()
        logger.info("Database schema initialized successfully at %s", self.db_path)

    async def close(self) -> None:
        """Safely close active database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed cleanly.")

    # -------------------------------------------------------------
    # Guild Settings Operations
    # -------------------------------------------------------------

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Fetch settings for a guild, creating default row if it does not exist."""
        conn = await self.connect()
        query = "SELECT * FROM guild_settings WHERE guild_id = ?;"
        async with conn.execute(query, (guild_id,)) as cursor:
            row = await cursor.fetchone()

        if row is None:
            # Insert default row
            insert_query = "INSERT INTO guild_settings (guild_id) VALUES (?);"
            await conn.execute(insert_query, (guild_id,))
            await conn.commit()

            async with conn.execute(query, (guild_id,)) as cursor:
                row = await cursor.fetchone()

        return dict(row) if row else {}

    async def update_guild_settings(self, guild_id: int, **kwargs: Any) -> Dict[str, Any]:
        """Update specific settings fields for a guild."""
        if not kwargs:
            return await self.get_guild_settings(guild_id)

        # Make sure row exists first
        await self.get_guild_settings(guild_id)

        conn = await self.connect()
        allowed_columns = {
            "welcome_enabled",
            "welcome_channel_id",
            "welcome_message",
            "welcome_embed_title",
            "welcome_embed_description",
            "welcome_embed_color",
            "welcome_thumbnail_url",
            "welcome_image_url",
            "welcome_footer",
            "live_channel_id",
            "live_role_id",
            "live_allow_everyone",
            "live_message_template",
        }

        updates: List[str] = []
        values: List[Any] = []

        for key, value in kwargs.items():
            if key in allowed_columns:
                updates.append(f"{key} = ?")
                values.append(value)

        if not updates:
            return await self.get_guild_settings(guild_id)

        updates.append("updated_at = (datetime('now'))")
        values.append(guild_id)

        sql = f"UPDATE guild_settings SET {', '.join(updates)} WHERE guild_id = ?;"
        await conn.execute(sql, tuple(values))
        await conn.commit()

        return await self.get_guild_settings(guild_id)

    # -------------------------------------------------------------
    # YouTube Channels Operations
    # -------------------------------------------------------------

    async def upsert_youtube_channel(
        self,
        guild_id: int,
        channel_id: str,
        channel_name: Optional[str] = None,
    ) -> None:
        """Add or update the configured YouTube channel for a guild."""
        conn = await self.connect()
        query = """
            INSERT INTO youtube_channels (guild_id, channel_id, channel_name, is_active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(guild_id, channel_id) DO UPDATE SET
                channel_name = excluded.channel_name,
                is_active = 1;
        """
        await conn.execute(query, (guild_id, channel_id, channel_name))
        await conn.commit()

    async def get_youtube_channel(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get the active monitored YouTube channel for a guild."""
        conn = await self.connect()
        query = "SELECT * FROM youtube_channels WHERE guild_id = ? AND is_active = 1 LIMIT 1;"
        async with conn.execute(query, (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_youtube_last_checked(self, guild_id: int, channel_id: str) -> None:
        """Update the last_checked_at timestamp for a channel."""
        conn = await self.connect()
        query = """
            UPDATE youtube_channels
            SET last_checked_at = (datetime('now'))
            WHERE guild_id = ? AND channel_id = ?;
        """
        await conn.execute(query, (guild_id, channel_id))
        await conn.commit()

    async def get_last_announced_broadcast(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Fetch the most recently notified broadcast for a guild."""
        conn = await self.connect()
        query = """
            SELECT * FROM notified_broadcasts
            WHERE guild_id = ?
            ORDER BY notified_at DESC, rowid DESC
            LIMIT 1;
        """
        async with conn.execute(query, (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    # -------------------------------------------------------------
    # Broadcast Tracking Operations
    # -------------------------------------------------------------

    async def is_broadcast_notified(self, broadcast_id: str) -> bool:
        """Check if a YouTube broadcast ID has already been notified."""
        conn = await self.connect()
        query = "SELECT 1 FROM notified_broadcasts WHERE broadcast_id = ?;"
        async with conn.execute(query, (broadcast_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

    async def record_broadcast_notified(
        self,
        broadcast_id: str,
        channel_id: str,
        guild_id: int,
        title: Optional[str] = None,
        published_at: Optional[str] = None,
    ) -> None:
        """Record a notified broadcast ID to prevent future duplicate notifications."""
        conn = await self.connect()
        query = """
            INSERT OR IGNORE INTO notified_broadcasts
            (broadcast_id, channel_id, guild_id, title, published_at)
            VALUES (?, ?, ?, ?, ?);
        """
        await conn.execute(query, (broadcast_id, channel_id, guild_id, title, published_at))
        await conn.commit()
