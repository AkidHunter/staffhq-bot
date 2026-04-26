# StaffHQ Discord Bot

Discord bot for StaffHQ. Tracks staff activity, posts punishment alerts, links Discord accounts to Minecraft, and provides slash commands for player lookups.

Fetches its Discord token from the StaffHQ dashboard at startup. Only one secret needed: your StaffHQ API key.

## Setup

### 1. Create a Discord application

1. Go to https://discord.com/developers/applications and create a new application.
2. Go to **Bot**, click **Reset Token**, copy the token.
3. Enable **Server Members Intent** and **Message Content Intent**.
4. Note the **Application ID** from the General Information page.

### 2. Invite the bot

1. Go to **OAuth2 > URL Generator**.
2. Select scopes: `bot`, `applications.commands`.
3. Select permissions: Send Messages, Embed Links, Read Message History, View Channels.
4. Open the generated URL and add it to your server.

### 3. Generate a StaffHQ API key

1. Log in to your StaffHQ dashboard.
2. Go to **Settings > API Keys**.
3. Generate a new key with type **Bot**.
4. Copy it.

### 4. Configure Discord in StaffHQ

1. Go to **Settings > Discord Bot** in the dashboard.
2. Enter your Client ID, Bot Token, Guild ID, and Alert Channel ID.
3. Save.

### 5. Run the bot

```bash
git clone https://github.com/AkidHunter/staffhq-bot.git
cd staffhq-bot
cp .env.example .env
# Set STAFFHQ_API_KEY in .env
```

With Docker:
```bash
docker compose up -d
```

Without Docker:
```bash
pip install -r requirements.txt
python main.py
```

First run (syncs slash commands with Discord):
```bash
SYNC_COMMANDS=1 python main.py
```

### Slash commands

- `/investigate <player>` - player info, recent punishments, AC flags
- `/chatlog <player>` - recent chat and commands
- `/punishments <player>` - punishment history
- `/flags <player>` - anticheat flags
- `/online` - server status and online staff

## Troubleshooting

**`STAFFHQ_API_KEY is not set`** - Create `.env` from `.env.example` and fill in the key.

**`Discord not configured yet`** - Complete step 4 in the dashboard. Bot retries automatically.

**`Bad token`** - Regenerate the token at discord.com/developers and update it in the dashboard.

**`Config fetch failed`** - Dashboard unreachable. Check `DASHBOARD_API_URL` in `.env` (default: `https://dash.staffhq.net`).

## Support

Join our Discord: https://discord.gg/tDsxFsxb6c

## Updating

```bash
git pull
docker compose up -d --build
```
