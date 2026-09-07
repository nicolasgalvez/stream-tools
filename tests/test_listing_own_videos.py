"""Listing the channel's own videos, and finding one by title.

`videos.list` has no `mine` parameter — that belongs to `search.list`. Both call
sites here passed it anyway, so `yt video list` raised TypeError on every
invocation, and the committed-upload recovery swallowed the same TypeError in a
broad except and reported "id not found" every time it was asked.

The second one is the expensive failure: it is the path that runs when an upload
commits and the response is lost, and returning None there sends the caller off
to reconcile by hand a video it could have identified.

The route that works is the documented one: the channel's uploads playlist.
"""

from unittest.mock import MagicMock

import pytest

from stream_tools.services.videos import VideoService

UPLOADS = "UUq7LL7Pa1xUlPIpbIyf3Tig"


@pytest.fixture
def mock_youtube():
    return MagicMock()


@pytest.fixture
def videos(mock_youtube):
    return VideoService(mock_youtube)


def channel_with_uploads(mock_youtube, playlist_id=UPLOADS):
    mock_youtube.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"relatedPlaylists": {"uploads": playlist_id}}}]
    }


def playlist_holding(mock_youtube, video_ids, next_page=None):
    page = {"items": [{"contentDetails": {"videoId": v}} for v in video_ids]}
    if next_page:
        page["nextPageToken"] = next_page
    mock_youtube.playlistItems.return_value.list.return_value.execute.return_value = page


def videos_are(mock_youtube, items):
    mock_youtube.videos.return_value.list.return_value.execute.return_value = {"items": items}


def snippet(video_id, title):
    return {
        "id": video_id,
        "snippet": {"title": title, "description": "", "tags": []},
        "status": {"privacyStatus": "public"},
    }


class TestListing:
    def test_never_passes_mine_to_videos_list(self, videos, mock_youtube):
        """The bug itself: videos.list has no such parameter."""
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1"])
        videos_are(mock_youtube, [snippet("a1", "One")])

        videos.list(max_results=5)

        _, kwargs = mock_youtube.videos.return_value.list.call_args
        assert "mine" not in kwargs

    def test_goes_through_the_channel_uploads_playlist(self, videos, mock_youtube):
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1"])
        videos_are(mock_youtube, [snippet("a1", "One")])

        videos.list(max_results=5)

        _, kwargs = mock_youtube.playlistItems.return_value.list.call_args
        assert kwargs["playlistId"] == UPLOADS

    def test_returns_the_videos(self, videos, mock_youtube):
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1", "a2"])
        videos_are(mock_youtube, [snippet("a1", "One"), snippet("a2", "Two")])

        result = videos.list(max_results=5)

        assert [v.id for v in result.items] == ["a1", "a2"]
        assert [v.title for v in result.items] == ["One", "Two"]

    def test_carries_the_page_token_through(self, videos, mock_youtube):
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1"], next_page="PAGE2")
        videos_are(mock_youtube, [snippet("a1", "One")])

        result = videos.list(max_results=5)

        assert result.next_page_token == "PAGE2"

    def test_an_empty_channel_is_not_an_error(self, videos, mock_youtube):
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, [])

        result = videos.list(max_results=5)

        assert result.items == []
        # Nothing to ask about, so nothing is asked.
        mock_youtube.videos.return_value.list.assert_not_called()

    def test_a_channel_with_no_uploads_playlist_is_not_an_error(self, videos, mock_youtube):
        mock_youtube.channels.return_value.list.return_value.execute.return_value = {"items": []}

        result = videos.list(max_results=5)

        assert result.items == []


class TestFindingOneByTitle:
    """The committed-upload recovery path."""

    def test_finds_the_video_it_just_uploaded(self, videos, mock_youtube):
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1", "a2"])
        videos_are(mock_youtube, [snippet("a1", "Something Else"), snippet("a2", "Loom (1990)")])

        assert videos._find_video_id_by_title("Loom (1990)") == "a2"

    def test_never_passes_mine_here_either(self, videos, mock_youtube):
        # The same bad call lived on this path, where a broad except swallowed
        # the TypeError and reported "not found" on every committed upload.
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1"])
        videos_are(mock_youtube, [snippet("a1", "Loom (1990)")])

        videos._find_video_id_by_title("Loom (1990)")

        _, kwargs = mock_youtube.videos.return_value.list.call_args
        assert "mine" not in kwargs

    def test_asks_only_for_the_ids_the_channel_owns(self, videos, mock_youtube):
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1", "a2"])
        videos_are(mock_youtube, [snippet("a1", "x"), snippet("a2", "Loom (1990)")])

        videos._find_video_id_by_title("Loom (1990)")

        _, kwargs = mock_youtube.videos.return_value.list.call_args
        assert kwargs["id"] == "a1,a2"

    def test_a_title_that_is_not_there_yet_is_none_rather_than_a_guess(self, videos, mock_youtube):
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1"])
        videos_are(mock_youtube, [snippet("a1", "Something Else")])

        assert videos._find_video_id_by_title("Loom (1990)") is None

    def test_matches_exactly_rather_than_loosely(self, videos, mock_youtube):
        # A near-match is the wrong video, and returning it would tell a caller
        # its upload succeeded as something it is not.
        channel_with_uploads(mock_youtube)
        playlist_holding(mock_youtube, ["a1"])
        videos_are(mock_youtube, [snippet("a1", "Loom (1990) — Full Soundtrack")])

        assert videos._find_video_id_by_title("Loom (1990)") is None

    def test_an_api_failure_degrades_to_none(self, videos, mock_youtube):
        mock_youtube.channels.return_value.list.return_value.execute.side_effect = RuntimeError(
            "network"
        )

        assert videos._find_video_id_by_title("Loom (1990)") is None
