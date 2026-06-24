"""Video commands: upload, list, get, update, delete, categories."""

import json
from pathlib import Path

import typer
from rich.console import Console

from stream_tools.exceptions import StreamToolsError
from stream_tools_cli.formatting import output
from stream_tools_cli.state import common_options

from stream_tools_cli.commands import get_client

app = typer.Typer(no_args_is_help=True)
console = Console()

VIDEO_COLUMNS = {
    "ID": lambda v: v.id,
    "Title": lambda v: v.title,
    "Privacy": lambda v: v.privacy_status.value if v.privacy_status else "-",
    "Duration": lambda v: v.duration or "-",
    "Views": lambda v: v.view_count,
    "Status": lambda v: v.upload_status or "-",
    "Published": lambda v: (v.published_at or "-")[:10],
}


def _load_video_json(path: Path) -> dict:
    """Load video settings from a JSON file.

    Expects the schema from the YouTube Data API or `yt video get --format json`:
    {"snippet": {"title": ..., "description": ..., "tags": [...]}, "status": {"privacyStatus": ...}}
    """
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON: {e}")
    except FileNotFoundError:
        raise typer.BadParameter(f"File not found: {path}")

    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    snippet = data.get("snippet", data)
    status = data.get("status", {})

    return {
        "title": snippet.get("title"),
        "description": snippet.get("description"),
        "tags": snippet.get("tags"),
        "category_id": snippet.get("categoryId") or snippet.get("category_id"),
        "privacy_status": status.get("privacyStatus") or status.get("privacy_status"),
        "publish_at": status.get("publishAt") or status.get("publish_at"),
        "default_language": snippet.get("defaultLanguage") or snippet.get("default_language"),
    }


@app.command()
@common_options
def upload(
    file: Path = typer.Argument(..., help="Path to video file"),
    title: str = typer.Option(None, "--title", "-t", help="Video title"),
    description: str = typer.Option(None, "--description", "-d", help="Video description"),
    tags: str = typer.Option(None, "--tags", help="Comma-separated tags"),
    category: str = typer.Option(None, "--category", "-c", help="Category ID (e.g. 22=People)"),
    privacy: str = typer.Option("private", "--privacy", "-p", help="private|public|unlisted"),
    publish_at: str = typer.Option(None, "--publish-at", help="ISO 8601 schedule (requires private)"),
    license: str = typer.Option("youtube", "--license", help="youtube|creativeCommon"),
    made_for_kids: bool = typer.Option(False, "--made-for-kids", help="Mark as made for kids"),
    from_json: Path = typer.Option(None, "--from-json", "-j", help="Load settings from JSON file"),
) -> None:
    """Upload a video file to YouTube.

    Use --from-json to load settings from a JSON config file.
    CLI options override JSON values.
    """
    if from_json:
        data = _load_video_json(from_json)
        title = title or data.get("title")
        description = description or data.get("description")
        category = category or data.get("category_id")
        privacy = privacy or data.get("privacy_status") or "private"
        publish_at = publish_at or data.get("publish_at")
        if data.get("tags") and not tags:
            tags = ",".join(data["tags"])

    if title is None:
        title = typer.prompt("Video title")

    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    try:
        client = get_client()
        video = client.videos.upload(
            file_path=file,
            title=title,
            description=description or "",
            tags=tag_list,
            category_id=category or "",
            privacy_status=privacy,
            publish_at=publish_at,
            license=license,
            made_for_kids=made_for_kids,
        )
        console.print(f"[green]Video uploaded:[/green] https://youtube.com/watch?v={video.id}")
        output([video], VIDEO_COLUMNS, title="Video")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("list")
@common_options
def list_videos(
    limit: int = typer.Option(25, "--limit", "-l", help="Max results (1-50)"),
) -> None:
    """List your uploaded videos."""
    try:
        client = get_client()
        result = client.videos.list(max_results=limit)
        if result.items:
            output(result.items, VIDEO_COLUMNS, title="Your Videos")
        else:
            console.print("No videos found.")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def get(
    video_id: str = typer.Argument(..., help="Video ID"),
) -> None:
    """Get details for a single video."""
    try:
        client = get_client()
        video = client.videos.get(video_id)
        output([video], VIDEO_COLUMNS, title="Video")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def update(
    video_id: str = typer.Argument(..., help="Video ID"),
    title: str = typer.Option(None, "--title", "-t", help="New title"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    tags: str = typer.Option(None, "--tags", help="Comma-separated tags (replaces existing)"),
    category: str = typer.Option(None, "--category", "-c", help="New category ID"),
    privacy: str = typer.Option(None, "--privacy", "-p", help="private|public|unlisted"),
    publish_at: str = typer.Option(None, "--publish-at", help="ISO 8601 schedule"),
) -> None:
    """Update video metadata. Only provided options are changed."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    try:
        client = get_client()
        video = client.videos.update(
            video_id=video_id,
            title=title,
            description=description,
            tags=tag_list,
            category_id=category,
            privacy_status=privacy,
            publish_at=publish_at,
        )
        console.print("[green]Video updated.[/green]")
        output([video], VIDEO_COLUMNS, title="Video")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def delete(
    video_id: str = typer.Argument(..., help="Video ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """Delete a video permanently."""
    if not confirm:
        confirm = typer.confirm(f"Delete video {video_id}? This cannot be undone.")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.videos.delete(video_id)
        console.print(f"[green]Video {video_id} deleted.[/green]")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
@common_options
def categories(
    region: str = typer.Option("US", "--region", "-r", help="ISO 3166-1 country code (US, GB, JP, ...)"),
) -> None:
    """List available video categories for a region."""
    try:
        client = get_client()
        cats = client.videos.list_categories(region_code=region)
        if cats:
            output(
                cats,
                {
                    "ID": lambda c: c["id"],
                    "Title": lambda c: c["title"],
                    "Assignable": lambda c: "Yes" if c["assignable"] else "No",
                },
                title=f"Video Categories ({region})",
            )
        else:
            console.print("No categories found.")
    except StreamToolsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
