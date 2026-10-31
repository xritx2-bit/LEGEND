-- Schema definition for SQLite persistence

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    welcome_enabled INTEGER NOT NULL DEFAULT 0,
    welcome_channel_id INTEGER DEFAULT NULL,
    welcome_message TEXT NOT NULL DEFAULT 'Welcome to {server}, {user}! We are glad you are here.',
    welcome_embed_title TEXT NOT NULL DEFAULT 'Welcome to the Community!',
    welcome_embed_description TEXT NOT NULL DEFAULT 'Hey {user}, welcome! Check out the channels and enjoy your stay.',
    welcome_embed_color TEXT NOT NULL DEFAULT '#5865F2',
    welcome_thumbnail_url TEXT DEFAULT NULL,
    welcome_image_url TEXT DEFAULT NULL,
    welcome_footer TEXT NOT NULL DEFAULT 'Member #{count}',
    live_channel_id INTEGER DEFAULT NULL,
    live_role_id INTEGER DEFAULT NULL,
    live_allow_everyone INTEGER NOT NULL DEFAULT 0,
    live_message_template TEXT NOT NULL DEFAULT '🔴 **{streamer}** is now LIVE on YouTube!\nWatch here: {url}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS youtube_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id TEXT NOT NULL,
    channel_name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_checked_at TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS notified_broadcasts (
    broadcast_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    guild_id INTEGER NOT NULL,
    title TEXT,
    published_at TEXT,
    notified_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_broadcast_channel ON notified_broadcasts (channel_id);
CREATE INDEX IF NOT EXISTS idx_guild_youtube ON youtube_channels (guild_id);
