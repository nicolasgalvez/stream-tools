"""OAuth2 authentication manager for YouTube API."""

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from stream_tools.auth.credentials import AuthConfig, AuthMethod
from stream_tools.exceptions import AuthenticationError


class OAuthManager:
    """Manages OAuth2 authentication with priority chain.

    Tries authentication methods in order:
    1. Environment variables (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN)
    2. Cached token file (~/.config/stream-tools/token.json)
    3. Interactive browser flow (opens browser for OAuth consent)

    Args:
        config: Optional AuthConfig to override default paths and env var names.

    Example:
        ```python
        auth = OAuthManager()
        auth.auto_authenticate()
        client = YouTubeLiveClient(auth.credentials)
        ```
    """

    def __init__(self, config: AuthConfig | None = None):
        self.config = config or AuthConfig()
        self._credentials: Credentials | None = None

    @property
    def credentials(self) -> Credentials:
        """Get current credentials.

        Raises:
            AuthenticationError: If not yet authenticated.
        """
        if self._credentials is None:
            raise AuthenticationError("Not authenticated. Run 'yt auth login' first.")
        return self._credentials

    @property
    def is_authenticated(self) -> bool:
        """Check if valid (non-expired) credentials are available."""
        return self._credentials is not None and self._credentials.valid

    def auto_authenticate(self) -> AuthMethod:
        """Try all auth methods in priority order.

        Returns:
            The AuthMethod that succeeded.

        Raises:
            AuthenticationError: If all methods fail (e.g. no credentials
                available and interactive flow cannot run).
        """
        # 1. Try environment variables
        try:
            self._authenticate_from_env()
            return AuthMethod.ENVIRONMENT
        except AuthenticationError:
            pass

        # 2. Try cached token file
        try:
            self._authenticate_from_token_file()
            return AuthMethod.TOKEN_FILE
        except AuthenticationError:
            pass

        # 3. Interactive browser flow
        self._authenticate_interactive()
        return AuthMethod.INTERACTIVE

    def authenticate(self, method: AuthMethod | None = None) -> AuthMethod:
        """Authenticate using a specific method, or auto if None.

        Args:
            method: The auth method to use, or None for auto-detection.

        Returns:
            The AuthMethod that was used.
        """
        if method is None:
            return self.auto_authenticate()

        match method:
            case AuthMethod.ENVIRONMENT:
                self._authenticate_from_env()
            case AuthMethod.TOKEN_FILE:
                self._authenticate_from_token_file()
            case AuthMethod.INTERACTIVE:
                self._authenticate_interactive()

        return method

    def authenticate_with_token(
        self,
        refresh_token: str,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        """Authenticate using a directly-provided refresh token.

        Reads client_id/secret from client_secret.json if not provided.

        Args:
            refresh_token: A valid OAuth2 refresh token.
            client_id: Google OAuth client ID, or None to read from file.
            client_secret: Google OAuth client secret, or None to read from file.

        Raises:
            AuthenticationError: If credentials cannot be built or refreshed.
        """
        if not client_id or not client_secret:
            client_id, client_secret = self._read_client_secret_file()

        self._credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=self.config.scopes,
        )
        self._refresh_if_needed()
        self._save_credentials()

    def _read_client_secret_file(self) -> tuple[str, str]:
        """Read client_id and client_secret from the stored client_secret.json."""
        if not self.config.client_secret_path.exists():
            raise AuthenticationError(
                f"Client secret file not found: {self.config.client_secret_path}\n"
                "Provide --client-id and --client-secret, or run 'yt setup' first."
            )
        data = json.loads(self.config.client_secret_path.read_text())
        # Google's format: {"installed": {"client_id": ..., "client_secret": ...}}
        installed = data.get("installed", data.get("web", {}))
        client_id = installed.get("client_id")
        client_secret = installed.get("client_secret")
        if not client_id or not client_secret:
            raise AuthenticationError("Invalid client_secret.json: missing client_id or client_secret")
        return client_id, client_secret

    def logout(self) -> None:
        """Remove cached credentials and delete the token file."""
        self._credentials = None
        if self.config.token_path.exists():
            self.config.token_path.unlink()

    def get_status(self) -> dict[str, str | bool]:
        """Return current auth status info.

        Returns:
            A dict with keys: authenticated, token_file_exists,
            env_configured, client_secret_exists.
        """
        return {
            "authenticated": self.is_authenticated,
            "token_file_exists": self.config.token_path.exists(),
            "env_configured": all(
                os.environ.get(v)
                for v in [
                    self.config.client_id_env,
                    self.config.client_secret_env,
                    self.config.refresh_token_env,
                ]
            ),
            "client_secret_exists": self.config.client_secret_path.exists(),
        }

    def _authenticate_from_env(self) -> None:
        """Build credentials from environment variables."""
        client_id = os.environ.get(self.config.client_id_env)
        client_secret = os.environ.get(self.config.client_secret_env)
        refresh_token = os.environ.get(self.config.refresh_token_env)

        if not all([client_id, client_secret, refresh_token]):
            raise AuthenticationError(
                "Environment variables not set: "
                f"{self.config.client_id_env}, {self.config.client_secret_env}, "
                f"{self.config.refresh_token_env}"
            )

        self._credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=self.config.scopes,
        )
        self._refresh_if_needed()

    def _authenticate_from_token_file(self) -> None:
        """Load credentials from cached token file."""
        if not self.config.token_path.exists():
            raise AuthenticationError(f"Token file not found: {self.config.token_path}")

        self._credentials = Credentials.from_authorized_user_file(
            str(self.config.token_path), self.config.scopes
        )
        self._refresh_if_needed()
        # Re-save in case the token was refreshed
        self._save_credentials()

    def _authenticate_interactive(self, force_prompt: bool = False) -> None:
        """Run interactive browser-based OAuth flow."""
        if not self.config.client_secret_path.exists():
            raise AuthenticationError(
                f"Client secret file not found: {self.config.client_secret_path}\n"
                "Run 'yt setup' to configure OAuth credentials."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.config.client_secret_path), self.config.scopes
        )
        # force_prompt=True shows account/channel picker even if already authorized
        kwargs = {}
        if force_prompt:
            kwargs["prompt"] = "consent"
        self._credentials = flow.run_local_server(port=0, **kwargs)
        self._save_credentials()

    def reauth(self) -> None:
        """Force re-authentication, showing the account/channel picker."""
        self._authenticate_interactive(force_prompt=True)

    def _refresh_if_needed(self) -> None:
        """Refresh credentials if expired."""
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
            except Exception as e:
                self._credentials = None
                raise AuthenticationError(f"Failed to refresh token: {e}") from e

    def _save_credentials(self) -> None:
        """Save credentials to the token file for later reuse."""
        if self._credentials is None:
            return
        self.config.ensure_config_dir()
        token_data = {
            "token": self._credentials.token,
            "refresh_token": self._credentials.refresh_token,
            "token_uri": self._credentials.token_uri,
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "scopes": self._credentials.scopes,
        }
        self.config.token_path.write_text(json.dumps(token_data))

    def run_flow_for_client_secret(self, client_secret_path: Path) -> None:
        """Run OAuth flow using a specific client_secret.json file.

        Used during setup to immediately obtain tokens after downloading credentials.

        Args:
            client_secret_path: Path to the client_secret.json file to use.
        """
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path), self.config.scopes
        )
        self._credentials = flow.run_local_server(port=0)
        self._save_credentials()
