# PROJECT KNOWLEDGE BASE

**Generated:** 2026-06-23
**Commit:** b4a9391
**Branch:** main

> See `CLAUDE.md` for Claude-specific operational guidance. This file is the universal knowledge base.

## OVERVIEW

YouTube Live Stream management — Python 3.11+ library (`stream_tools`) + Typer CLI (`stream_tools_cli`, entrypoint `yt`). Wraps `googleapiclient` for broadcasts, streams, chat, moderators, bans, channels. Hatchling build, ruff lint, no CI yet.

## STRUCTURE

```
stream-tools/
├── src/
│   ├── stream_tools/          # Library — auth-agnostic, no CLI deps
│   │   ├── auth/              # OAuthManager (optional CLI/local utility)
│   │   ├── models/            # Dataclasses + from_api_response()
│   │   ├── services/          # One BaseService per YouTube resource
│   │   ├── client.py          # YouTubeLiveClient facade (lazy services)
│   │   └── exceptions.py      # StreamToolsError hierarchy
│   └── stream_tools_cli/      # Thin Typer wrapper — only place auth is wired
│       ├── commands/          # One module per command group
│       ├── app.py             # Typer app, .env load, sub-app registration
│       ├── state.py           # @common_options signature-injection decorator
│       ├── formatting.py      # output(items, columns) — table/json/csv/ids
│       ├── azuracast.py       # AzuraCast REST client (env-driven, optional)
│       └── notifications.py   # Discord webhook poster
├── tests/                     # pytest, no conftest, class-grouped
├── scripts/
│   ├── docs                   # pdoc wrapper (serve/build)
│   └── export-yt-credentials  # token.json → .env (BSD sed + jq)
├── docs/                      # Generated API reference (cli.md, library.md, models.md)
├── Dockerfile                 # Multi-stage: install → slim runtime w/ site-packages + yt
└── docker-compose.yml         # Mounts ~/.config/stream-tools, runs `yt stream watch`
```

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Add YouTube API operation | `src/stream_tools/services/<resource>.py` + matching `commands/<resource>.py` | Follow existing service+command pattern |
| Add model field | `src/stream_tools/models/<resource>.py` | Update `from_api_response` |
| Wire global CLI option | `src/stream_tools_cli/state.py` `@common_options` | Signature injection — see file header |
| Render list output | `src/stream_tools_cli/formatting.py` `output()` | Funnel all list commands through this |
| Handle API error | `BaseService._handle_api_error(e, "<ResourceName>")` | 404 → `NotFoundError`, else `APIError` |
| Auth flow | `src/stream_tools/auth/oauth.py` `OAuthManager.auto_authenticate()` | env → token file → browser |
| Stream watch / auto-restart | `src/stream_tools_cli/commands/streams.py` `watch` command | Largest file (551 lines) — AzuraCast + Discord hooks |

## CODE MAP

| Symbol | Type | Location | Role |
|---|---|---|---|
| `YouTubeLiveClient` | class | `stream_tools/client.py` | Library facade, lazy service props |
| `BaseService` | class | `stream_tools/services/base.py` | HttpError → stream_tools exception |
| `OAuthManager` | class | `stream_tools/auth/oauth.py` | 3-step auth priority chain |
| `StreamToolsError` | base exc | `stream_tools/exceptions.py` | Root of error hierarchy |
| `app` | Typer | `stream_tools_cli/app.py` | `yt` entrypoint, sub-app registration |
| `common_options` | decorator | `stream_tools_cli/state.py` | Injects `--verbose`/`--format` via signature manipulation |
| `output()` | func | `stream_tools_cli/formatting.py` | table/json/csv/ids dispatch on `state.config.format` |
| `get_client()` | func | `stream_tools_cli/commands/__init__.py` | OAuthManager → YouTubeLiveClient bridge |

## CONVENTIONS

- **Library/CLI split is intentional**: `stream_tools/` MUST NOT import `typer`/`rich`/`stream_tools_cli`. CLI is a thin wrapper.
- **Services are stateless**: receive pre-built `youtube` Resource, not credentials. One service per YouTube resource, named `<Resource>Service`.
- **Models are dataclasses**: `from_api_response(item)` classmethod constructs from raw API JSON. Enums live in `models/common.py`.
- **Commands are uniform**: `@common_options` + `get_client()` + `formatting.output()`. Map `StreamToolsError` → `typer.Exit(1)` with `[red]Error:[/red]` prefix.
- **Lazy initialization**: `YouTubeLiveClient` builds the `googleapiclient` Resource on first property access; each service is instantiated on first property access.
- **Logging**: `loguru.logger` only. `app.py` removes default sink at import time; `state._process_common_options` re-adds stderr sink at DEBUG when `-v`.

## ANTI-PATTERNS (THIS PROJECT)

- DO NOT add new sinks at import time — only `state._process_common_options` re-adds stderr.
- DO NOT reorder imports in `app.py`: `load_dotenv()` → `logger.remove()` → everything else. Breaking this order breaks logging.
- DO NOT make `stream_tools/` depend on `typer`, `rich`, or `stream_tools_cli`.
- DO NOT declare `--verbose`/`--format` on commands manually — use `@common_options`.
- DO NOT add type-suppression (`as any`-equivalents: bare `# type: ignore` without comment, `Any` to silence).
- DO NOT catch `HttpError` without routing through `self._handle_api_error`.
- DO NOT print list output directly — route through `formatting.output(items, columns)`.

## COMMANDS

```bash
# Dev install
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests (pytest defaults — no [tool.pytest] section, no conftest.py)
pytest tests/ -v
pytest tests/test_services.py::TestBroadcastServiceList::test_list_returns_broadcasts -v

# Lint
ruff check src/ tests/

# CLI from dev venv
yt --help

# Docs (pdoc)
scripts/docs           # serve http://localhost:8080
scripts/docs build     # static HTML to docs/
```

## NOTES

- **No CI workflows** (`.github/workflows/` absent). No `Makefile`.
- **`tests/` is a package** (`__init__.py` present) — uncommon for plain pytest, intentional here.
- **`scripts/export-yt-credentials`** is macOS/BSD-only (`sed -i ''`) and depends on `jq`.
- **Docker runtime command** uses shell expansion: `yt stream watch $(yt stream list --format ids | head -1)`.
- **`__pycache__`/`.pyc` present under `src/`** — should be gitignored; currently tracked accidentally.
- **Auth priority**: env vars > `~/.config/stream-tools/token.json` > interactive browser. Env vars win for headless deploys.
- **`pyproject.toml` `[tool.hatch.build.targets.wheel]`** lists both `src/stream_tools` and `src/stream_tools_cli` as packages — single distribution, two importable top-level packages.
