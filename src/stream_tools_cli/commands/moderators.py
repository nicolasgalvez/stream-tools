"""Moderator commands: list, add, remove."""

import typer
from rich.console import Console

from stream_tools.exceptions import StreamToolsError
from stream_tools_cli.formatting import output
from stream_tools_cli.state import common_options

from stream_tools_cli.commands import get_client

app = typer.Typer(no_args_is_help=True)
console = Console()

MODERATOR_COLUMNS = {
    "ID": lambda m: m.id,
    "Display Name": lambda m: m.display_name,
    "Channel ID": lambda m: m.channel_id,
}


@app.command("list")
@common_options
def list_moderators(
    live_chat_id: str = typer.Argument(..., help="Live chat ID"),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results"),
) -> None:
    """List chat moderators."""
    try:
        client = get_client()
        result = client.moderators.list(live_chat_id, max_results=limit)
        if result.items:
            output(result.items, MODERATOR_COLUMNS, title="Moderators")
        else:
            console.print("No moderators found.")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def add(
    live_chat_id: str = typer.Argument(..., help="Live chat ID"),
    channel_id: str = typer.Argument(..., help="Channel ID to add as moderator"),
) -> None:
    """Add a moderator."""
    try:
        client = get_client()
        mod = client.moderators.add(live_chat_id, channel_id)
        console.print(f"[green]Added moderator:[/green] {mod.display_name} ({mod.channel_id})")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def remove(
    moderator_id: str = typer.Argument(..., help="Moderator ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """Remove a moderator."""
    if not confirm:
        confirm = typer.confirm(f"Remove moderator {moderator_id}?")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.moderators.remove(moderator_id)
        console.print(f"[green]Moderator {moderator_id} removed.[/green]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
