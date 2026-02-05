"""AzuraCast station control commands."""

import typer
from rich.console import Console

from stream_tools_cli.azuracast import get_azuracast_client

app = typer.Typer(no_args_is_help=True)
console = Console()


def _get_client():
    """Get AzuraCast client or exit with error."""
    client = get_azuracast_client()
    if not client:
        console.print("[red]Error:[/red] AzuraCast not configured.")
        console.print("Set these environment variables:")
        console.print("  AZURACAST_URL=https://your-azuracast-server.com")
        console.print("  AZURACAST_API_KEY=your-api-key")
        console.print("  AZURACAST_STATION_ID=station_name_or_id")
        raise typer.Exit(1)
    return client


@app.command()
def status() -> None:
    """Show AzuraCast station status."""
    client = _get_client()
    try:
        data = client.get_status()
        console.print(f"[bold]Station:[/bold] {data.get('name', 'Unknown')}")
        console.print(f"[bold]Shortcode:[/bold] {data.get('shortcode', '-')}")
        console.print(f"[bold]Backend:[/bold] {data.get('backend', 'Unknown')}")
        console.print(f"[bold]Frontend:[/bold] {data.get('frontend', 'Unknown')}")

        # Get service status
        try:
            svc = client.get_service_status()
            backend_running = svc.get('backend_running', False)
            frontend_running = svc.get('frontend_running', False)

            be_color = "green" if backend_running else "red"
            fe_color = "green" if frontend_running else "red"
            console.print(f"\n[bold]Backend Running:[/bold] [{be_color}]{backend_running}[/{be_color}]")
            console.print(f"[bold]Frontend Running:[/bold] [{fe_color}]{frontend_running}[/{fe_color}]")
        except Exception:
            pass  # Service status endpoint may not be available

        # Get now playing
        try:
            np = client.get_nowplaying()
            if np.get('now_playing'):
                song = np['now_playing'].get('song', {})
                console.print(f"\n[bold]Now Playing:[/bold] {song.get('artist', '?')} - {song.get('title', '?')}")
            listeners = np.get('listeners', {})
            console.print(f"[bold]Listeners:[/bold] {listeners.get('current', 0)}")
        except Exception:
            pass

        if data.get('public_player_url'):
            console.print(f"\n[bold]Player URL:[/bold] {data['public_player_url']}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def restart() -> None:
    """Restart liquidsoap backend."""
    client = _get_client()
    try:
        console.print("Restarting backend (liquidsoap)...")
        result = client.restart_backend()
        console.print(f"[green]Backend restarted.[/green]")
        if result.get("message"):
            console.print(result["message"])
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def stop() -> None:
    """Stop liquidsoap backend."""
    client = _get_client()
    try:
        console.print("Stopping backend (liquidsoap)...")
        result = client.stop_backend()
        console.print(f"[yellow]Backend stopped.[/yellow]")
        if result.get("message"):
            console.print(result["message"])
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def start() -> None:
    """Start liquidsoap backend."""
    client = _get_client()
    try:
        console.print("Starting backend (liquidsoap)...")
        result = client.start_backend()
        console.print(f"[green]Backend started.[/green]")
        if result.get("message"):
            console.print(result["message"])
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
