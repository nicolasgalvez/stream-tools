# stream-tools

CLI and Python library for managing YouTube Live Streams via the YouTube Live Streaming API.

## Installation

### Global Install (recommended)

Install with [pipx](https://pipx.pypa.io/) to use `yt` anywhere without activating a venv:

```bash
brew install pipx
pipx ensurepath  # adds ~/.local/bin to PATH (restart shell after)
pipx install .
```

### Development Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then run the guided setup to configure GCP credentials:

```bash
yt setup
```

This will:
1. Check your `gcloud` auth and show which Google account you're using
2. Create a GCP project (or use an existing one)
3. Enable the YouTube Data API v3
4. Open the **App Branding** page — set app name and emails
5. Open the **Test Users** page — add your Google account
6. Open the **OAuth Client** page — create a Desktop client and download the JSON
7. Run the OAuth flow to cache your tokens

If you already have a `client_secret.json`:

```bash
yt setup --client-secret ~/Downloads/client_secret_XXX.json
```

## Usage

```bash
# Authenticate (auto-detects: env vars → cached token → browser flow)
yt auth login
yt auth status

# Re-authenticate with account picker (switch YouTube channels)
yt auth login --force

# Authenticate with a token directly (no browser)
yt auth login --token "1//0your-refresh-token"

# See which channel you're using
yt channel list

# Broadcasts
yt broadcast list
yt broadcast get BROADCAST_ID
yt broadcast create --title "Friday Stream" --start "2026-01-24T10:00:00Z" --privacy unlisted
yt broadcast update BROADCAST_ID --title "New Title"
yt broadcast delete BROADCAST_ID --confirm
yt broadcast bind BROADCAST_ID STREAM_ID
yt broadcast transition BROADCAST_ID live

# RTMP Streams
yt stream list
yt stream get STREAM_ID
yt stream create --title "Main Camera" --resolution 1080p --frame-rate 30fps
yt stream update STREAM_ID --title "Backup Camera"
yt stream delete STREAM_ID --confirm

# Live Chat
yt chat list LIVE_CHAT_ID
yt chat send LIVE_CHAT_ID --message "Hello everyone!"
yt chat delete MESSAGE_ID --confirm

# Moderators
yt mod list LIVE_CHAT_ID
yt mod add LIVE_CHAT_ID CHANNEL_ID
yt mod remove MODERATOR_ID --confirm

# Bans
yt ban add LIVE_CHAT_ID CHANNEL_ID --type permanent
yt ban add LIVE_CHAT_ID CHANNEL_ID --type temporary --duration 300
yt ban remove BAN_ID --confirm

# AzuraCast station control (requires AZURACAST_* env vars)
yt azuracast status
yt azuracast restart
yt azuracast stop
yt azuracast start

# Stream health monitoring with auto-restart
yt stream watch STREAM_ID                    # Monitor stream health
yt stream watch STREAM_ID --no-restart       # Monitor only, no auto-restart
yt stream watch STREAM_ID --interval 60      # Check every 60s instead of 300s
yt stream watch STREAM_ID --discord URL      # Send notifications to Discord
```

All commands support interactive prompts. Flags skip the prompt for scripting use.

## Global Options

Global options can be placed anywhere in the command:

```bash
# Output format: table (default), json, csv
yt broadcast list --format json
yt stream list --format csv

# Verbose mode (debug logs to stderr)
yt broadcast list -v
yt stream create --verbose

# Combine: pipe JSON while seeing debug info
yt broadcast list --format json -v 2>/dev/null | jq .
```

## Shell Autocomplete

Typer provides built-in shell completion:

```bash
yt --install-completion  # Install for current shell (bash/zsh/fish)
yt --show-completion     # Print completion script
```

After installing, restart your shell or source your profile.

## Authentication

Three methods, tried in priority order:

1. **Environment variables**: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
2. **Cached token file**: `~/.config/stream-tools/token.json`
3. **Interactive browser flow**: Opens browser for OAuth consent

Switching accounts:
- `yt auth login --force` re-opens the consent flow with the account/channel picker
- `yt channel list` shows which YouTube channel the current credentials are for

### Headless/Remote Deployment

For servers without a browser (Docker, VPS, etc.):

1. **Login locally** to get credentials:
   ```bash
   yt auth login
   ```

2. **Export credentials** to `.env`:
   ```bash
   ./scripts/export-yt-credentials
   ```

3. **Copy `.env`** to your remote server. The CLI will use the env vars automatically.

## Library Usage

The `stream_tools` package is decoupled from the CLI and can be used from any context (web server, bot, script):

```python
from google.oauth2.credentials import Credentials
from stream_tools import YouTubeLiveClient

# Provide credentials however you want (database, env, file, etc.)
creds = Credentials(
    token=access_token,
    refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret,
)

client = YouTubeLiveClient(creds)

# List broadcasts
result = client.broadcasts.list()
for b in result.items:
    print(f"{b.title} [{b.life_cycle_status.value}]")

# Create a stream
stream = client.streams.create(title="Main Camera")
print(f"RTMP URL: {stream.rtmp_url}")
```

The `OAuthManager` is available as an optional utility for local/CLI use:

```python
from stream_tools.auth.oauth import OAuthManager
from stream_tools import YouTubeLiveClient

auth = OAuthManager()
auth.auto_authenticate()
client = YouTubeLiveClient(auth.credentials)
```

## Development

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Serve API docs locally (http://localhost:8080)
scripts/docs

# Generate static HTML to docs/
scripts/docs build
```

## Project Structure

```
src/
├── stream_tools/           # Library (no CLI deps)
│   ├── auth/               # OAuthManager (optional utility)
│   ├── models/             # Dataclasses with from_api_response()
│   ├── services/           # One service per YouTube resource
│   ├── client.py           # YouTubeLiveClient(credentials) facade
│   └── exceptions.py       # Error hierarchy
└── stream_tools_cli/       # Thin CLI wrapper
    ├── app.py              # Typer app + sub-app registration
    ├── formatting.py       # Rich tables/panels
    ├── azuracast.py        # AzuraCast API client
    ├── notifications.py    # Discord webhook notifications
    └── commands/           # One module per command group
scripts/
└── export-yt-credentials   # Export OAuth tokens to .env for headless deploy
```
