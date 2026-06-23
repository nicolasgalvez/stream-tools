# stream_tools_cli (CLI)

Thin Typer wrapper around `stream_tools` library. Only place auth (`OAuthManager`) is wired in by default. Entrypoint: `yt` (defined in `pyproject.toml`).

## STRUCTURE

```
stream_tools_cli/
├── app.py             # Typer app + sub-app registration (IMPORT ORDER MATTERS)
├── state.py           # config dataclass + @common_options decorator
├── formatting.py      # output(items, columns) → table/json/csv/ids
├── azuracast.py       # AzuraCastConfig.from_env() + REST client (None when env unset)
├── notifications.py   # Discord webhook poster
└── commands/
    ├── __init__.py    # get_client() — OAuthManager → YouTubeLiveClient
    ├── auth.py        # yt auth login / status
    ├── broadcasts.py  # yt broadcast * (507 lines)
    ├── streams.py     # yt stream * (551 lines, includes `watch` w/ AzuraCast+Discord)
    ├── chat.py
    ├── moderators.py
    ├── bans.py
    ├── channels.py
    ├── azuracast.py   # yt azura *
    └── setup.py       # yt setup (top-level command, NOT sub-app)
```

## WHERE TO LOOK

| Task | Location |
|---|---|
| Add new command group | `commands/<resource>.py` → Typer sub-app → register in `app.py` |
| Add global option | `state.py:common_options` — uses `inspect.Signature` manipulation |
| Render list/table output | `formatting.py:output(items, columns, title=...)` |
| Wire auth | `commands/__init__.py:get_client()` — every command calls this |
| Stream watch + auto-restart | `commands/streams.py:watch` — AzuraCast + Discord integration |
| AzuraCast integration | `azuracast.py` — env-driven, returns `None` when unset (graceful degrade) |

## CONVENTIONS (CLI-SPECIFIC)

- Every command: `@app.command()` + `@common_options` + `get_client()` + try/except `StreamToolsError` → `typer.Exit(1)`.
- List output columns defined as module-level dict: `{"Header": lambda item: item.field, ...}`. Pass to `output()`.
- Errors print as `f"[red]Error:[/red] {e}"` via `rich.console.Console`.
- `setup` is a top-level command (`app.command()`), not a sub-app.
- `app.py` import order is load-bearing: `load_dotenv()` → `logger.remove()` → typer/commands imports.

## ANTI-PATTERNS

- NEVER declare `--verbose`/`--format` manually on commands — use `@common_options`.
- NEVER reorder imports in `app.py`.
- NEVER add loguru sinks at import time.
- NEVER import library types from CLI into library code (creates cycle).
- NEVER print list output directly — route through `formatting.output()`.
