"""Playlist operations: the scheduler needs 'add to playlist(s)' at import time."""

import json
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from stream_tools.exceptions import APIError
from stream_tools.services.playlists import Playlist, PlaylistService


@pytest.fixture
def mock_youtube():
    return MagicMock()


@pytest.fixture
def playlists(mock_youtube):
    return PlaylistService(mock_youtube)


def api_error(status=403, reason="forbidden"):
    resp = MagicMock()
    resp.status = status
    content = json.dumps({"error": {"code": status, "errors": [{"reason": reason}]}}).encode()
    return HttpError(resp, content)


def lists_return(mock_youtube, items, next_token=None):
    mock_youtube.playlists.return_value.list.return_value.execute.return_value = {
        "items": items,
        "nextPageToken": next_token,
        "pageInfo": {"totalResults": len(items)},
    }


PLAYLIST_ITEM = {
    "id": "PLI-1",
    "snippet": {"title": "VGM Top 50", "description": "singles", "resourceId": {}},
    "status": {"privacyStatus": "public"},
    "contentDetails": {"itemCount": 34},
}


class TestListPlaylists:
    def test_returns_playlists(self, playlists, mock_youtube):
        lists_return(mock_youtube, [PLAYLIST_ITEM])

        result = playlists.list()

        assert [p.title for p in result.items] == ["VGM Top 50"]

    def test_parses_item_count_and_privacy(self, playlists, mock_youtube):
        lists_return(mock_youtube, [PLAYLIST_ITEM])

        playlist = playlists.list().items[0]

        assert playlist.id == "PLI-1"
        assert playlist.item_count == 34
        assert playlist.privacy_status == "public"

    def test_passes_the_page_token_through(self, playlists, mock_youtube):
        lists_return(mock_youtube, [], next_token="NEXT")

        playlists.list(page_token="TOKEN")

        kwargs = mock_youtube.playlists.return_value.list.call_args.kwargs
        assert kwargs["pageToken"] == "TOKEN"
        assert kwargs["mine"] is True

    def test_surfaces_the_next_page_token(self, playlists, mock_youtube):
        lists_return(mock_youtube, [PLAYLIST_ITEM], next_token="NEXT")

        assert playlists.list().next_page_token == "NEXT"

    def test_api_errors_become_api_errors(self, playlists, mock_youtube):
        mock_youtube.playlists.return_value.list.return_value.execute.side_effect = api_error()

        with pytest.raises(APIError):
            playlists.list()


class TestAddVideo:
    def test_inserts_the_video_into_the_playlist(self, playlists, mock_youtube):
        insert = mock_youtube.playlistItems.return_value.insert
        insert.return_value.execute.return_value = {"id": "ITEM-9"}

        playlists.add_video("PLI-1", "vid123")

        body = insert.call_args.kwargs["body"]
        assert body["snippet"]["playlistId"] == "PLI-1"
        assert body["snippet"]["resourceId"] == {"kind": "youtube#video", "videoId": "vid123"}

    def test_returns_the_new_playlist_item_id(self, playlists, mock_youtube):
        mock_youtube.playlistItems.return_value.insert.return_value.execute.return_value = {
            "id": "ITEM-9"
        }

        assert playlists.add_video("PLI-1", "vid123") == "ITEM-9"

    def test_an_explicit_position_is_honoured(self, playlists, mock_youtube):
        insert = mock_youtube.playlistItems.return_value.insert
        insert.return_value.execute.return_value = {"id": "ITEM-9"}

        playlists.add_video("PLI-1", "vid123", position=0)

        assert insert.call_args.kwargs["body"]["snippet"]["position"] == 0

    def test_position_is_omitted_when_not_given(self, playlists, mock_youtube):
        insert = mock_youtube.playlistItems.return_value.insert
        insert.return_value.execute.return_value = {"id": "ITEM-9"}

        playlists.add_video("PLI-1", "vid123")

        assert "position" not in insert.call_args.kwargs["body"]["snippet"]

    def test_api_errors_become_api_errors(self, playlists, mock_youtube):
        mock_youtube.playlistItems.return_value.insert.return_value.execute.side_effect = (
            api_error()
        )

        with pytest.raises(APIError):
            playlists.add_video("PLI-1", "vid123")


def items_return(mock_youtube, videos):
    mock_youtube.playlistItems.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": f"ITEM-{i}", "snippet": {"resourceId": {"videoId": v}}}
            for i, v in enumerate(videos)
        ],
        "pageInfo": {"totalResults": len(videos)},
    }


class TestFindAndRemove:
    def test_find_item_returns_the_playlist_item_id(self, playlists, mock_youtube):
        items_return(mock_youtube, ["other", "vid123"])

        assert playlists.find_item("PLI-1", "vid123") == "ITEM-1"

    def test_find_item_returns_none_when_absent(self, playlists, mock_youtube):
        items_return(mock_youtube, ["other"])

        assert playlists.find_item("PLI-1", "vid123") is None

    def test_remove_video_deletes_by_playlist_item_id(self, playlists, mock_youtube):
        playlists.remove_video("ITEM-9")

        assert mock_youtube.playlistItems.return_value.delete.call_args.kwargs["id"] == "ITEM-9"

    def test_remove_video_by_video_id_finds_then_deletes(self, playlists, mock_youtube):
        items_return(mock_youtube, ["vid123"])

        assert playlists.remove_video_by_video_id("PLI-1", "vid123") is True
        assert mock_youtube.playlistItems.return_value.delete.call_args.kwargs["id"] == "ITEM-0"

    def test_remove_video_by_video_id_reports_a_miss(self, playlists, mock_youtube):
        items_return(mock_youtube, [])

        assert playlists.remove_video_by_video_id("PLI-1", "vid123") is False
        mock_youtube.playlistItems.return_value.delete.assert_not_called()


class TestPlaylistModel:
    def test_parses_a_missing_content_details_block(self):
        playlist = Playlist.from_api_response({"id": "X", "snippet": {"title": "T"}})

        assert playlist.item_count == 0
        assert playlist.description == ""
