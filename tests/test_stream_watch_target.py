"""`yt stream watch` watches a configured stream, never one picked by list position.

The compose service once ran `yt stream watch $(yt stream list | head -1)`. When
YouTube listed an idle stream first, the monitor saw `noData`, restarted the
healthy AzuraCast backend every few minutes, and posted each restart to Discord.
So the stream ID comes from the argument or from YT_WATCH_STREAM_ID, and with
neither the command refuses to start before it touches AzuraCast or Discord.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from stream_tools_cli.commands.streams import app
from stream_tools_cli.exit_codes import EXIT_ERROR, EXIT_OK

ENV_VAR = "YT_WATCH_STREAM_ID"

runner = CliRunner()


@pytest.fixture
def client():
    """A client whose stream is healthy once, then the operator presses Ctrl+C."""
    client = MagicMock()
    stream = MagicMock()
    stream.title = "Default stream key"
    stream.health_status.value = "good"
    client.streams.get.side_effect = [stream, KeyboardInterrupt()]
    client.broadcasts.list.return_value.items = []
    return client


def invoke_watch(client, args, env):
    with (
        patch("stream_tools_cli.commands.streams.get_client", return_value=client) as get_client,
        patch("stream_tools_cli.azuracast.get_azuracast_client", return_value=None) as azura,
        patch("stream_tools_cli.notifications.send_discord_notification") as discord,
        patch("stream_tools_cli.notifications.get_discord_webhook_url", return_value=None),
        patch("time.sleep"),
    ):
        result = runner.invoke(app, ["watch", *args], env=env)
    return result, get_client, azura, discord


class TestWatchWithoutAStreamId:
    def test_it_refuses_to_start(self, client):
        result, *_ = invoke_watch(client, [], env={ENV_VAR: None})

        assert result.exit_code == EXIT_ERROR

    def test_it_names_the_missing_setting(self, client):
        result, *_ = invoke_watch(client, [], env={ENV_VAR: None})

        assert ENV_VAR in result.output

    def test_a_blank_setting_counts_as_missing(self, client):
        result, *_ = invoke_watch(client, [], env={ENV_VAR: "   "})

        assert result.exit_code == EXIT_ERROR
        assert ENV_VAR in result.output

    def test_it_never_reaches_youtube_azuracast_or_discord(self, client):
        _, get_client, azura, discord = invoke_watch(
            client, ["--discord", "https://discord.example/hook"], env={ENV_VAR: None}
        )

        get_client.assert_not_called()
        azura.assert_not_called()
        discord.assert_not_called()


class TestWatchTarget:
    def test_it_watches_the_configured_stream(self, client):
        result, *_ = invoke_watch(client, ["--no-restart"], env={ENV_VAR: "configured-id"})

        assert result.exit_code == EXIT_OK
        assert {c.args[0] for c in client.streams.get.call_args_list} == {"configured-id"}

    def test_an_explicit_argument_overrides_the_setting(self, client):
        result, *_ = invoke_watch(
            client, ["explicit-id", "--no-restart"], env={ENV_VAR: "configured-id"}
        )

        assert result.exit_code == EXIT_OK
        assert {c.args[0] for c in client.streams.get.call_args_list} == {"explicit-id"}

    def test_it_never_lists_streams_to_pick_one(self, client):
        invoke_watch(client, ["--no-restart"], env={ENV_VAR: "configured-id"})

        client.streams.list.assert_not_called()
