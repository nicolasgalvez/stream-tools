"""Broadcast commands: list, get, create, update, delete, bind, transition."""

from datetime import datetime, timezone

import typer
from rich.console import Console

from stream_tools.exceptions import StreamToolsError
from stream_tools.models.common import BroadcastStatus, LifeCycleStatus, PrivacyStatus
from stream_tools_cli.formatting import output
from stream_tools_cli.state import common_options

from stream_tools_cli.commands import get_client

app = typer.Typer(no_args_is_help=True)
console = Console()


def _format_duration(start: datetime | None) -> str:
    """Format duration since start time as 'Xh Ym Zs'."""
    if not start:
        return "-"
    delta = datetime.now(timezone.utc) - start
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


BROADCAST_COLUMNS = {
    "ID": lambda b: b.id,
    "Title": lambda b: b.title,
    "Description": lambda b: b.description or "-",
    "Status": lambda b: b.life_cycle_status.value,
    "Privacy": lambda b: b.privacy.value,
    "Started": lambda b: b.actual_start.strftime("%Y-%m-%d %H:%M") if b.actual_start else "-",
    "Duration": lambda b: _format_duration(b.actual_start) if b.life_cycle_status.value == "live" else "-",
    "Chat ID": lambda b: b.live_chat_id or "-",
    "Stream ID": lambda b: b.bound_stream_id or "-",
}


@app.command("list")
@common_options
def list_broadcasts(
    status: str = typer.Option("all", "--status", "-s", help="Filter: all, active, completed, upcoming"),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results"),
) -> None:
    """List broadcasts."""
    try:
        client = get_client()
        result = client.broadcasts.list(
            status=BroadcastStatus(status),
            max_results=limit,
        )
        if result.items:
            output(result.items, BROADCAST_COLUMNS, title="Broadcasts")
        else:
            console.print("No broadcasts found.")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def get(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
) -> None:
    """Get a single broadcast by ID."""
    try:
        client = get_client()
        broadcast = client.broadcasts.get(broadcast_id)
        output([broadcast], BROADCAST_COLUMNS, title="Broadcast")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def create(
    title: str = typer.Option(None, "--title", "-t", help="Broadcast title"),
    start: str = typer.Option(None, "--start", help="Scheduled start (ISO 8601)"),
    privacy: str = typer.Option(None, "--privacy", "-p", help="Privacy: public, unlisted, private"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
) -> None:
    """Create a new broadcast."""
    if title is None:
        title = typer.prompt("Broadcast title")
    if start is None:
        start = typer.prompt("Scheduled start time (ISO 8601, e.g. 2026-01-24T10:00:00Z)")
    if privacy is None:
        privacy = typer.prompt("Privacy (public/unlisted/private)", default="private")

    try:
        scheduled = datetime.fromisoformat(start.replace("Z", "+00:00"))
        client = get_client()
        broadcast = client.broadcasts.create(
            title=title,
            scheduled_start=scheduled,
            privacy=PrivacyStatus(privacy),
            description=description,
        )
        console.print("[green]Broadcast created:[/green]")
        output([broadcast], BROADCAST_COLUMNS, title="Broadcast")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def update(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    title: str = typer.Option(None, "--title", "-t", help="New title"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    privacy: str = typer.Option(None, "--privacy", "-p", help="New privacy status"),
) -> None:
    """Update a broadcast."""
    try:
        client = get_client()
        broadcast = client.broadcasts.update(
            broadcast_id=broadcast_id,
            title=title,
            description=description,
            privacy=PrivacyStatus(privacy) if privacy else None,
        )
        console.print("[green]Broadcast updated:[/green]")
        output([broadcast], BROADCAST_COLUMNS, title="Broadcast")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def delete(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """Delete a broadcast."""
    if not confirm:
        confirm = typer.confirm(f"Delete broadcast {broadcast_id}?")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.broadcasts.delete(broadcast_id)
        console.print(f"[green]Broadcast {broadcast_id} deleted.[/green]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def bind(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    stream_id: str = typer.Argument(..., help="Stream ID to bind"),
) -> None:
    """Bind a stream to a broadcast."""
    try:
        client = get_client()
        broadcast = client.broadcasts.bind(broadcast_id, stream_id)
        console.print("[green]Stream bound to broadcast:[/green]")
        output([broadcast], BROADCAST_COLUMNS, title="Broadcast")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def transition(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    status: str = typer.Argument(..., help="Target status: live, complete, testing"),
) -> None:
    """Transition a broadcast to a new state."""
    try:
        client = get_client()
        broadcast = client.broadcasts.transition(broadcast_id, LifeCycleStatus(status))
        console.print(f"[green]Broadcast transitioned to {status}:[/green]")
        output([broadcast], BROADCAST_COLUMNS, title="Broadcast")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
