"""Main Typer application and sub-app registration."""

# Load .env file before any other imports
from dotenv import load_dotenv

load_dotenv()

# Remove loguru's default handler before any other imports trigger it
from loguru import logger

logger.remove()

import typer

from stream_tools_cli.commands import auth, azuracast, bans, broadcasts, channels, chat, moderators, setup, streams

app = typer.Typer(
    name="yt",
    help="YouTube Live Stream management CLI.",
    no_args_is_help=True,
)

# Register sub-apps
app.add_typer(auth.app, name="auth", help="Authentication management")
app.add_typer(channels.app, name="channel", help="Channel info")
app.add_typer(broadcasts.app, name="broadcast", help="Manage live broadcasts")
app.add_typer(streams.app, name="stream", help="Manage RTMP streams")
app.add_typer(chat.app, name="chat", help="Live chat operations")
app.add_typer(moderators.app, name="mod", help="Chat moderator management")
app.add_typer(bans.app, name="ban", help="Chat ban management")
app.add_typer(azuracast.app, name="azura", help="AzuraCast station control")

# Setup is a top-level command, not a sub-app
app.command(name="setup")(setup.setup)


if __name__ == "__main__":
    app()
