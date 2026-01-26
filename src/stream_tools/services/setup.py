"""Setup service for GCP project creation and YouTube API enablement."""

import secrets
import shutil
import subprocess
from pathlib import Path

from stream_tools.auth.credentials import DEFAULT_CLIENT_SECRET_PATH, DEFAULT_CONFIG_DIR
from stream_tools.exceptions import SetupError


class SetupService:
    """Handles GCP project creation and YouTube API enablement via gcloud CLI."""

    def generate_project_id(self) -> str:
        """Generate a default GCP project ID."""
        return f"stream-tools-{secrets.token_hex(3)}"

    def check_gcloud_installed(self) -> bool:
        """Check if gcloud CLI is available."""
        return shutil.which("gcloud") is not None

    def get_gcloud_account(self) -> str | None:
        """Get the active gcloud account, or None if not authenticated."""
        try:
            result = self._run_gcloud([
                "auth", "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ])
            return result or None
        except SetupError:
            return None

    def list_gcloud_accounts(self) -> list[str]:
        """List all authenticated gcloud accounts."""
        try:
            result = self._run_gcloud([
                "auth", "list",
                "--format=value(account)",
            ])
            return [a for a in result.splitlines() if a.strip()]
        except SetupError:
            return []

    def set_gcloud_account(self, account: str) -> None:
        """Set the active gcloud account."""
        self._run_gcloud(["config", "set", "account", account])

    def create_project(self, project_id: str) -> None:
        """Create a GCP project."""
        self._run_gcloud(["projects", "create", project_id])

    def enable_youtube_api(self, project_id: str) -> None:
        """Enable the YouTube Data API v3 for the project."""
        self._run_gcloud([
            "services", "enable", "youtube.googleapis.com",
            f"--project={project_id}",
        ])

    def get_consent_screen_url(self, project_id: str) -> str:
        """Get the URL to configure the OAuth consent screen."""
        return (
            f"https://console.cloud.google.com/auth/branding"
            f"?project={project_id}"
        )

    def get_test_users_url(self, project_id: str) -> str:
        """Get the URL to manage OAuth test users."""
        return (
            f"https://console.cloud.google.com/auth/audience"
            f"?project={project_id}"
        )

    def get_credentials_url(self, project_id: str) -> str:
        """Get the URL to create OAuth credentials in the console."""
        return (
            f"https://console.cloud.google.com/apis/credentials/oauthclient"
            f"?project={project_id}"
        )

    def store_client_secret(self, json_path: Path) -> Path:
        """Copy client_secret.json to the config directory."""
        if not json_path.exists():
            raise SetupError(f"File not found: {json_path}")

        dest = DEFAULT_CLIENT_SECRET_PATH
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(json_path, dest)
        return dest

    def _run_gcloud(self, args: list[str]) -> str:
        """Run a gcloud command and return stdout."""
        cmd = ["gcloud"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise SetupError(
                f"gcloud command failed: {' '.join(cmd)}\n{e.stderr}"
            ) from e
