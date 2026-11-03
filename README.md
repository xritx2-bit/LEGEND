# 🎮 Legend Discord Bot

A reliable, modular, production-ready Discord bot purpose-built for gaming creators and streaming communities.

Designed to deliver **YouTube livestream notifications** with duplicate-prevention, rich embeds, and safe role pings, alongside a **customizable welcome system** and an **interactive `/setup` dashboard**.

---

## ✨ Features

- **🔴 YouTube Livestream Alerts**:
  - Automatically monitors your configured YouTube channel for active livestreams.
  - Zero hardcoding: Configure channel IDs, target channels, and role pings on the fly.
  - **Duplicate Prevention**: Tracks broadcast IDs in SQLite so restarts never send duplicate alerts.
  - **Safe Mention Controls**: Role mentions supported, with `@everyone` protected behind strict administrator authorization.
  - **In-Chat Preview & Test Mode**: Send mock alerts (`/live test` and `/live preview`) without having to go live.
  - **Quota Aware**: Polling rate limits and exponential backoff to keep API usage well within the free tier.

- **👋 Custom Welcome System**:
  - Greet new community members automatically when they join.
  - Dynamic template placeholders: `{user}`, `{username}`, `{server}`, and `{count}`.
  - Rich embed customization: Title, description, hex colors (`#5865F2`), thumbnails, and banner images.
  - Safe mention filtering: Strictly pings only the joined member (no accidental mass mentions).
  - Preview (`/welcome preview`) and factory reset (`/welcome reset`).

- **⚙️ Interactive `/setup` Control Panel**:
  - Visual Discord UI dashboard using buttons, select menus, and modals.
  - Easily edit templates, toggle settings, and test appearances without remembering command syntax.

- **🛡️ Security & Reliability**:
  - Sensitive credentials automatically redacted from console and file logs.
  - Asynchronous SQLite with Write-Ahead Logging (WAL mode) and atomic snapshot backups.
  - Strict permission decorators (`@is_guild_admin()`) protecting configuration commands.
  - Centralized application command error handling.

---

## 📋 Technology Stack

- **Python 3.12+**
- **discord.py 2.7+**
- **YouTube Data API v3**
- **aiosqlite** (Asynchronous SQLite)
- **python-dotenv** (Environment credentials)
- **pytest & pytest-asyncio** (Automated testing suite)

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.12+** installed on your system.
- A **Discord Account** with administrator permissions on your test server.
- A **Google Cloud Account** for the YouTube Data API key.

---

### 2. Discord Developer Portal Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. Name your application (e.g. `Legend Bot`) and accept the terms.
3. In the left sidebar, click **Bot**:
   - Click **Reset Token** and copy your **Bot Token** (keep this secret!).
4. Scroll down to **Privileged Gateway Intents**:
   - Turn **ON** `SERVER MEMBERS INTENT` (Required for the welcome system and member counts).
   - Click **Save Changes**.
5. In the left sidebar, click **OAuth2** > **URL Generator**:
   - Under **Scopes**, select `bot` and `applications.commands`.
   - Under **Bot Permissions**, select:
     - `Send Messages`
     - `Embed Links`
     - `Attach Files`
     - `Read Message History`
     - `Mention Everyone`
     - `Use Application Commands`
     - `View Channels`
6. Copy the generated URL at the bottom and open it in your browser to invite the bot to your Discord server.

---

### 3. YouTube Data API v3 Setup

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `My-Gaming-Bot`).
3. In the search bar at the top, search for **YouTube Data API v3** and click **Enable**.
4. Go to **APIs & Services** > **Credentials**:
   - Click **+ CREATE CREDENTIALS** > **API key**.
   - Copy the generated API key.
5. Find your YouTube Channel ID:
   - Go to your YouTube Channel > **About** > **Share** > **Copy channel ID** (starts with `UC...`).

---

### 4. Installation & Local Setup

Clone or open the project folder in your terminal:

```powershell
# 1. Create a Python virtual environment
python -m venv .venv

# 2. Activate the virtual environment
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

# 3. Install required dependencies
pip install -r requirements.txt

# 4. Create your .env configuration file
Copy-Item .env.example .env
```

Open `.env` in any text editor and fill in your credentials:

```ini
# Discord Credentials
DISCORD_BOT_TOKEN="your_bot_token_here"
DISCORD_GUILD_ID="" # (Optional: paste your Discord server ID for instant dev slash command sync)

# YouTube Data API
YOUTUBE_API_KEY="your_google_cloud_api_key_here"
YOUTUBE_CHANNEL_ID="UCxxxxxxxxxxxxxxxxxxxxxx"
YOUTUBE_POLL_INTERVAL=300 # In seconds (default: 5 minutes)

# Storage & Logging
DATABASE_PATH="data/bot_database.db"
LOG_LEVEL="INFO"
```

---

### 5. Running the Bot

Start the bot with:

```powershell
python src/main.py
```

When started successfully, you will see output similar to:
```text
2026-10-31 16:30:00 [INFO    ] LegendBot: Starting Legend Discord Bot...
2026-10-31 16:30:00 [INFO    ] LegendBot.Database: Database schema initialized successfully at data\bot_database.db
2026-10-31 16:30:01 [INFO    ] LegendBot: Synced 14 slash commands globally.
2026-10-31 16:30:02 [INFO    ] LegendBot: 🤖 Logged in as: Legend Bot#0000
2026-10-31 16:30:02 [INFO    ] LegendBot.YouTubeCog: YouTube livestream background polling started (interval: 300s).
```

---

## 🛠️ Slash Commands Reference

### General Commands
| Command | Description | Permission |
| :--- | :--- | :--- |
| `/ping` | Displays gateway latency and database roundtrip latency | Everyone |
| `/botinfo` | Shows bot uptime, servers, Python version, and loaded modules | Everyone |
| `/setup` | Launches the interactive settings dashboard | Administrator / Manage Server |

### YouTube Livestream Commands (`/live ...`)
| Command | Description | Parameters |
| :--- | :--- | :--- |
| `/live setup` | Configures YouTube notifications | `youtube_channel_id`, `discord_channel`, `notification_role`, `allow_everyone`, `message_template` |
| `/live test` | Sends a sample live alert to the configured channel | None |
| `/live check` | Manually queries YouTube right now and checks stream status | None |
| `/live preview`| Shows an ephemeral preview of the notification layout | None |
| `/live status` | Displays current channel, ping role, polling interval, and last check | None |

### Welcome System Commands (`/welcome ...`)
| Command | Description | Parameters |
| :--- | :--- | :--- |
| `/welcome channel` | Sets the welcome channel and activates greeting messages | `channel` (TextChannel) |
| `/welcome enable`  | Turns automated welcome greetings on | None |
| `/welcome disable` | Turns automated welcome greetings off | None |
| `/welcome message` | Customizes message text above the embed | `template` (supports variables) |
| `/welcome embed`   | Customizes embed title, body, color, thumbnail, and banner | `title`, `description`, `color`, `thumbnail`, `image`, `footer` |
| `/welcome upload`  | Uploads an image file directly from device for thumbnail/banner | `target` (Thumbnail/Banner), `file` (Attachment) |
| `/welcome preview` | Displays an ephemeral preview of the welcome greeting | None |
| `/welcome reset`   | Restores welcome settings to default values | None |

### Dynamic Template Variables
| Variable | Description | Supported In |
| :--- | :--- | :--- |
| `{user}` | Mentions the new member (`@User`) | Welcome Message & Embed |
| `{username}` | Member's display name | Welcome Message & Embed |
| `{server}` | Server name | Welcome Message & Embed |
| `{count}` | Total server member count | Welcome Message & Embed |
| `{user_avatar}` / `{avatar}` | Joining member's profile avatar URL | Welcome Thumbnail & Image |
| `{server_icon}` / `{icon}` | Server icon URL | Welcome Thumbnail & Image |
| `{server_banner}` / `{banner}` | Server banner image URL | Welcome Thumbnail & Image |
| `{streamer}`| YouTube creator channel name | Live Message Template |
| `{title}` | Livestream title | Live Message Template |
| `{url}` | Livestream watch URL | Live Message Template |
| `{game}` | Game / category name | Live Message Template |
| `{role}` | Configured role ping | Live Message Template |

---

## 🧪 Running Automated Tests

Run the complete test suite anytime with:

```powershell
.\.venv\Scripts\pytest -v
```

All 55 automated tests verify:
- SQLite persistence, concurrency, and duplicate stream prevention.
- YouTube API response parsing and mock broadcast generation.
- Template token validation and URL/hex color sanitization.
- Mention security policies and administrator checks.
- Welcome embed and event dispatch handlers.
- Database backup creation via `VACUUM INTO` and config restore.

---

## 🚢 24/7 Production Deployment Guide

### Option A: Windows (Local Server or Always-On PC)
Using **NSSM (Non-Sucking Service Manager)**:
1. Download NSSM from [nssm.cc](https://nssm.cc/).
2. Run PowerShell as Administrator:
   ```powershell
   nssm install LegendBot "C:\path\to\LEGEND\.venv\Scripts\python.exe" "src/main.py"
   nssm set LegendBot AppDirectory "C:\path\to\LEGEND"
   nssm set LegendBot Start SERVICE_AUTO_START
   nssm start LegendBot
   ```

### Option B: Linux VPS (Ubuntu / Debian)
Using **systemd**:
1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/legendbot.service
   ```
2. Paste the following configuration:
   ```ini
   [Unit]
   Description=Legend Discord Bot
   After=network.target

   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/LEGEND
   ExecStart=/home/ubuntu/LEGEND/.venv/bin/python src/main.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```
3. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable legendbot
   sudo systemctl start legendbot
   ```

---

## 🔒 Security Best Practices

- **Never share or commit your `.env` file**: Your `.gitignore` is already pre-configured to protect `.env`, SQLite databases, and logs.
- **Redaction**: All configured tokens and keys are automatically masked in log outputs.
- **Mentions**: The bot restricts gateway mentions by default. `@everyone` pings cannot be dispatched unless explicitly approved by an administrator in `/live setup`.

---

## 📄 License
MIT License. Built for gaming creators and their communities.
