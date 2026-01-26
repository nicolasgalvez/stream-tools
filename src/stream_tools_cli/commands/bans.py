"""Ban commands: add, remove."""

import typer
from rich.console import Console

from stream_tools.exceptions import StreamToolsError

from stream_tools_cli.commands import get_client

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def add(
    live_chat_id: str = typer.Argument(..., help="Live chat ID"),
    channel_id: str = typer.Argument(..., help="Channel ID to ban"),
    ban_type: str = typer.Option("permanent", "--type", "-t", help="Ban type: permanent or temporary"),
    duration: int = typer.Option(None, "--duration", "-d", help="Duration in seconds (for temporary bans)"),
) -> None:
    """Ban a user from live chat."""
    try:
        client = get_client()
        ban = client.bans.ban(
            live_chat_id=live_chat_id,
            channel_id=channel_id,
            ban_type=ban_type,
            duration_seconds=duration,
        )
        console.print(f"[green]Banned channel {ban.channel_id} ({ban.ban_type})[/green]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def remove(
    ban_id: str = typer.Argument(..., help="Ban ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """Remove a ban (unban a user)."""
    if not confirm:
        confirm = typer.confirm(f"Remove ban {ban_id}?")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.bans.unban(ban_id)
        console.print(f"[green]Ban {ban_id} removed.[/green]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
