"""Broadcast commands: list, get, create, update, delete, bind, transition."""

import json
from datetime import datetime, timezone
from pathlib import Path

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


def _upload_thumbnail(client, broadcast_id: str, source: str) -> None:
    """Upload a thumbnail from a file path or URL.

    Args:
        client: The YouTubeLiveClient instance.
        broadcast_id: The broadcast to set the thumbnail for.
        source: Either a file path or URL to the thumbnail image.
    """
    import tempfile
    import urllib.request

    # Check if it's a URL
    if source.startswith("http://") or source.startswith("https://"):
        console.print(f"Downloading thumbnail from {source}...")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            urllib.request.urlretrieve(source, tmp_path)
            console.print("Uploading thumbnail...")
            client.broadcasts.set_thumbnail(broadcast_id, tmp_path)
            console.print("[green]Thumbnail uploaded.[/green]")
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    else:
        # It's a file path
        if Path(source).exists():
            console.print(f"Uploading thumbnail from {source}...")
            client.broadcasts.set_thumbnail(broadcast_id, source)
            console.print("[green]Thumbnail uploaded.[/green]")
        else:
            console.print(f"[yellow]Warning:[/yellow] Thumbnail file not found: {source}")


def _load_broadcast_json(path: Path) -> dict:
    """Load broadcast config from JSON file.

    Expects the schema from `yt broadcast get --format json`.
    """
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON: {e}")
    except FileNotFoundError:
        raise typer.BadParameter(f"File not found: {path}")

    # Handle array output from `yt broadcast get --format json`
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    return {
        "title": data.get("title"),
        "description": data.get("description"),
        "privacy": data.get("privacy"),
        "scheduled_start": data.get("scheduled_start"),
        "enable_auto_start": data.get("enable_auto_start"),
        "enable_auto_stop": data.get("enable_auto_stop"),
        "enable_dvr": data.get("enable_dvr"),
        "enable_embed": data.get("enable_embed"),
        "enable_closed_captions": data.get("enable_closed_captions"),
        "closed_captions_type": data.get("closed_captions_type"),
        "enable_low_latency": data.get("enable_low_latency"),
        "latency_preference": data.get("latency_preference"),
        "projection": data.get("projection"),
        "record_from_start": data.get("record_from_start"),
        "made_for_kids": data.get("made_for_kids") or data.get("self_declared_made_for_kids"),
        "thumbnail_url": data.get("thumbnail_url"),
        "bound_stream_id": data.get("bound_stream_id"),
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


def _format_timedelta(start: datetime | None, end: datetime | None) -> str:
    """Format duration between two datetimes."""
    if not start or not end:
        return "-"
    delta = end - start
    total_seconds = int(delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


@app.command()
@common_options
def status(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
) -> None:
    """Show detailed broadcast status and settings."""
    from stream_tools_cli.state import OutputFormat, config

    try:
        client = get_client()
        b = client.broadcasts.get(broadcast_id)

        if config.format == OutputFormat.json:
            print(json.dumps(b.to_dict(), indent=2))
            return

        # Detailed table output
        console.print(f"[bold]Broadcast:[/bold] {b.title}")
        console.print(f"[bold]ID:[/bold] {b.id}")
        console.print()

        # Status section
        status_color = {
            "live": "green",
            "complete": "dim",
            "created": "yellow",
            "ready": "cyan",
            "testing": "cyan",
        }.get(b.life_cycle_status.value, "white")
        console.print(f"[bold]Status:[/bold] [{status_color}]{b.life_cycle_status.value}[/{status_color}]")
        console.print(f"[bold]Privacy:[/bold] {b.privacy.value}")
        if b.recording_status:
            console.print(f"[bold]Recording:[/bold] {b.recording_status}")
        console.print(f"[bold]Made for Kids:[/bold] {b.made_for_kids}")
        console.print()

        # Timing section
        console.print("[bold underline]Timing[/bold underline]")
        if b.scheduled_start:
            console.print(f"  Scheduled Start: {b.scheduled_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        if b.actual_start:
            console.print(f"  Actual Start:    {b.actual_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        if b.actual_end:
            console.print(f"  Actual End:      {b.actual_end.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        if b.actual_start and b.actual_end:
            console.print(f"  Duration:        {_format_timedelta(b.actual_start, b.actual_end)}")
        elif b.actual_start and b.life_cycle_status.value == "live":
            console.print(f"  Running for:     {_format_duration(b.actual_start)}")
        console.print()

        # Settings section
        console.print("[bold underline]Settings[/bold underline]")
        console.print(f"  Auto Start: {b.enable_auto_start}")
        console.print(f"  Auto Stop:  {b.enable_auto_stop}")
        console.print(f"  DVR:        {b.enable_dvr}")
        console.print(f"  Embed:      {b.enable_embed}")
        console.print(f"  Low Latency: {b.enable_low_latency}")
        if b.latency_preference:
            console.print(f"  Latency:    {b.latency_preference}")
        console.print()

        # Linked resources
        console.print("[bold underline]Linked Resources[/bold underline]")
        console.print(f"  Stream ID: {b.bound_stream_id or '[dim]not bound[/dim]'}")
        console.print(f"  Chat ID:   {b.live_chat_id or '[dim]none[/dim]'}")

        # If auto_stop is enabled, add a note about why it might have ended
        if b.life_cycle_status.value == "complete" and b.enable_auto_stop:
            console.print()
            console.print("[yellow]Note:[/yellow] Auto-stop was enabled. Broadcast ended when stream disconnected.")

    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def create(
    title: str = typer.Option(None, "--title", "-t", help="Broadcast title"),
    start: str = typer.Option(None, "--start", help="Scheduled start (ISO 8601). Omit to start now."),
    privacy: str = typer.Option(None, "--privacy", "-p", help="Privacy: public, unlisted, private"),
    description: str = typer.Option(None, "--description", "-d", help="Description"),
    auto_start: bool = typer.Option(True, "--auto-start/--no-auto-start", help="Start when stream goes live"),
    auto_stop: bool = typer.Option(True, "--auto-stop/--no-auto-stop", help="End when stream disconnects"),
    dvr: bool = typer.Option(False, "--dvr/--no-dvr", help="Allow viewers to rewind"),
    embed: bool = typer.Option(True, "--embed/--no-embed", help="Allow embedding"),
    low_latency: bool = typer.Option(False, "--low-latency/--no-low-latency", help="Enable low latency"),
    latency: str = typer.Option("normal", "--latency", help="Latency: normal, low, ultraLow"),
    made_for_kids: bool = typer.Option(False, "--made-for-kids/--not-for-kids", help="Made for kids"),
    stream: str = typer.Option(None, "--stream", "-s", help="Stream ID to bind"),
    from_json: Path = typer.Option(None, "--from-json", "-j", help="Load settings from JSON file"),
    thumbnail: Path = typer.Option(None, "--thumbnail", help="Thumbnail image/URL to upload after creation"),
    restart_stream: bool = typer.Option(False, "--restart-stream", "-r", help="Restart AzuraCast after creating"),
) -> None:
    """Create a new broadcast.

    Use --from-json to create from an exported broadcast config.
    CLI options override JSON values. Omit --start to create a broadcast ready to go live now.

    Use --no-auto-stop for long-running streams that may have brief disconnections.
    Use --restart-stream to restart AzuraCast backend after creating (requires AZURACAST_* env vars).
    """
    # Load defaults from JSON if provided
    json_data: dict = {}
    if from_json:
        json_data = _load_broadcast_json(from_json)

    # Helper to get value: CLI > JSON > default
    def get_val(cli_val, json_key, default=None):
        if json_key in json_data and json_data[json_key] is not None:
            return json_data[json_key]
        return cli_val if cli_val is not None else default

    # String options
    final_title = title or json_data.get("title") or typer.prompt("Broadcast title")
    final_description = description if description is not None else (json_data.get("description") or "")
    final_privacy = privacy or json_data.get("privacy") or typer.prompt("Privacy (public/unlisted/private)", default="private")

    # Boolean options: use JSON value only if CLI is at default
    final_auto_start = json_data.get("enable_auto_start") if (json_data.get("enable_auto_start") is not None and auto_start is True) else auto_start
    final_auto_stop = json_data.get("enable_auto_stop") if (json_data.get("enable_auto_stop") is not None and auto_stop is True) else auto_stop
    final_dvr = json_data.get("enable_dvr") if (json_data.get("enable_dvr") is not None and dvr is False) else dvr
    final_embed = json_data.get("enable_embed") if (json_data.get("enable_embed") is not None and embed is True) else embed
    final_low_latency = json_data.get("enable_low_latency") if (json_data.get("enable_low_latency") is not None and low_latency is False) else low_latency
    final_made_for_kids = json_data.get("made_for_kids") if (json_data.get("made_for_kids") is not None and made_for_kids is False) else made_for_kids

    # String options with defaults
    final_latency = json_data.get("latency_preference") or latency
    final_projection = json_data.get("projection") or "rectangular"
    final_closed_captions = json_data.get("enable_closed_captions") or False
    final_captions_type = json_data.get("closed_captions_type") or "closedCaptionsDisabled"
    final_record_from_start = json_data.get("record_from_start") if json_data.get("record_from_start") is not None else True

    # Parse start time: CLI > JSON > None (immediate)
    # None = immediate broadcast (service uses past time to make it "ready" not "scheduled")
    # "now" = same as None (immediate)
    # datetime = scheduled for that time
    scheduled = None
    json_start = json_data.get("scheduled_start")
    if start is not None:
        if start.lower() == "now":
            scheduled = None  # Immediate broadcast
        else:
            scheduled = datetime.fromisoformat(start.replace("Z", "+00:00"))
    elif json_start is not None:
        scheduled = datetime.fromisoformat(json_start.replace("Z", "+00:00"))
        if scheduled < datetime.now(timezone.utc):
            console.print(f"[yellow]Note:[/yellow] scheduled_start from JSON is in the past, creating immediate broadcast")
            scheduled = None  # Immediate broadcast

    try:
        client = get_client()
        broadcast = client.broadcasts.create(
            title=final_title,
            scheduled_start=scheduled,
            privacy=PrivacyStatus(final_privacy),
            description=final_description,
            enable_auto_start=final_auto_start,
            enable_auto_stop=final_auto_stop,
            enable_dvr=final_dvr,
            enable_embed=final_embed,
            enable_closed_captions=final_closed_captions,
            closed_captions_type=final_captions_type,
            enable_low_latency=final_low_latency,
            latency_preference=final_latency,
            projection=final_projection,
            record_from_start=final_record_from_start,
            made_for_kids=final_made_for_kids,
        )
        console.print("[green]Broadcast created:[/green]")

        # Auto-bind stream: CLI overrides JSON
        stream_id = stream or json_data.get("bound_stream_id")
        if stream_id:
            console.print(f"Binding stream {stream_id}...")
            broadcast = client.broadcasts.bind(broadcast.id, stream_id)
            console.print("[green]Stream bound.[/green]")

        output([broadcast], BROADCAST_COLUMNS, title="Broadcast")

        # Determine thumbnail source: CLI overrides JSON
        thumbnail_source = str(thumbnail) if thumbnail else json_data.get("thumbnail_url")

        if thumbnail_source:
            _upload_thumbnail(client, broadcast.id, thumbnail_source)

        # Restart AzuraCast if requested
        if restart_stream:
            from stream_tools_cli.azuracast import get_azuracast_client

            azura = get_azuracast_client()
            if azura:
                console.print("Restarting AzuraCast backend...")
                try:
                    azura.restart_backend()
                    console.print("[green]AzuraCast backend restarted.[/green]")
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to restart AzuraCast: {e}")
            else:
                console.print("[yellow]Warning:[/yellow] AzuraCast not configured (set AZURACAST_* env vars)")

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


@app.command("thumbnail-download")
def thumbnail_download(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    output_path: Path = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Download the broadcast thumbnail."""
    import urllib.request

    try:
        client = get_client()
        broadcast = client.broadcasts.get(broadcast_id)

        if not broadcast.thumbnail_url:
            console.print("[red]Error:[/red] No thumbnail found for this broadcast")
            raise typer.Exit(1)

        # Default output path based on broadcast ID
        if output_path is None:
            output_path = Path(f"{broadcast_id}_thumbnail.jpg")

        console.print(f"Downloading thumbnail from {broadcast.thumbnail_url}...")
        urllib.request.urlretrieve(broadcast.thumbnail_url, output_path)
        console.print(f"[green]Thumbnail saved to {output_path}[/green]")

    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("thumbnail-set")
def thumbnail_set(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    image_path: Path = typer.Argument(..., help="Path to image file (JPEG, PNG, GIF)"),
) -> None:
    """Set a custom thumbnail for the broadcast."""
    if not image_path.exists():
        console.print(f"[red]Error:[/red] File not found: {image_path}")
        raise typer.Exit(1)

    try:
        client = get_client()
        client.broadcasts.set_thumbnail(broadcast_id, str(image_path))
        console.print(f"[green]Thumbnail set for broadcast {broadcast_id}[/green]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
