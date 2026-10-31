"""Tests for YouTube Data API v3 service client and metadata parser."""

from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
import pytest

from src.services.youtube_service import (
    BroadcastMetadata,
    YouTubeAPIError,
    YouTubeChannelNotFoundError,
    YouTubeInvalidKeyError,
    YouTubeQuotaExceededError,
    YouTubeService,
)


def test_mock_broadcast_generation() -> None:
    """Verify mock broadcast generator produces valid stream metadata."""
    service = YouTubeService(api_key="dummy_key", default_channel_id="UC_TEST_CHANNEL")
    broadcast = service.generate_mock_broadcast(
        channel_title="Apex Champion",
        title="Climbing to Predator Rank!",
        game_name="Apex Legends",
    )

    assert isinstance(broadcast, BroadcastMetadata)
    assert broadcast.channel_id == "UC_TEST_CHANNEL"
    assert broadcast.channel_title == "Apex Champion"
    assert broadcast.title == "Climbing to Predator Rank!"
    assert broadcast.url.startswith("https://www.youtube.com/watch?v=")
    assert broadcast.thumbnail_url.startswith("https://")
    assert broadcast.status == "test"
    assert broadcast.game_name == "Apex Legends"

    # Verify to_dict format
    b_dict = broadcast.to_dict()
    assert b_dict["game_name"] == "Apex Legends"
    assert b_dict["channel_id"] == "UC_TEST_CHANNEL"


def test_parse_broadcast_snippet_thumbnail_hierarchy() -> None:
    """Verify that highest resolution thumbnail is selected from YouTube snippet."""
    service = YouTubeService(api_key="dummy_key")

    snippet = {
        "channelId": "UC_123",
        "channelTitle": "Streamer Name",
        "title": "My Epic Stream",
        "publishedAt": "2026-10-31T12:00:00Z",
        "thumbnails": {
            "default": {"url": "https://img.youtube.com/vi/abc/default.jpg"},
            "high": {"url": "https://img.youtube.com/vi/abc/hqdefault.jpg"},
            "maxres": {"url": "https://img.youtube.com/vi/abc/maxresdefault.jpg"},
        },
    }

    parsed = service._parse_broadcast_snippet("abc", snippet)
    assert parsed.thumbnail_url == "https://img.youtube.com/vi/abc/maxresdefault.jpg"
    assert parsed.broadcast_id == "abc"
    assert parsed.channel_title == "Streamer Name"


def test_parse_broadcast_snippet_fallback_thumbnail() -> None:
    """Verify fallback thumbnail URL is constructed when thumbnails dict is empty."""
    service = YouTubeService(api_key="dummy_key")
    snippet = {
        "channelId": "UC_123",
        "channelTitle": "Streamer Name",
        "title": "Stream Without Thumbnails",
        "thumbnails": {},
    }

    parsed = service._parse_broadcast_snippet("video_xyz", snippet)
    assert parsed.thumbnail_url == "https://i.ytimg.com/vi/video_xyz/hqdefault.jpg"


@pytest.mark.asyncio
async def test_fetch_active_livestream_none_found() -> None:
    """Verify fetch_active_livestream returns None when search returns empty items."""
    service = YouTubeService(api_key="dummy_key", default_channel_id="UC_NO_STREAM")
    try:
        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"items": []}
            result = await service.fetch_active_livestream()
            assert result is None
            mock_request.assert_called_once()
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_fetch_active_livestream_found() -> None:
    """Verify fetch_active_livestream properly constructs BroadcastMetadata when live video exists."""
    service = YouTubeService(api_key="dummy_key", default_channel_id="UC_IS_STREAMING")
    try:
        sample_api_response = {
            "items": [
                {
                    "id": {"videoId": "live_video_777"},
                    "snippet": {
                        "channelId": "UC_IS_STREAMING",
                        "channelTitle": "Pro Gamer",
                        "title": "🔴 Sub Games & Tournaments",
                        "publishedAt": "2026-10-31T10:00:00Z",
                        "thumbnails": {
                            "high": {"url": "https://img.youtube.com/vi/live_video_777/hqdefault.jpg"}
                        },
                    },
                }
            ]
        }

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_api_response
            result = await service.fetch_active_livestream()

            assert result is not None
            assert result.broadcast_id == "live_video_777"
            assert result.title == "🔴 Sub Games & Tournaments"
            assert result.channel_title == "Pro Gamer"
            assert result.url == "https://www.youtube.com/watch?v=live_video_777"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_quota_exceeded_error() -> None:
    """Verify that HTTP 403 with quotaExceeded reason raises YouTubeQuotaExceededError."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.closed = False

    # Mock response object
    mock_response = AsyncMock()
    mock_response.status = 403
    mock_response.json.return_value = {
        "error": {
            "message": "The request cannot be completed because you have exceeded your quota.",
            "errors": [{"reason": "quotaExceeded"}],
        }
    }

    # Context manager setup for session.get
    mock_session.get.return_value.__aenter__.return_value = mock_response

    service = YouTubeService(api_key="test_key", session=mock_session)

    with pytest.raises(YouTubeQuotaExceededError, match="daily quota exceeded"):
        await service._request("search", {"part": "snippet"})


@pytest.mark.asyncio
async def test_invalid_api_key_error() -> None:
    """Verify that HTTP 403 or 400 with keyInvalid reason raises YouTubeInvalidKeyError."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.closed = False

    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.json.return_value = {
        "error": {
            "message": "API key not valid. Please pass a valid API key.",
            "errors": [{"reason": "keyInvalid"}],
        }
    }
    mock_session.get.return_value.__aenter__.return_value = mock_response

    service = YouTubeService(api_key="bad_key", session=mock_session)

    with pytest.raises(YouTubeInvalidKeyError, match="API key is invalid"):
        await service._request("search", {"part": "snippet"})


@pytest.mark.asyncio
async def test_channel_details_parsing() -> None:
    """Verify channel details extraction."""
    service = YouTubeService(api_key="dummy_key")
    try:
        mock_channel_response = {
            "items": [
                {
                    "snippet": {
                        "title": "Legendary Gaming",
                        "description": "Welcome to my gaming channel!",
                        "customUrl": "@legendarygaming",
                        "thumbnails": {
                            "high": {"url": "https://yt3.ggpht.com/avatar_high.jpg"}
                        },
                    },
                    "statistics": {
                        "subscriberCount": "150000",
                        "videoCount": "420",
                    },
                }
            ]
        }

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_channel_response
            details = await service.fetch_channel_details("UC_LEGEND")

            assert details["title"] == "Legendary Gaming"
            assert details["subscriber_count"] == "150000"
            assert details["avatar_url"] == "https://yt3.ggpht.com/avatar_high.jpg"
            assert details["custom_url"] == "@legendarygaming"
    finally:
        await service.close()
