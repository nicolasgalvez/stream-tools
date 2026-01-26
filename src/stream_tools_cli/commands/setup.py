"""Setup command: guided GCP project + OAuth configuration."""

import webbrowser
from pathlib import Path

import typer
from rich.console import Console

from stream_tools.auth.oauth import OAuthManager
from stream_tools.services.setup import SetupService

console = Console()


def setup(
    project_id: str = typer.Option(None, "--project", help="GCP project ID"),
    client_secret_file: Path = typer.Option(
        None, "--client-secret", help="Path to downloaded client_secret.json"
    ),
) -> None:
    """Interactive setup: create GCP project, enable API, configure OAuth."""
    svc = SetupService()

    # Check gcloud
    if not svc.check_gcloud_installed():
        console.print(
            "[red]gcloud CLI not found.[/red] Install it from: "
            "https://cloud.google.com/sdk/docs/install"
        )
        raise typer.Exit(1)

    # Check gcloud auth
    accounts = svc.list_gcloud_accounts()
    if not accounts:
        console.print("[red]gcloud is not authenticated.[/red] Run:")
        console.print("  gcloud auth login")
        raise typer.Exit(1)

    if len(accounts) == 1:
        account = accounts[0]
    else:
        console.print("Available Google accounts:")
        for i, acct in enumerate(accounts, 1):
            active = svc.get_gcloud_account()
            marker = " (active)" if acct == active else ""
            console.print(f"  {i}. {acct}{marker}")
        choice = typer.prompt("Account number", default="1")
        account = accounts[int(choice) - 1]
        svc.set_gcloud_account(account)

    console.print(f"Using Google account: [bold]{account}[/bold]\n")

    console.print("[bold]YouTube Live Stream Tools Setup[/bold]\n")

    # Step 1: Project ID
    if project_id is None:
        project_id = typer.prompt("GCP Project ID", default=svc.generate_project_id())

    # Step 2: Create project (or skip if exists)
    create_project = typer.confirm(f"Create new GCP project '{project_id}'?", default=True)
    if create_project:
        try:
            console.print(f"Creating project [bold]{project_id}[/bold]...")
            svc.create_project(project_id)
            console.print("[green]Project created.[/green]")
        except Exception as e:
            console.print(f"[yellow]Project creation: {e}[/yellow]")
            console.print("Continuing with existing project...")

    # Step 3: Enable YouTube API
    console.print("Enabling YouTube Data API v3...")
    try:
        svc.enable_youtube_api(project_id)
        console.print("[green]YouTube API enabled.[/green]")
    except Exception as e:
        console.print(f"[yellow]API enablement: {e}[/yellow]")

    # Step 4: OAuth consent screen + test users + credentials
    if client_secret_file is None:
        # 4a: Branding (app name, email)
        consent_url = svc.get_consent_screen_url(project_id)
        console.print("\n[bold]Step 1: App Branding[/bold]")
        console.print(f"URL: {consent_url}\n")
        webbrowser.open(consent_url)

        console.print("Instructions:")
        console.print("  1. Set App name (e.g. 'stream-tools')")
        console.print("  2. Add your email as User support email")
        console.print("  3. Add your email as Developer contact")
        console.print("  4. Click [bold]'Save'[/bold]\n")

        typer.prompt("Press Enter when done", default="", show_default=False)

        # 4b: Test users
        test_users_url = svc.get_test_users_url(project_id)
        console.print("\n[bold]Step 2: Add Test Users[/bold]")
        console.print(f"URL: {test_users_url}\n")
        webbrowser.open(test_users_url)

        console.print("Instructions:")
        console.print("  1. Click [bold]'+ Add Users'[/bold]")
        console.print(f"  2. Add your Google email ({account})")
        console.print("  3. Click [bold]'Save'[/bold]\n")

        typer.prompt("Press Enter when done", default="", show_default=False)

        # 4c: OAuth client credentials
        credentials_url = svc.get_credentials_url(project_id)
        console.print("\n[bold]Step 3: Create OAuth Client[/bold]")
        console.print(f"URL: {credentials_url}\n")
        webbrowser.open(credentials_url)

        console.print("Instructions:")
        console.print("  1. Application type: [bold]'Desktop app'[/bold]")
        console.print("  2. Name it anything (e.g. 'stream-tools')")
        console.print("  3. Click [bold]'Create'[/bold]")
        console.print("  4. Click [bold]'Download JSON'[/bold]\n")

        path_str = typer.prompt("Path to downloaded client_secret JSON file")
        client_secret_file = Path(path_str).expanduser()

    # Step 5: Store client secret
    dest = svc.store_client_secret(client_secret_file)
    console.print(f"[green]Client secret saved to {dest}[/green]")

    # Step 6: Run OAuth flow immediately
    console.print("\nStarting OAuth flow to obtain tokens...")
    auth = OAuthManager()
    auth.run_flow_for_client_secret(dest)
    console.print("[green]Authentication complete! Tokens cached.[/green]")
    console.print("\nSetup finished. Run [bold]yt broadcast list[/bold] to verify.")
