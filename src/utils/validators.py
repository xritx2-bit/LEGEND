"""Validation utilities for user input, templates, colors, and URLs."""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
import aiohttp

HEX_COLOR_REGEX = re.compile(r"^#?([A-Fa-f0-9]{6})$")
TEMPLATE_TOKEN_REGEX = re.compile(r"\{([a-zA-Z0-9_]+)\}")

PINTEREST_IMG_REGEX = re.compile(
    r"https://i\.pinimg\.com/(?:originals|736x|564x|474x|236x)/[a-zA-Z0-9_\/]+\.(?:jpg|png|jpeg|webp|gif)",
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
    # If user provided a domain/path without scheme (e.g. pin.it/... or pinterest.com/...)
    if cleaned and "://" not in cleaned:
        if "." in cleaned and "/" in cleaned:
            cleaned = "https://" + cleaned

    return cleaned


async def resolve_image_url(url: str, session: Optional[aiohttp.ClientSession] = None) -> str:
    """Resolve image links from Pinterest, Imgur, Google Drive, or direct links into Discord-compatible direct image URLs."""
    url = clean_url(url)
    if not url:
        return ""

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

    # Already a direct image or direct Pinterest CDN image (i.pinimg.com)
    if "i.pinimg.com" in url or any(url.lower().split("?")[0].endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
        return url

    # Pinterest pin or shortened link (pin.it or pinterest.com/pin/...)
    if "pinterest.com" in url or "pin.it" in url:
        close_session = False
        if session is None:
            session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }
            )
            close_session = True

        try:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    matches = PINTEREST_IMG_REGEX.findall(html)
                    if matches:
                        # Prefer 'originals'
                        for m in matches:
                            if "originals" in m:
                                return m
                        # Try converting 736x to originals
                        for m in matches:
                            if "736x" in m:
                                return m.replace("/736x/", "/originals/")
                        return matches[0]
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

