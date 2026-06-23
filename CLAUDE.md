# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Dev install (Python 3.11)
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests
pytest tests/ -v
pytest tests/test_services.py::TestBroadcastServiceList -v   # single class
pytest tests/test_services.py::TestBroadcastServiceList::test_list_returns_broadcasts   # single test

# Lint
ruff check src/ tests/

# API reference docs (pdoc)
scripts/docs           # serve at http://localhost:8080
scripts/docs build     # generate static HTML to docs/

# Run the CLI from the dev venv
yt --help
```

The console script `yt` is defined in `pyproject.toml` as `stream_tools_cli.app:app`. Production install is via `pipx install .`.

## Architecture

Two top-level packages under `src/`, intentionally separated:

- **`stream_tools/`** — Library. Contains no CLI dependencies and can be used from any context (web server, bot, script). The library exposes a single `YouTubeLiveClient(credentials)` facade that takes a `google.oauth2.credentials.Credentials` directly — it does NOT manage auth.
- **`stream_tools_cli/`** — Thin Typer-based CLI wrapper around the library. Holds all interactive/Rich/output-format logic and the only place `OAuthManager` is wired in by default.

### Library layout (`stream_tools/`)

- `client.py` — `YouTubeLiveClient` facade. Lazily builds the `googleapiclient` Resource on first access, then lazily instantiates one service per YouTube resource (`broadcasts`, `streams`, `chat`, `moderators`, `bans`, `channels`).
- `services/` — One `BaseService` subclass per YouTube API resource. Services receive the pre-built `youtube` Resource (not credentials), call `youtube.<resource>().<verb>(...).execute()`, and convert `HttpError` → `APIError`/`NotFoundError` via `BaseService._handle_api_error`. Models are constructed from raw API JSON via `Model.from_api_response(item)`.
- `models/` — Plain dataclasses with `from_api_response()` classmethods. Enums (`PrivacyStatus`, `LifeCycleStatus`, `StreamResolution`, `StreamFrameRate`, `BroadcastStatus`) live in `models/common.py`. `PageResult[T]` wraps paginated list responses.
- `auth/oauth.py` — `OAuthManager` is an **optional** utility for local/CLI use only. It implements a 3-step auth chain: env vars (`YT_CLIENT_ID`/`YT_CLIENT_SECRET`/`YT_REFRESH_TOKEN`) → cached token (`~/.config/stream-tools/token.json`) → interactive browser flow. Library consumers should construct `Credentials` themselves and pass to `YouTubeLiveClient`.
- `exceptions.py` — Error hierarchy rooted at `StreamToolsError`; includes `AuthenticationError`, `APIError`, `NotFoundError`.

### CLI layout (`stream_tools_cli/`)

- `app.py` — Top-level Typer app. **Loads `.env` and removes loguru's default handler before importing anything else** — keep that ordering. Registers sub-apps from `commands/`.
- `commands/` — One module per sub-app (`auth`, `broadcasts`, `streams`, `chat`, `moderators`, `bans`, `azuracast`, `channels`, `setup`). Every command calls `get_client()` (in `commands/__init__.py`) which runs `OAuthManager().auto_authenticate()` and returns a `YouTubeLiveClient`.
- `state.py` — Global `config` (format/verbose) plus the `@common_options` decorator. The decorator uses `inspect.Signature` manipulation to inject `--verbose`/`--format` parameters that Typer can discover — when adding new commands, just apply `@common_options` and read `state.config` for format/verbosity rather than declaring those options manually.
- `formatting.py` — `output(items, columns, title=...)` renders to table/json/csv/ids based on `state.config.format`. New commands should funnel list output through this helper.
- `azuracast.py` — Separate `AzuraCastConfig.from_env()` + REST client used by the `yt azura` and `yt stream watch` commands. Returns `None` when env vars are unset; commands degrade gracefully.
- `notifications.py` — Discord webhook poster used by `yt stream watch --discord URL`.

### Adding a new YouTube operation

1. If a new model field is needed, extend the dataclass in `stream_tools/models/<resource>.py` and update its `from_api_response`.
2. Add the method to the corresponding `*Service` in `stream_tools/services/<resource>.py`. Always wrap API calls in `try/except HttpError` and call `self._handle_api_error(e, "<ResourceName>")`. Pass the right `part=` string for what you read/write.
3. Add a Typer command in `stream_tools_cli/commands/<resource>.py`, decorate with `@common_options`, call `get_client()`, and route list/get output through `formatting.output(...)`. Map `StreamToolsError` to `typer.Exit(1)` with a `[red]Error:[/red]` message.

### Auth headless deploy

The Docker setup (`Dockerfile` + `docker-compose.yml`) mounts `~/.config/stream-tools` into the container and runs `yt stream watch $(yt stream list --format ids | head -1)`. For VPS/headless use, run `./scripts/export-yt-credentials` locally to materialize `YT_CLIENT_ID`/`YT_CLIENT_SECRET`/`YT_REFRESH_TOKEN` into `.env`, then copy `.env` to the host — the env-var auth method will take priority over the token file.

## Conventions

- Python 3.11+, ruff `line-length = 100`, `src = ["src"]`.
- Logging: use `loguru.logger`. `app.py` removes the default sink; `state._process_common_options` re-adds a stderr sink at DEBUG when `-v` is set. Do not add other sinks at import time.
- Library code must not depend on `typer`, `rich`, or anything in `stream_tools_cli`.
