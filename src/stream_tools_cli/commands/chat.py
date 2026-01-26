"""Chat commands: list, send, delete."""

import typer
from rich.console import Console

from stream_tools.exceptions import StreamToolsError
from stream_tools_cli.formatting import output
from stream_tools_cli.state import common_options

from stream_tools_cli.commands import get_client

app = typer.Typer(no_args_is_help=True)
console = Console()

CHAT_COLUMNS = {
    "ID": lambda m: m.id,
    "Author": lambda m: m.author_display_name,
    "Message": lambda m: m.message_text,
    "Time": lambda m: m.published_at.strftime("%H:%M:%S"),
}


@app.command("list")
@common_options
def list_messages(
    live_chat_id: str = typer.Argument(..., help="Live chat ID"),
    limit: int = typer.Option(200, "--limit", "-l", help="Max messages"),
) -> None:
    """List live chat messages."""
    try:
        client = get_client()
        result = client.chat.list_messages(live_chat_id, max_results=limit)
        if result.items:
            output(result.items, CHAT_COLUMNS, title="Chat Messages")
        else:
            console.print("No messages.")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def send(
    live_chat_id: str = typer.Argument(..., help="Live chat ID"),
    message: str = typer.Option(None, "--message", "-m", help="Message text"),
) -> None:
    """Send a chat message."""
    if message is None:
        message = typer.prompt("Message")

    try:
        client = get_client()
        msg = client.chat.send_message(live_chat_id, message)
        console.print(f"[green]Sent:[/green] {msg.message_text}")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def delete(
    message_id: str = typer.Argument(..., help="Message ID to delete"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """Delete a chat message."""
    if not confirm:
        confirm = typer.confirm(f"Delete message {message_id}?")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.chat.delete_message(message_id)
        console.print(f"[green]Message {message_id} deleted.[/green]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
