"""Authentication configuration and types."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class AuthMethod(Enum):
    """Authentication method used to obtain credentials.

    Methods are tried in priority order: ENVIRONMENT -> TOKEN_FILE -> INTERACTIVE.
    """

    ENVIRONMENT = "environment"
    TOKEN_FILE = "token_file"
    INTERACTIVE = "interactive"


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "stream-tools"
DEFAULT_TOKEN_PATH = DEFAULT_CONFIG_DIR / "token.json"
DEFAULT_CLIENT_SECRET_PATH = DEFAULT_CONFIG_DIR / "client_secret.json"

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


@dataclass
class AuthConfig:
    """Configuration for YouTube API authentication.

    Attributes:
        config_dir: Directory for storing auth files.
        token_path: Path to the cached OAuth token file.
        client_secret_path: Path to the Google OAuth client secret JSON.
        scopes: OAuth scopes to request.
        client_id_env: Environment variable name for client ID.
        client_secret_env: Environment variable name for client secret.
        refresh_token_env: Environment variable name for refresh token.
    """

    config_dir: Path = field(default_factory=lambda: DEFAULT_CONFIG_DIR)
    token_path: Path = field(default_factory=lambda: DEFAULT_TOKEN_PATH)
    client_secret_path: Path = field(default_factory=lambda: DEFAULT_CLIENT_SECRET_PATH)
    scopes: list[str] = field(default_factory=lambda: list(YOUTUBE_SCOPES))

    # Environment variable names
    client_id_env: str = "YT_CLIENT_ID"
    client_secret_env: str = "YT_CLIENT_SECRET"
    refresh_token_env: str = "YT_REFRESH_TOKEN"

    def ensure_config_dir(self) -> None:
        """Create the config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
