"""Validation utilities for user input, templates, colors, and URLs."""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

HEX_COLOR_REGEX = re.compile(r"^#?([A-Fa-f0-9]{6})$")
TEMPLATE_TOKEN_REGEX = re.compile(r"\{([a-zA-Z0-9_]+)\}")


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
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    try:
        parsed = urlparse(url)
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
