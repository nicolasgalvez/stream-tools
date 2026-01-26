"""Channel commands: list current channel."""

import typer
from rich.console import Console

from stream_tools.exceptions import StreamToolsError
from stream_tools_cli.commands import get_client
from stream_tools_cli.formatting import output
from stream_tools_cli.state import common_options

app = typer.Typer(no_args_is_help=True)
console = Console()

CHANNEL_COLUMNS = {
    "ID": lambda c: c.id,
    "Title": lambda c: c.title,
    "URL": lambda c: f"youtube.com/{c.custom_url}" if c.custom_url else "-",
    "Live Streaming": lambda c: "enabled" if c.is_live_streaming_enabled else "not enabled",
}


@app.command("list")
@common_options
def list_channels() -> None:
    """Show the authenticated YouTube channel."""
    try:
        client = get_client()
        channel = client.channels.get_mine()
        if channel:
            output([channel], CHANNEL_COLUMNS, title="Channel")
        else:
            console.print("[yellow]No channel found for this account.[/yellow]")
            console.print("Try [bold]yt auth login --force[/bold] to pick a different account.")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
