"""Tests for service classes with mocked YouTube API."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from stream_tools.exceptions import APIError, NotFoundError
from stream_tools.models.common import (
    BroadcastStatus,
    LifeCycleStatus,
    PrivacyStatus,
    StreamFrameRate,
    StreamResolution,
)
from stream_tools.services.broadcasts import BroadcastService
from stream_tools.services.chat import ChatService
from stream_tools.services.streams import StreamService


@pytest.fixture
def mock_youtube():
    return MagicMock()


@pytest.fixture
def broadcast_service(mock_youtube):
    return BroadcastService(mock_youtube)


@pytest.fixture
def stream_service(mock_youtube):
    return StreamService(mock_youtube)


@pytest.fixture
def chat_service(mock_youtube):
    return ChatService(mock_youtube)


# ─── Broadcast Service ────────────────────────────────────────────────────────


class TestBroadcastServiceList:
    def test_list_returns_broadcasts(self, broadcast_service, mock_youtube):
        mock_youtube.liveBroadcasts().list().execute.return_value = {
            "items": [
                {
                    "id": "b1",
                    "snippet": {"title": "Stream 1", "scheduledStartTime": "2026-01-24T10:00:00Z"},
                    "status": {"privacyStatus": "private", "lifeCycleStatus": "created"},
                    "contentDetails": {},
                },
                {
                    "id": "b2",
                    "snippet": {"title": "Stream 2"},
                    "status": {"privacyStatus": "public", "lifeCycleStatus": "live"},
                    "contentDetails": {},
                },
            ],
            "pageInfo": {"totalResults": 2},
        }

        result = broadcast_service.list(status=BroadcastStatus.ALL)

        assert len(result.items) == 2
        assert result.items[0].id == "b1"
        assert result.items[1].title == "Stream 2"
        assert result.total_results == 2

    def test_list_empty(self, broadcast_service, mock_youtube):
        mock_youtube.liveBroadcasts().list().execute.return_value = {
            "items": [],
            "pageInfo": {"totalResults": 0},
        }

        result = broadcast_service.list()

        assert result.items == []
        assert result.total_results == 0

    def test_list_api_error(self, broadcast_service, mock_youtube):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 403
        error = HttpError(resp, b"forbidden")

        mock_youtube.liveBroadcasts().list().execute.side_effect = error

        with pytest.raises(APIError) as exc_info:
            broadcast_service.list()
        assert exc_info.value.status_code == 403


class TestBroadcastServiceCreate:
    def test_create_broadcast(self, broadcast_service, mock_youtube):
        mock_youtube.liveBroadcasts().insert().execute.return_value = {
            "id": "new-b",
            "snippet": {
                "title": "New Broadcast",
                "description": "desc",
                "scheduledStartTime": "2026-02-01T15:00:00Z",
            },
            "status": {"privacyStatus": "private", "lifeCycleStatus": "created"},
            "contentDetails": {},
        }

        result = broadcast_service.create(
            title="New Broadcast",
            scheduled_start=datetime(2026, 2, 1, 15, 0, tzinfo=timezone.utc),
            privacy=PrivacyStatus.PRIVATE,
            description="desc",
        )

        assert result.id == "new-b"
        assert result.title == "New Broadcast"
        assert result.privacy == PrivacyStatus.PRIVATE


class TestBroadcastServiceUpdate:
    def test_update_title(self, broadcast_service, mock_youtube):
        # First call: fetch current
        mock_youtube.liveBroadcasts().list().execute.return_value = {
            "items": [{
                "id": "b1",
                "snippet": {"title": "Old Title", "description": ""},
                "status": {"privacyStatus": "private", "lifeCycleStatus": "created"},
                "contentDetails": {},
            }],
        }
        # Second call: update
        mock_youtube.liveBroadcasts().update().execute.return_value = {
            "id": "b1",
            "snippet": {"title": "New Title", "description": ""},
            "status": {"privacyStatus": "private", "lifeCycleStatus": "created"},
            "contentDetails": {},
        }

        result = broadcast_service.update("b1", title="New Title")

        assert result.title == "New Title"

    def test_update_not_found(self, broadcast_service, mock_youtube):
        mock_youtube.liveBroadcasts().list().execute.return_value = {"items": []}

        with pytest.raises(NotFoundError):
            broadcast_service.update("nonexistent", title="X")


class TestBroadcastServiceDelete:
    def test_delete_success(self, broadcast_service, mock_youtube):
        mock_youtube.liveBroadcasts().delete().execute.return_value = None

        # Should not raise
        broadcast_service.delete("b1")


class TestBroadcastServiceBind:
    def test_bind_stream(self, broadcast_service, mock_youtube):
        mock_youtube.liveBroadcasts().bind().execute.return_value = {
            "id": "b1",
            "snippet": {"title": "Bound"},
            "status": {"privacyStatus": "private", "lifeCycleStatus": "created"},
            "contentDetails": {"boundStreamId": "s1"},
        }

        result = broadcast_service.bind("b1", "s1")

        assert result.bound_stream_id == "s1"


class TestBroadcastServiceTransition:
    def test_transition_to_live(self, broadcast_service, mock_youtube):
        mock_youtube.liveBroadcasts().transition().execute.return_value = {
            "id": "b1",
            "snippet": {"title": "Going Live"},
            "status": {"privacyStatus": "public", "lifeCycleStatus": "live"},
            "contentDetails": {},
        }

        result = broadcast_service.transition("b1", LifeCycleStatus.LIVE)

        assert result.life_cycle_status == LifeCycleStatus.LIVE


# ─── Stream Service ───────────────────────────────────────────────────────────


class TestStreamServiceList:
    def test_list_streams(self, stream_service, mock_youtube):
        mock_youtube.liveStreams().list().execute.return_value = {
            "items": [{
                "id": "s1",
                "snippet": {"title": "Main", "description": ""},
                "cdn": {
                    "resolution": "1080p",
                    "frameRate": "30fps",
                    "ingestionInfo": {
                        "ingestionAddress": "rtmp://x",
                        "streamName": "key",
                    },
                },
                "status": {},
            }],
            "pageInfo": {"totalResults": 1},
        }

        result = stream_service.list()

        assert len(result.items) == 1
        assert result.items[0].resolution == StreamResolution.RES_1080P
        assert result.items[0].rtmp_url == "rtmp://x/key"


class TestStreamServiceCreate:
    def test_create_stream(self, stream_service, mock_youtube):
        mock_youtube.liveStreams().insert().execute.return_value = {
            "id": "new-s",
            "snippet": {"title": "New Stream", "description": ""},
            "cdn": {"resolution": "720p", "frameRate": "60fps", "ingestionInfo": {}},
            "status": {},
        }

        result = stream_service.create(
            title="New Stream",
            resolution=StreamResolution.RES_720P,
            frame_rate=StreamFrameRate.FPS_60,
        )

        assert result.id == "new-s"
        assert result.resolution == StreamResolution.RES_720P


class TestStreamServiceUpdate:
    def test_update_title(self, stream_service, mock_youtube):
        mock_youtube.liveStreams().list().execute.return_value = {
            "items": [{
                "id": "s1",
                "snippet": {"title": "Old"},
                "cdn": {"resolution": "1080p"},
                "status": {},
            }],
        }
        mock_youtube.liveStreams().update().execute.return_value = {
            "id": "s1",
            "snippet": {"title": "Updated", "description": ""},
            "cdn": {"resolution": "1080p"},
            "status": {},
        }

        result = stream_service.update("s1", "Updated")

        assert result.title == "Updated"

    def test_update_not_found(self, stream_service, mock_youtube):
        mock_youtube.liveStreams().list().execute.return_value = {"items": []}

        with pytest.raises(NotFoundError):
            stream_service.update("nope", "X")


class TestStreamServiceDelete:
    def test_delete_success(self, stream_service, mock_youtube):
        mock_youtube.liveStreams().delete().execute.return_value = None
        stream_service.delete("s1")


# ─── Chat Service ─────────────────────────────────────────────────────────────


class TestChatServiceListMessages:
    def test_list_messages(self, chat_service, mock_youtube):
        mock_youtube.liveChatMessages().list().execute.return_value = {
            "items": [{
                "id": "m1",
                "snippet": {
                    "type": "textMessageEvent",
                    "publishedAt": "2026-01-24T10:00:00Z",
                    "textMessageDetails": {"messageText": "Hi there"},
                },
                "authorDetails": {
                    "channelId": "UC1",
                    "displayName": "User1",
                },
            }],
            "pageInfo": {"totalResults": 1},
        }

        result = chat_service.list_messages("chat-id")

        assert len(result.items) == 1
        assert result.items[0].message_text == "Hi there"


class TestChatServiceSendMessage:
    def test_send_message(self, chat_service, mock_youtube):
        mock_youtube.liveChatMessages().insert().execute.return_value = {
            "id": "m-new",
            "snippet": {
                "type": "textMessageEvent",
                "publishedAt": "2026-01-24T10:05:00Z",
                "textMessageDetails": {"messageText": "Hello!"},
                "liveChatId": "chat-id",
            },
            "authorDetails": {
                "channelId": "UC-me",
                "displayName": "Me",
            },
        }

        result = chat_service.send_message("chat-id", "Hello!")

        assert result.message_text == "Hello!"


class TestChatServiceDeleteMessage:
    def test_delete_message(self, chat_service, mock_youtube):
        mock_youtube.liveChatMessages().delete().execute.return_value = None
        chat_service.delete_message("m1")
