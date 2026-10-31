"""YouTube Data API v3 service client and metadata parser."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import aiohttp

logger = logging.getLogger("LegendBot.YouTubeService")

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeAPIError(Exception):
    """Base exception for YouTube Data API errors."""
    pass


class YouTubeQuotaExceededError(YouTubeAPIError):
    """Raised when the daily YouTube Data API quota has been exhausted."""
    pass


class YouTubeInvalidKeyError(YouTubeAPIError):
    """Raised when the provided YouTube API key is rejected."""
    pass


class YouTubeChannelNotFoundError(YouTubeAPIError):
    """Raised when the specified YouTube channel cannot be located."""
    pass


@dataclass(frozen=True)
class BroadcastMetadata:
    """Strongly-typed metadata for an active or scheduled YouTube broadcast."""
    broadcast_id: str
    channel_id: str
    channel_title: str
    title: str
    url: str
    thumbnail_url: str
    published_at: str
    status: str  # 'live', 'upcoming', 'test'
    game_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary representation."""
        return {
            "broadcast_id": self.broadcast_id,
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "title": self.title,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "published_at": self.published_at,
            "status": self.status,
            "game_name": self.game_name or "Gaming",
        }


class YouTubeService:
    """Asynchronous client for interacting with the YouTube Data API v3."""

    def __init__(
        self,
        api_key: str,
        default_channel_id: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        timeout_seconds: int = 10,
    ) -> None:
        self.api_key = api_key.strip()
        self.default_channel_id = default_channel_id.strip() if default_channel_id else None
        self._external_session = session is not None
        self._session = session
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or initialize the underlying aiohttp client session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if owned by this service instance."""
        if not self._external_session and self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("YouTubeService HTTP session closed.")

    async def _request(self, endpoint: str, params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """Execute HTTP GET request against YouTube API with exponential backoff on transient errors."""
        session = await self._get_session()
        params = {**params, "key": self.api_key}
        url = f"{YOUTUBE_API_BASE_URL}/{endpoint}"

        backoff = 1.0
        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                async with session.get(url, params=params) as response:
                    status = response.status

                    if status == 200:
                        return await response.json()

                    error_data = {}
                    try:
                        error_data = await response.json()
                    except Exception:
                        pass

                    error_message = (
                        error_data.get("error", {}).get("message")
                        or f"HTTP status {status}"
                    )
                    error_reasons = [
                        err.get("reason")
                        for err in error_data.get("error", {}).get("errors", [])
                        if isinstance(err, dict)
                    ]

                    # Specific error classifications
                    if "quotaExceeded" in error_reasons or "rateLimitExceeded" in error_reasons:
                        logger.error("YouTube API quota exceeded: %s", error_message)
                        raise YouTubeQuotaExceededError("YouTube API daily quota exceeded.")

                    if "keyInvalid" in error_reasons or "API key not valid" in error_message:
                        logger.error("Invalid YouTube API Key: %s", error_message)
                        raise YouTubeInvalidKeyError("Provided YouTube API key is invalid.")

                    if status == 403:
                        raise YouTubeAPIError(f"YouTube 403 Forbidden: {error_message}")

                    if status == 404:
                        raise YouTubeChannelNotFoundError("Target YouTube channel not found.")

                    # Transient server errors (429 Too Many Requests, 500, 503)
                    if status in {429, 500, 502, 503, 504}:
                        logger.warning(
                            "YouTube API transient error HTTP %d (attempt %d/%d): %s",
                            status,
                            attempt,
                            max_retries,
                            error_message,
                        )
                        if attempt < max_retries:
                            await asyncio.sleep(backoff)
                            backoff *= 2.0
                            continue
                        raise YouTubeAPIError(f"YouTube API server error HTTP {status}: {error_message}")

                    raise YouTubeAPIError(f"YouTube API request failed (HTTP {status}): {error_message}")

            except (aiohttp.ClientError, asyncio.TimeoutError) as net_err:
                last_error = net_err
                logger.warning(
                    "Network error during YouTube API call (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    net_err,
                )
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue

        raise YouTubeAPIError(f"YouTube API network failure after {max_retries} attempts: {last_error}")

    async def fetch_channel_details(self, channel_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch public channel metadata (title, customUrl, avatar)."""
        target_id = channel_id or self.default_channel_id
        if not target_id:
            raise ValueError("No channel ID specified.")

        data = await self._request(
            endpoint="channels",
            params={
                "part": "snippet,statistics",
                "id": target_id,
            },
        )

        items = data.get("items", [])
        if not items:
            raise YouTubeChannelNotFoundError(f"No channel found with ID: {target_id}")

        snippet = items[0].get("snippet", {})
        statistics = items[0].get("statistics", {})

        thumbnails = snippet.get("thumbnails", {})
        avatar_url = (
            thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or ""
        )

        return {
            "channel_id": target_id,
            "title": snippet.get("title", "Unknown Channel"),
            "description": snippet.get("description", ""),
            "custom_url": snippet.get("customUrl", ""),
            "avatar_url": avatar_url,
            "subscriber_count": statistics.get("subscriberCount", "Hidden"),
            "video_count": statistics.get("videoCount", "0"),
        }

    async def fetch_active_livestream(
        self,
        channel_id: Optional[str] = None,
    ) -> Optional[BroadcastMetadata]:
        """Query YouTube Data API for currently active live broadcasts on the channel.

        Returns BroadcastMetadata if an active live stream is found, otherwise None.
        """
        target_id = channel_id or self.default_channel_id
        if not target_id:
            raise ValueError("No channel ID provided.")

        # Search for active livestreams on the channel
        search_data = await self._request(
            endpoint="search",
            params={
                "part": "snippet",
                "channelId": target_id,
                "eventType": "live",
                "type": "video",
                "maxResults": 1,
            },
        )

        items = search_data.get("items", [])
        if not items:
            logger.debug("No active livestreams found for channel %s", target_id)
            return None

        item = items[0]
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            return None

        snippet = item.get("snippet", {})
        return self._parse_broadcast_snippet(video_id=video_id, snippet=snippet, status="live")

    def _parse_broadcast_snippet(
        self,
        video_id: str,
        snippet: Dict[str, Any],
        status: str = "live",
    ) -> BroadcastMetadata:
        """Parse YouTube API snippet dictionary into a clean BroadcastMetadata object."""
        thumbnails = snippet.get("thumbnails", {})
        # Pick the highest available resolution thumbnail
        thumb_url = (
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("standard", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        )

        channel_title = snippet.get("channelTitle", "Creator")
        title = snippet.get("title", "Live Broadcast")
        published_at = snippet.get("publishedAt") or datetime.now(timezone.utc).isoformat()

        return BroadcastMetadata(
            broadcast_id=video_id,
            channel_id=snippet.get("channelId", ""),
            channel_title=channel_title,
            title=title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            thumbnail_url=thumb_url,
            published_at=published_at,
            status=status,
            game_name=None,
        )

    def generate_mock_broadcast(
        self,
        channel_id: Optional[str] = None,
        channel_title: Optional[str] = None,
        title: Optional[str] = None,
        game_name: Optional[str] = None,
    ) -> BroadcastMetadata:
        """Generate realistic mock broadcast metadata for testing without going live."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        c_id = channel_id or self.default_channel_id or "UC_MOCK_CHANNEL_123"
        c_title = channel_title or "Legend Gamer"
        stream_title = title or "🔴 [TEST] Weekend Ranked Gaming & Community Custom Matches!"
        game = game_name or "Valorant"

        # Realistic mock broadcast ID
        mock_id = f"test_stream_{int(datetime.now(timezone.utc).timestamp())}"

        # High quality sample gaming thumbnail
        thumbnail = "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1280&q=80"

        return BroadcastMetadata(
            broadcast_id=mock_id,
            channel_id=c_id,
            channel_title=c_title,
            title=stream_title,
            url=f"https://www.youtube.com/watch?v={mock_id}",
            thumbnail_url=thumbnail,
            published_at=now_str,
            status="test",
            game_name=game,
        )
