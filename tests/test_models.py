"""Tests for model from_api_response parsing."""

from datetime import datetime, timezone

from stream_tools.models.broadcast import Broadcast
from stream_tools.models.chat import ChatBan, ChatMessage, ChatModerator
from stream_tools.models.common import LifeCycleStatus, PrivacyStatus, StreamFrameRate, StreamResolution
from stream_tools.models.stream import LiveStream


class TestBroadcast:
    def test_full_response(self):
        data = {
            "id": "abc123",
            "snippet": {
                "title": "My Stream",
                "description": "Test broadcast",
                "scheduledStartTime": "2026-01-24T10:00:00Z",
                "scheduledEndTime": "2026-01-24T12:00:00Z",
                "actualStartTime": "2026-01-24T10:01:00Z",
                "actualEndTime": None,
                "liveChatId": "chat-xyz",
            },
            "status": {
                "privacyStatus": "unlisted",
                "lifeCycleStatus": "live",
            },
            "contentDetails": {
                "boundStreamId": "stream-456",
            },
        }

        b = Broadcast.from_api_response(data)

        assert b.id == "abc123"
        assert b.title == "My Stream"
        assert b.description == "Test broadcast"
        assert b.scheduled_start == datetime(2026, 1, 24, 10, 0, tzinfo=timezone.utc)
        assert b.scheduled_end == datetime(2026, 1, 24, 12, 0, tzinfo=timezone.utc)
        assert b.actual_start == datetime(2026, 1, 24, 10, 1, tzinfo=timezone.utc)
        assert b.actual_end is None
        assert b.privacy == PrivacyStatus.UNLISTED
        assert b.life_cycle_status == LifeCycleStatus.LIVE
        assert b.live_chat_id == "chat-xyz"
        assert b.bound_stream_id == "stream-456"

    def test_minimal_response(self):
        data = {
            "id": "min-id",
            "snippet": {},
            "status": {},
            "contentDetails": {},
        }

        b = Broadcast.from_api_response(data)

        assert b.id == "min-id"
        assert b.title == ""
        assert b.scheduled_start is None
        assert b.privacy == PrivacyStatus.PRIVATE
        assert b.life_cycle_status == LifeCycleStatus.CREATED
        assert b.live_chat_id is None
        assert b.bound_stream_id is None

    def test_missing_sections(self):
        data = {"id": "bare"}

        b = Broadcast.from_api_response(data)

        assert b.id == "bare"
        assert b.title == ""


class TestLiveStream:
    def test_full_response(self):
        data = {
            "id": "stream-1",
            "snippet": {
                "title": "Main Camera",
                "description": "1080p feed",
            },
            "cdn": {
                "resolution": "1080p",
                "frameRate": "30fps",
                "ingestionType": "rtmp",
                "ingestionInfo": {
                    "ingestionAddress": "rtmp://a.rtmp.youtube.com/live2",
                    "streamName": "xxxx-xxxx-xxxx",
                },
                "isReusable": True,
            },
            "status": {
                "healthStatus": {
                    "status": "good",
                },
            },
        }

        s = LiveStream.from_api_response(data)

        assert s.id == "stream-1"
        assert s.title == "Main Camera"
        assert s.resolution == StreamResolution.RES_1080P
        assert s.frame_rate == StreamFrameRate.FPS_30
        assert s.ingestion_address == "rtmp://a.rtmp.youtube.com/live2"
        assert s.stream_name == "xxxx-xxxx-xxxx"
        assert s.rtmp_url == "rtmp://a.rtmp.youtube.com/live2/xxxx-xxxx-xxxx"
        assert s.is_reusable is True

    def test_rtmp_url_none_when_missing(self):
        data = {
            "id": "stream-2",
            "snippet": {"title": "No CDN"},
            "cdn": {},
            "status": {},
        }

        s = LiveStream.from_api_response(data)

        assert s.rtmp_url is None
        assert s.resolution is None
        assert s.frame_rate is None

    def test_variable_resolution(self):
        data = {
            "id": "stream-3",
            "snippet": {"title": "Variable"},
            "cdn": {"resolution": "variable", "frameRate": "variable"},
            "status": {},
        }

        s = LiveStream.from_api_response(data)

        assert s.resolution == StreamResolution.VARIABLE
        assert s.frame_rate == StreamFrameRate.VARIABLE


class TestChatMessage:
    def test_from_api_response(self):
        data = {
            "id": "msg-1",
            "snippet": {
                "type": "textMessageEvent",
                "publishedAt": "2026-01-24T10:05:30Z",
                "textMessageDetails": {
                    "messageText": "Hello world!",
                },
            },
            "authorDetails": {
                "channelId": "UC123",
                "displayName": "TestUser",
            },
        }

        m = ChatMessage.from_api_response(data)

        assert m.id == "msg-1"
        assert m.author_channel_id == "UC123"
        assert m.author_display_name == "TestUser"
        assert m.message_text == "Hello world!"
        assert m.type == "textMessageEvent"
        assert m.published_at.year == 2026

    def test_missing_text_details(self):
        data = {
            "id": "msg-2",
            "snippet": {"publishedAt": "2026-01-01T00:00:00Z"},
            "authorDetails": {},
        }

        m = ChatMessage.from_api_response(data)

        assert m.message_text == ""
        assert m.author_display_name == ""


class TestChatModerator:
    def test_from_api_response(self):
        data = {
            "id": "mod-1",
            "snippet": {
                "moderatorDetails": {
                    "channelId": "UC-mod",
                    "displayName": "ModUser",
                },
            },
        }

        mod = ChatModerator.from_api_response(data)

        assert mod.id == "mod-1"
        assert mod.channel_id == "UC-mod"
        assert mod.display_name == "ModUser"


class TestChatBan:
    def test_permanent_ban(self):
        data = {
            "id": "ban-1",
            "snippet": {
                "type": "permanent",
                "bannedUserDetails": {
                    "channelId": "UC-banned",
                },
            },
        }

        ban = ChatBan.from_api_response(data)

        assert ban.id == "ban-1"
        assert ban.channel_id == "UC-banned"
        assert ban.ban_type == "permanent"
        assert ban.ban_duration_seconds is None

    def test_temporary_ban(self):
        data = {
            "id": "ban-2",
            "snippet": {
                "type": "temporary",
                "banDurationSeconds": 300,
                "bannedUserDetails": {
                    "channelId": "UC-temp",
                },
            },
        }

        ban = ChatBan.from_api_response(data)

        assert ban.ban_type == "temporary"
        assert ban.ban_duration_seconds == 300
