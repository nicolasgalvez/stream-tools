"""Auth commands: login, status, logout."""

import typer
from rich.console import Console

from stream_tools.auth.credentials import AuthMethod
from stream_tools.auth.oauth import OAuthManager
from stream_tools.exceptions import AuthenticationError

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def login(
    method: str = typer.Option(
        None, "--method", "-m", help="Auth method: environment, token_file, interactive"
    ),
    token: str = typer.Option(None, "--token", help="Refresh token (skips browser flow)"),
    client_id: str = typer.Option(None, "--client-id", help="OAuth client ID (used with --token)"),
    client_secret: str = typer.Option(
        None, "--client-secret", help="OAuth client secret (used with --token)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force re-auth with account/channel picker"
    ),
) -> None:
    """Authenticate with YouTube API."""
    auth = OAuthManager()

    try:
        if force:
            auth.reauth()
            console.print("[green]Re-authenticated with new account.[/green]")
            return

        if token:
            auth.authenticate_with_token(token, client_id, client_secret)
            console.print("[green]Authenticated with provided token.[/green]")
            return

        auth_method = None
        if method:
            try:
                auth_method = AuthMethod(method)
            except ValueError:
                console.print(f"[red]Invalid method: {method}[/red]")
                console.print("Valid: environment, token_file, interactive")
                raise typer.Exit(1)

        used = auth.authenticate(auth_method)
        console.print(f"[green]Authenticated via {used.value}[/green]")
    except AuthenticationError as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show current authentication status."""
    auth = OAuthManager()
    info = auth.get_status()

    console.print("[bold]Auth Status[/bold]")
    for key, value in info.items():
        label = key.replace("_", " ").title()
        color = "green" if value else "red"
        console.print(f"  {label}: [{color}]{value}[/{color}]")


@app.command()
def logout() -> None:
    """Remove cached credentials."""
    auth = OAuthManager()
    auth.logout()
    console.print("[green]Logged out. Cached credentials removed.[/green]")
