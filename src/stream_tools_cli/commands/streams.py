"""Stream commands: list, get, create, update, delete."""

import json
from pathlib import Path

import typer
from rich.console import Console

from stream_tools.exceptions import StreamToolsError
from stream_tools.models.common import BroadcastStatus, StreamFrameRate, StreamResolution
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
def health(
    stream_id: str = typer.Argument(..., help="Stream ID"),
) -> None:
    """Show stream health and configuration issues."""
    from stream_tools_cli.state import OutputFormat, config

    try:
        client = get_client()
        stream = client.streams.get(stream_id)

        if config.format == OutputFormat.json:
            import json as json_module
            data = {
                "id": stream.id,
                "title": stream.title,
                "health_status": stream.health_status.value if stream.health_status else None,
                "configuration_issues": [issue.to_dict() for issue in stream.configuration_issues],
            }
            print(json_module.dumps(data, indent=2))
            return

        # Table/default output
        console.print(f"[bold]Stream:[/bold] {stream.title}")
        console.print(f"[bold]ID:[/bold] {stream.id}")

        if stream.health_status:
            color = {
                "good": "green",
                "ok": "yellow",
                "bad": "red",
                "noData": "dim",
            }.get(stream.health_status.value, "white")
            console.print(f"[bold]Health:[/bold] [{color}]{stream.health_status.value}[/{color}]")
        else:
            console.print("[bold]Health:[/bold] [dim]no data[/dim]")

        if stream.configuration_issues:
            console.print("\n[bold]Issues:[/bold]")
            for issue in stream.configuration_issues:
                severity_color = {
                    "error": "red",
                    "warning": "yellow",
                    "info": "blue",
                }.get(issue.severity.value, "white")
                console.print(f"  [{severity_color}][{issue.severity.value}][/{severity_color}] {issue.type}: {issue.reason}")
                if issue.description:
                    console.print(f"           {issue.description}")
        else:
            console.print("\n[green]No configuration issues detected.[/green]")

    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _load_stream_json(path: Path) -> dict:
    """Load stream config from JSON file.

    Expects the schema from `yt stream get --format json`.
    """
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON: {e}")
    except FileNotFoundError:
        raise typer.BadParameter(f"File not found: {path}")

    # Handle array output from `yt stream get --format json`
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    return {
        "title": data.get("title"),
        "resolution": data.get("resolution"),
        "frame_rate": data.get("frame_rate"),
    }


@app.command()
@common_options
def create(
    title: str = typer.Option(None, "--title", "-t", help="Stream title"),
    resolution: str = typer.Option(None, "--resolution", "-r", help="Resolution (e.g. 1080p)"),
    frame_rate: str = typer.Option(None, "--frame-rate", "-f", help="Frame rate (30fps/60fps)"),
    from_json: Path = typer.Option(None, "--from-json", "-j", help="Load settings from JSON file"),
) -> None:
    """Create a new RTMP stream.

    Use --from-json to create from an exported stream config.
    CLI options override JSON values.
    """
    # Load defaults from JSON if provided
    if from_json:
        data = _load_stream_json(from_json)
        json_title = data.get("title")
        json_resolution = data.get("resolution")
        json_frame_rate = data.get("frame_rate")
    else:
        json_title = json_resolution = json_frame_rate = None

    # CLI options override JSON, then fall back to prompts
    if title is None:
        title = json_title or typer.prompt("Stream title")
    if resolution is None:
        resolution = json_resolution or typer.prompt(
            "Resolution (240p/360p/480p/720p/1080p/1440p/2160p/variable)", default="1080p"
        )
    if frame_rate is None:
        frame_rate = json_frame_rate or typer.prompt(
            "Frame rate (30fps/60fps/variable)", default="30fps"
        )

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


@app.command()
def test(
    stream_id: str = typer.Argument(..., help="Stream ID to test"),
    duration: int = typer.Option(30, "--duration", "-d", help="Test duration in seconds"),
    secure: bool = typer.Option(False, "--secure", "-s", help="Use RTMPS (secure) instead of RTMP"),
) -> None:
    """Send a test stream (color bars + tone) via ffmpeg."""
    import shutil
    import subprocess
    import time

    # Check ffmpeg is installed
    if not shutil.which("ffmpeg"):
        console.print("[red]Error:[/red] ffmpeg not found. Install it with: brew install ffmpeg")
        raise typer.Exit(1)

    try:
        client = get_client()
        stream = client.streams.get(stream_id)

        # Choose URL based on secure flag
        if secure:
            base_url = stream.rtmps_ingestion_address
            protocol = "RTMPS"
        else:
            base_url = stream.ingestion_address
            protocol = "RTMP"

        if not base_url or not stream.stream_name:
            console.print("[red]Error:[/red] Stream missing ingestion URL or key")
            raise typer.Exit(1)

        rtmp_url = f"{base_url}/{stream.stream_name}"
        console.print(f"[bold]Sending test stream via {protocol}...[/bold]")
        console.print(f"URL: {rtmp_url}")
        console.print(f"Duration: {duration}s")
        console.print()

        # ffmpeg command: test pattern + sine wave tone
        cmd = [
            "ffmpeg",
            "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=30:duration={duration}",
            "-f", "lavfi", "-i", f"sine=frequency=1000:sample_rate=44100:duration={duration}",
            "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "3000k",
            "-maxrate", "3000k", "-bufsize", "6000k",
            "-pix_fmt", "yuv420p", "-g", "60",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-f", "flv", rtmp_url,
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Wait a few seconds then check health
        console.print("Waiting for stream to connect...")
        time.sleep(5)

        # Check stream health
        stream = client.streams.get(stream_id)
        health = stream.health_status.value if stream.health_status else "unknown"
        health_color = {"good": "green", "ok": "yellow", "bad": "red"}.get(health, "dim")
        console.print(f"Stream health: [{health_color}]{health}[/{health_color}]")

        if stream.configuration_issues:
            console.print("\n[bold]Issues:[/bold]")
            for issue in stream.configuration_issues:
                console.print(f"  [{issue.severity.value}] {issue.type}: {issue.reason}")

        console.print(f"\nStreaming for {duration - 5}s more... (Ctrl+C to stop)")

        # Wait for ffmpeg to finish
        process.wait()
        console.print("[green]Test stream complete.[/green]")

    except KeyboardInterrupt:
        process.terminate()
        console.print("\n[yellow]Test stream stopped.[/yellow]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def watch(
    stream_id: str = typer.Argument(..., help="Stream ID to monitor"),
    interval: int = typer.Option(300, "--interval", "-i", help="Normal check interval in seconds"),
    fail_interval: int = typer.Option(30, "--fail-interval", "-f", help="Check interval when unhealthy"),
    fail_count: int = typer.Option(3, "--fail-count", "-c", help="Failures before restart"),
    restart_wait: int = typer.Option(180, "--restart-wait", "-w", help="Seconds to wait after restart"),
    restart_on_fail: bool = typer.Option(True, "--restart/--no-restart", help="Restart AzuraCast on failure"),
    max_restarts: int = typer.Option(10, "--max-restarts", "-m", help="Max restart attempts before giving up"),
    discord_webhook: str = typer.Option(None, "--discord", "-d", help="Discord webhook URL (or set DISCORD_WEBHOOK_URL)"),
) -> None:
    """Monitor stream health and optionally restart AzuraCast on failure.

    Watches the YouTube stream health status:
    - Normal: checks every 5 minutes (--interval)
    - Unhealthy: checks every 30 seconds (--fail-interval)
    - After 3 failures (--fail-count): restarts AzuraCast
    - After restart: waits 3 minutes (--restart-wait) before resuming

    Sends Discord notifications on failures and restarts if webhook is configured.

    Requires AZURACAST_* environment variables for restart functionality.
    """
    import time
    from datetime import datetime

    from stream_tools_cli.azuracast import get_azuracast_client
    from stream_tools_cli.notifications import (
        DISCORD_BLUE,
        DISCORD_GREEN,
        DISCORD_RED,
        DISCORD_YELLOW,
        get_discord_webhook_url,
        send_discord_notification,
    )

    azura = get_azuracast_client()
    if restart_on_fail and not azura:
        console.print("[yellow]Warning:[/yellow] AzuraCast not configured, restart disabled")
        console.print("Set AZURACAST_URL, AZURACAST_API_KEY, AZURACAST_STATION_ID")
        restart_on_fail = False

    # Get Discord webhook from arg or env
    webhook_url = discord_webhook or get_discord_webhook_url()
    notify = webhook_url is not None

    def send_notification(title: str, message: str, color: int) -> None:
        if notify:
            success = send_discord_notification(webhook_url, title, message, color)
            if not success:
                console.print("[dim]Discord notification failed[/dim]")

    client = get_client()
    consecutive_failures = 0
    total_restarts = 0
    notified_failure = False  # Track if we already notified about current failure

    # Get initial stream info
    try:
        stream = client.streams.get(stream_id)
        stream_title = stream.title
        initial_health = stream.health_status.value if stream.health_status else "noData"
    except StreamToolsError:
        stream_title = stream_id
        initial_health = "unknown"

    # Find the broadcast bound to this stream
    broadcast_title = None
    broadcast_id = None
    broadcast_status = None
    broadcast_url = None
    try:
        # First try to find a "live" broadcast bound to this stream
        broadcasts = client.broadcasts.list(max_results=50, status=BroadcastStatus.ACTIVE)
        for b in broadcasts.items:
            if b.bound_stream_id == stream_id and b.life_cycle_status.value == "live":
                broadcast_title = b.title
                broadcast_id = b.id
                broadcast_status = b.life_cycle_status.value
                broadcast_url = f"https://youtube.com/live/{b.id}"
                break
        # Fall back to ready/testing if no live broadcast found
        if not broadcast_id:
            for b in broadcasts.items:
                if b.bound_stream_id == stream_id and b.life_cycle_status.value in ("ready", "testing"):
                    broadcast_title = b.title
                    broadcast_id = b.id
                    broadcast_status = b.life_cycle_status.value
                    broadcast_url = f"https://youtube.com/live/{b.id}"
                    break
    except Exception:
        pass

    # Get AzuraCast station info
    station_name = "Unknown"
    now_playing = ""
    if azura:
        try:
            station_info = azura.get_status()
            station_name = station_info.get("name", "Unknown")
            np = azura.get_nowplaying()
            if np.get("now_playing"):
                song = np["now_playing"].get("song", {})
                now_playing = f"{song.get('artist', '?')} - {song.get('title', '?')}"
        except Exception:
            pass

    console.print(f"[bold]Station:[/bold] {station_name}")
    if broadcast_title:
        console.print(f"[bold]Broadcast:[/bold] {broadcast_title}")
        console.print(f"[bold]Broadcast ID:[/bold] {broadcast_id}")
        console.print(f"[bold]Broadcast status:[/bold] {broadcast_status}")
        console.print(f"[bold]URL:[/bold] {broadcast_url}")
    console.print(f"[bold]Stream:[/bold] {stream_title}")
    console.print(f"[bold]Stream ID:[/bold] {stream_id}")
    console.print(f"[bold]Current health:[/bold] {initial_health}")
    if now_playing:
        console.print(f"[bold]Now playing:[/bold] {now_playing}")
    console.print(f"\n[bold]Normal interval:[/bold] {interval}s")
    console.print(f"[bold]Fail interval:[/bold] {fail_interval}s")
    console.print(f"[bold]Fail count:[/bold] {fail_count}")
    console.print(f"[bold]Restart wait:[/bold] {restart_wait}s")
    console.print(f"[bold]Auto-restart:[/bold] {restart_on_fail}")
    console.print(f"[bold]Discord notifications:[/bold] {notify}")
    console.print("\nPress Ctrl+C to stop\n")

    # Send startup notification
    if notify:
        startup_msg = f"**Station:** {station_name}\n"
        if broadcast_title:
            startup_msg += f"**Broadcast:** [{broadcast_title}]({broadcast_url})\n"
            startup_msg += f"**Status:** {broadcast_status}\n"
        startup_msg += f"**Stream Health:** {initial_health}\n"
        if now_playing:
            startup_msg += f"**Now Playing:** {now_playing}\n"
        startup_msg += f"\n**Settings:**\n"
        startup_msg += f"• Check interval: {interval}s\n"
        startup_msg += f"• Fail interval: {fail_interval}s\n"
        startup_msg += f"• Failures before restart: {fail_count}\n"
        startup_msg += f"• Auto-restart: {restart_on_fail}"
        send_notification("🎬 Stream Monitor Started", startup_msg, DISCORD_BLUE)

    try:
        while True:
            try:
                stream = client.streams.get(stream_id)
                health = stream.health_status.value if stream.health_status else "noData"
                timestamp = datetime.now().strftime("%H:%M:%S")

                # Determine health color and status
                if health == "good":
                    color = "green"
                    is_healthy = True
                elif health == "ok":
                    color = "yellow"
                    is_healthy = True
                else:  # bad or noData
                    color = "red"
                    is_healthy = False

                console.print(f"[dim]{timestamp}[/dim] Health: [{color}]{health}[/{color}]", end="")

                if is_healthy:
                    consecutive_failures = 0
                    notified_failure = False
                    console.print()
                    # Use normal interval when healthy
                    time.sleep(interval)
                else:
                    consecutive_failures += 1
                    console.print(f" [dim](failures: {consecutive_failures}/{fail_count})[/dim]")

                    # Send failure notification on first failure
                    if consecutive_failures == 1 and not notified_failure:
                        send_notification(
                            "⚠️ Stream Health Issue",
                            f"Stream health is **{health}**\nStream ID: `{stream_id}`",
                            DISCORD_YELLOW,
                        )
                        notified_failure = True

                    # Check if we should restart
                    if restart_on_fail and consecutive_failures >= fail_count:
                        if total_restarts >= max_restarts:
                            console.print(f"[red]Max restarts ({max_restarts}) reached. Giving up.[/red]")
                            send_notification(
                                "🛑 Stream Monitor Stopped",
                                f"Max restarts ({max_restarts}) reached.\nStream ID: `{stream_id}`",
                                DISCORD_RED,
                            )
                            raise typer.Exit(1)

                        console.print(f"[yellow]Restarting AzuraCast backend...[/yellow]")
                        try:
                            azura.restart_backend()
                            total_restarts += 1
                            consecutive_failures = 0
                            notified_failure = False
                            console.print(f"[green]Restarted.[/green] (total restarts: {total_restarts})")
                            console.print(f"[dim]Waiting {restart_wait}s for stream to reconnect...[/dim]")
                            send_notification(
                                "🔄 AzuraCast Restarted",
                                f"Backend restarted due to stream failure.\nTotal restarts: {total_restarts}\nWaiting {restart_wait}s...",
                                DISCORD_YELLOW,
                            )
                            time.sleep(restart_wait)

                            # Check health after restart
                            stream = client.streams.get(stream_id)
                            health_after = stream.health_status.value if stream.health_status else "noData"
                            if health_after in ("good", "ok"):
                                send_notification(
                                    "✅ Stream Recovered",
                                    f"Stream health is now **{health_after}**",
                                    DISCORD_GREEN,
                                )
                        except Exception as e:
                            console.print(f"[red]Restart failed:[/red] {e}")
                            send_notification(
                                "❌ Restart Failed",
                                f"Failed to restart AzuraCast: {e}",
                                DISCORD_RED,
                            )
                            time.sleep(fail_interval)
                    else:
                        # Use shorter interval when unhealthy
                        time.sleep(fail_interval)

            except StreamToolsError as e:
                console.print(f"[red]Error checking stream:[/red] {e}")
                time.sleep(fail_interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped.[/yellow]")
        console.print(f"Total restarts: {total_restarts}")
