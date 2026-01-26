"""Stream commands: list, get, create, update, delete."""

import typer
from rich.console import Console

from stream_tools.exceptions import StreamToolsError
from stream_tools.models.common import StreamFrameRate, StreamResolution
from stream_tools_cli.formatting import output
from stream_tools_cli.state import common_options

from stream_tools_cli.commands import get_client

app = typer.Typer(no_args_is_help=True)
console = Console()

STREAM_COLUMNS = {
    "ID": lambda s: s.id,
    "Title": lambda s: s.title,
    "Resolution": lambda s: s.resolution.value if s.resolution else "-",
    "FPS": lambda s: s.frame_rate.value if s.frame_rate else "-",
    "Health": lambda s: s.health_status.value if s.health_status else "-",
    "RTMP URL": lambda s: s.rtmp_url or "-",
}


@app.command("list")
@common_options
def list_streams(
    limit: int = typer.Option(25, "--limit", "-l", help="Max results"),
) -> None:
    """List RTMP streams."""
    try:
        client = get_client()
        result = client.streams.list(max_results=limit)
        if result.items:
            output(result.items, STREAM_COLUMNS, title="Live Streams")
        else:
            console.print("No streams found.")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def get(
    stream_id: str = typer.Argument(..., help="Stream ID"),
) -> None:
    """Get a single stream by ID."""
    try:
        client = get_client()
        stream = client.streams.get(stream_id)
        output([stream], STREAM_COLUMNS, title="Stream")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def create(
    title: str = typer.Option(None, "--title", "-t", help="Stream title"),
    resolution: str = typer.Option(None, "--resolution", "-r", help="Resolution (e.g. 1080p)"),
    frame_rate: str = typer.Option(None, "--frame-rate", "-f", help="Frame rate (30fps/60fps)"),
) -> None:
    """Create a new RTMP stream."""
    if title is None:
        title = typer.prompt("Stream title")
    if resolution is None:
        resolution = typer.prompt("Resolution (240p/360p/480p/720p/1080p/1440p/2160p/variable)", default="1080p")
    if frame_rate is None:
        frame_rate = typer.prompt("Frame rate (30fps/60fps/variable)", default="30fps")

    try:
        client = get_client()
        stream = client.streams.create(
            title=title,
            resolution=StreamResolution(resolution),
            frame_rate=StreamFrameRate(frame_rate),
        )
        console.print("[green]Stream created:[/green]")
        output([stream], STREAM_COLUMNS, title="Stream")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def update(
    stream_id: str = typer.Argument(..., help="Stream ID"),
    title: str = typer.Option(None, "--title", "-t", help="New title"),
) -> None:
    """Update a stream."""
    if title is None:
        title = typer.prompt("New title")

    try:
        client = get_client()
        stream = client.streams.update(stream_id, title)
        console.print("[green]Stream updated:[/green]")
        output([stream], STREAM_COLUMNS, title="Stream")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def delete(
    stream_id: str = typer.Argument(..., help="Stream ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """Delete a stream."""
    if not confirm:
        confirm = typer.confirm(f"Delete stream {stream_id}?")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.streams.delete(stream_id)
        console.print(f"[green]Stream {stream_id} deleted.[/green]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
