"""Validation utilities for user input, templates, colors, and URLs."""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
import aiohttp

HEX_COLOR_REGEX = re.compile(r"^#?([A-Fa-f0-9]{6})$")
TEMPLATE_TOKEN_REGEX = re.compile(r"\{([a-zA-Z0-9_]+)\}")

ALLOWED_WELCOME_PLACEHOLDERS: Set[str] = {
    "user",
    "username",
    "server",
    "count",
    "user_avatar",
    "avatar",
    "server_icon",
    "icon",
    "server_banner",
    "banner",
    "user_banner",
}

PINTEREST_IMG_REGEX = re.compile(
    r"https://i\.pinimg\.com/(?:originals|[0-9]+x)/[a-zA-Z0-9_\/.-]+",
    re.IGNORECASE,
)
OG_IMAGE_REGEX = re.compile(
    r'<meta\s+[^>]*property=["\']og:image(?::secure_url)?["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_ALT_REGEX = re.compile(
    r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image(?::secure_url)?["\']',
    re.IGNORECASE,
)
TWITTER_IMAGE_REGEX = re.compile(
    r'<meta\s+[^>]*name=["\']twitter:image(?::src)?["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
GDRIVE_FILE_REGEX = re.compile(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)", re.IGNORECASE)
IMGUR_PAGE_REGEX = re.compile(r"https?://(?:www\.)?imgur\.com/([a-zA-Z0-9]+)(?:\.[a-zA-Z0-9]+)?$", re.IGNORECASE)


def clean_url(url: str) -> str:
    """Clean user-provided URL removing surrounding text/brackets and prepending https if missing."""
    if not url or not isinstance(url, str):
        return ""

    raw = url.strip()

    # Extract embedded http/https URL if user pasted mobile share text
    embedded_match = re.search(r"https?://[^\s<>\"']+", raw)
    if embedded_match:
        return embedded_match.group(0).rstrip(".,;)")

    # Clean surrounding brackets or quotes
    cleaned = raw.strip("<>\"' \t\r\n").rstrip(".,;)")
    if not cleaned:
        return ""

    # If user provided a domain/path without scheme (e.g. pin.it/... or pinterest.com/...)
    if "://" not in cleaned:
        if "." in cleaned and "/" in cleaned:
            cleaned = "https://" + cleaned

    return cleaned


def _upgrade_pinterest_cdn_url(cdn_url: str) -> str:
    """Convert resized Pinterest image URLs (736x, 564x, etc.) to full-res originals."""
    if not cdn_url or "i.pinimg.com" not in cdn_url:
        return cdn_url
    return re.sub(r"/i\.pinimg\.com/(?:[0-9]+x)/", "/i.pinimg.com/originals/", cdn_url)


async def resolve_image_url(url: str, session: Optional[aiohttp.ClientSession] = None) -> str:
    """Resolve image links from Pinterest, Imgur, Google Drive, Tenor, or direct links into Discord-compatible direct image URLs."""
    url = clean_url(url)
    if not url:
        return ""

    # Auto-upgrade insecure http image links to https for Discord embed compatibility
    if url.startswith("http://"):
        url = "https://" + url[7:]

    # Google Drive share link -> direct view endpoint
    gdrive_match = GDRIVE_FILE_REGEX.search(url)
    if gdrive_match:
        file_id = gdrive_match.group(1)
        return f"https://drive.google.com/uc?export=view&id={file_id}"

    # Imgur page link -> direct i.imgur.com link
    imgur_match = IMGUR_PAGE_REGEX.match(url)
    if imgur_match and not url.startswith("https://i.imgur.com/"):
        image_id = imgur_match.group(1)
        return f"https://i.imgur.com/{image_id}.png"

    # Already a direct image or direct CDN link
    lower_path = url.lower().split("?")[0]
    is_direct_image = any(lower_path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"])
    if "i.pinimg.com" in url:
        return _upgrade_pinterest_cdn_url(url)
    if is_direct_image:
        return url
    if "cdn.discordapp.com/attachments/" in url or "media.discordapp.net/attachments/" in url:
        return url

    # Pinterest pin or shortened link (pin.it or pinterest.com/pin/...)
    if "pinterest.com" in url or "pin.it" in url:
        close_session = False
        if session is None:
            # Use Discordbot user agent so Pinterest serves open-graph meta tags
            session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }
            )
            close_session = True

        try:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    html = await resp.text()

                    # 1. Try Open Graph meta tag
                    og_match = OG_IMAGE_REGEX.search(html) or OG_IMAGE_ALT_REGEX.search(html)
                    if og_match:
                        og_img = og_match.group(1)
                        if "i.pinimg.com" in og_img or any(og_img.lower().split("?")[0].endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
                            return _upgrade_pinterest_cdn_url(og_img)

                    # 2. Try Twitter image meta tag
                    tw_match = TWITTER_IMAGE_REGEX.search(html)
                    if tw_match:
                        tw_img = tw_match.group(1)
                        if "i.pinimg.com" in tw_img:
                            return _upgrade_pinterest_cdn_url(tw_img)

                    # 3. Direct i.pinimg.com regex in the page
                    matches = PINTEREST_IMG_REGEX.findall(html)
                    if matches:
                        for m in matches:
                            if "originals" in m:
                                return m
                        return _upgrade_pinterest_cdn_url(matches[0])
        except Exception:
            pass
        finally:
            if close_session and session:
                await session.close()

        # If scraping failed to find a direct image on Pinterest, return empty so caller knows
        return ""

    # Tenor page link -> scrape og:image
    if "tenor.com/view/" in url:
        close_session = False
        if session is None:
            session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)"}
            )
            close_session = True
        try:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    og_match = OG_IMAGE_REGEX.search(html) or OG_IMAGE_ALT_REGEX.search(html)
                    if og_match:
                        return og_match.group(1)
        except Exception:
            pass
        finally:
            if close_session and session:
                await session.close()

    return url


def validate_hex_color(hex_str: str) -> Tuple[bool, Optional[int]]:
    """Validate a hex color string and return its integer representation if valid.

    Examples: '#5865F2', '5865F2', '#FF0000'
    """
    if not hex_str:
        return False, None

    cleaned = hex_str.strip().lstrip("#")
    match = HEX_COLOR_REGEX.match(cleaned)
    if not match:
        return False, None

    try:
        color_int = int(match.group(1), 16)
        return True, color_int
    except ValueError:
        return False, None


def validate_url(url: str, require_https: bool = True) -> bool:
    """Validate whether a string is a well-formed HTTP/HTTPS URL."""
    cleaned = clean_url(url)
    if not cleaned:
        return False

    try:
        parsed = urlparse(cleaned)
        allowed_schemes = ("https",) if require_https else ("http", "https")
        return bool(parsed.scheme in allowed_schemes and parsed.netloc)
    except Exception:
        return False


def validate_template_placeholders(
    template: str,
    allowed_placeholders: Set[str],
) -> Tuple[bool, List[str]]:
    """Verify that all curly-brace placeholders in template exist in allowed set.

    Returns:
        (is_valid, list_of_invalid_tokens)
    """
    if not template:
        return True, []

    found_tokens = TEMPLATE_TOKEN_REGEX.findall(template)
    invalid_tokens = [tok for tok in found_tokens if tok not in allowed_placeholders]

    return len(invalid_tokens) == 0, invalid_tokens


def render_template(template: str, context: Dict[str, Any]) -> str:
    """Safely render a template string substituting known context keys."""
    if not template:
        return ""

    def replace_token(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return str(context[key])
        return match.group(0)  # Keep unrecognized token as-is

    return TEMPLATE_TOKEN_REGEX.sub(replace_token, template)

