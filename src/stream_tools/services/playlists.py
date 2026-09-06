"""Playlist service for YouTube Data API playlist operations."""

from __future__ import annotations

from dataclasses import dataclass

from googleapiclient.errors import HttpError

from stream_tools.models.common import PageResult
from stream_tools.services.base import BaseService


@dataclass
class Playlist:
    """Represents a YouTube playlist.

    Attributes:
        id: The playlist's unique YouTube ID.
        title: Display title of the playlist.
        description: Playlist description text.
        item_count: Number of videos currently in the playlist.
        privacy_status: "private", "public", or "unlisted".
    """

    id: str
    title: str
    description: str
    item_count: int
    privacy_status: str

    @classmethod
    def from_api_response(cls, data: dict) -> Playlist:
        """Parse a Playlist from a YouTube API response dict.

        Args:
            data: A single item from the `playlists.list` API response.
        """
        snippet = data.get("snippet", {})
        status = data.get("status", {})
        content_details = data.get("contentDetails", {})
        return cls(
            id=data["id"],
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            item_count=content_details.get("itemCount", 0),
            privacy_status=status.get("privacyStatus", "private"),
        )


class PlaylistService(BaseService):
    """Service for listing playlists and moving videos in and out of them."""

    def list(
        self,
        max_results: int = 25,
        page_token: str | None = None,
    ) -> PageResult[Playlist]:
        """List playlists owned by the authenticated channel.

        Args:
            max_results: Max items per page (1-50).
            page_token: Token for pagination.

        Returns:
            PageResult containing Playlist items and pagination tokens.
        """
        try:
            kwargs: dict = {
                "part": "snippet,status,contentDetails",
                "mine": True,
                "maxResults": max_results,
            }
            if page_token:
                kwargs["pageToken"] = page_token

            response = self.youtube.playlists().list(**kwargs).execute()

            return PageResult(
                items=[Playlist.from_api_response(i) for i in response.get("items", [])],
                next_page_token=response.get("nextPageToken"),
                prev_page_token=response.get("prevPageToken"),
                total_results=response.get("pageInfo", {}).get("totalResults", 0),
            )
        except HttpError as e:
            self._handle_api_error(e, "Playlist")

    def add_video(self, playlist_id: str, video_id: str, position: int | None = None) -> str:
        """Add a video to a playlist.

        Args:
            playlist_id: The playlist to add to.
            video_id: The video to add.
            position: Zero-based insert position. Appends when omitted.

        Returns:
            The ID of the created playlist item.
        """
        snippet: dict = {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
        if position is not None:
            snippet["position"] = position

        try:
            response = (
                self.youtube.playlistItems()
                .insert(part="snippet", body={"snippet": snippet})
                .execute()
            )
            return response["id"]
        except HttpError as e:
            self._handle_api_error(e, "PlaylistItem")

    def find_item(self, playlist_id: str, video_id: str) -> str | None:
        """Find the playlist-item ID for a video within a playlist.

        Args:
            playlist_id: The playlist to search.
            video_id: The video to look for.

        Returns:
            The playlist item ID, or None if the video is not in the playlist.
        """
        page_token: str | None = None
        try:
            while True:
                kwargs: dict = {
                    "part": "snippet",
                    "playlistId": playlist_id,
                    "maxResults": 50,
                }
                if page_token:
                    kwargs["pageToken"] = page_token

                response = self.youtube.playlistItems().list(**kwargs).execute()
                for item in response.get("items", []):
                    resource = item.get("snippet", {}).get("resourceId", {})
                    if resource.get("videoId") == video_id:
                        return item["id"]

                page_token = response.get("nextPageToken")
                if not page_token:
                    return None
        except HttpError as e:
            self._handle_api_error(e, "PlaylistItem")

    def remove_video(self, playlist_item_id: str) -> None:
        """Remove a playlist item by its ID.

        Args:
            playlist_item_id: The playlist item to delete. This is NOT a video ID
                — the same video can appear in several playlists.
        """
        try:
            self.youtube.playlistItems().delete(id=playlist_item_id).execute()
        except HttpError as e:
            self._handle_api_error(e, "PlaylistItem")

    def remove_video_by_video_id(self, playlist_id: str, video_id: str) -> bool:
        """Remove a video from a playlist, looking the item up first.

        Args:
            playlist_id: The playlist to remove from.
            video_id: The video to remove.

        Returns:
            True if an item was found and deleted, False if the video was not
            in the playlist.
        """
        item_id = self.find_item(playlist_id, video_id)
        if item_id is None:
            return False
        self.remove_video(item_id)
        return True
