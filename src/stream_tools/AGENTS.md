# stream_tools (Library)

Auth-agnostic YouTube Live Streaming API library. No CLI deps. Importable as `from stream_tools import YouTubeLiveClient`.

## STRUCTURE

```
stream_tools/
├── client.py          # YouTubeLiveClient — facade, lazy service props
├── exceptions.py      # StreamToolsError → AuthenticationError / APIError / NotFoundError / SetupError
├── auth/
│   ├── oauth.py       # OAuthManager (OPTIONAL — CLI/local only)
│   └── credentials.py # AuthConfig, AuthMethod enum
├── models/
│   ├── common.py      # Enums: PrivacyStatus, LifeCycleStatus, StreamResolution, StreamFrameRate, BroadcastStatus, PageResult[T]
│   ├── broadcast.py
│   ├── stream.py
│   └── chat.py
└── services/
    ├── base.py        # BaseService — _handle_api_error(HttpError → APIError/NotFoundError)
    ├── broadcasts.py  # BroadcastService
    ├── streams.py     # StreamService
    ├── chat.py        # ChatService
    ├── moderators.py  # ModeratorService
    ├── bans.py        # BanService
    ├── channels.py    # ChannelService
    └── setup.py       # SetupService (GCP project/API/OAuth config)
```

## WHERE TO LOOK

| Task | Location |
|---|---|
| Add API method | `services/<resource>.py` — `try/except HttpError` + `self._handle_api_error(e, "<ResourceName>")` |
| Extend model | `models/<resource>.py` — edit dataclass + `from_api_response` |
| Use library standalone | `client.py:YouTubeLiveClient(credentials)` — pass `google.oauth2.credentials.Credentials` |
| Understand error contract | `exceptions.py` — callers catch `StreamToolsError` for blanket handling |
| Auth for local/CLI use only | `auth/oauth.py:OAuthManager` — 3-step chain (env → token file → browser) |

## CONVENTIONS (LIBRARY-SPECIFIC)

- `YouTubeLiveClient` takes `Credentials` directly, NOT an auth manager. Library consumers build their own credentials.
- Services receive pre-built `youtube: Resource`, not credentials. Stateless.
- All services extend `BaseService`. Pattern: `youtube.<resource>().<verb>(part=...).execute()` → wrap in `try/except HttpError`.
- Models are plain dataclasses with `from_api_response(item)` classmethod. No pydantic in models despite pydantic in deps.
- `PageResult[T]` wraps paginated list responses — `.items` + `.next_page_token`.
- `OAuthManager` is **optional** — library code must never require it.

## ANTI-PATTERNS

- NEVER import `typer`, `rich`, or `stream_tools_cli` here.
- NEVER catch `HttpError` without `_handle_api_error` conversion.
- NEVER make `OAuthManager` a required dependency of library code.
