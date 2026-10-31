"""Tests for input and template validators."""

import pytest
from src.utils.validators import (
    render_template,
    validate_hex_color,
    validate_template_placeholders,
    validate_url,
)


def test_validate_hex_color() -> None:
    """Test valid and invalid hex color codes."""
    # Valid
    valid, val = validate_hex_color("#5865F2")
    assert valid and val == 0x5865F2

    valid, val = validate_hex_color("FF0000")
    assert valid and val == 0xFF0000

    # Invalid
    valid, val = validate_hex_color("invalid")
    assert not valid and val is None

    valid, val = validate_hex_color("#12345")  # 5 digits
    assert not valid and val is None

    valid, val = validate_hex_color("")
    assert not valid and val is None


def test_validate_url() -> None:
    """Test URL structure validation."""
    assert validate_url("https://youtube.com/channel/example")
    assert validate_url("https://i.imgur.com/sample.png")

    # Requires HTTPS by default
    assert not validate_url("http://insecure.com")
    assert validate_url("http://insecure.com", require_https=False)

    # Invalid
    assert not validate_url("not_a_url")
    assert not validate_url("")
    assert not validate_url("ftp://example.com")


def test_validate_template_placeholders() -> None:
    """Test template token validation against allowed set."""
    allowed = {"user", "username", "server", "count"}

    # All valid
    is_valid, invalid = validate_template_placeholders(
        "Welcome to {server}, {user}! You are member #{count}.",
        allowed,
    )
    assert is_valid
    assert invalid == []

    # Contains unknown tokens
    is_valid, invalid = validate_template_placeholders(
        "Hello {user}, your rank is {rank} and role is {role}!",
        allowed,
    )
    assert not is_valid
    assert set(invalid) == {"rank", "role"}


def test_render_template() -> None:
    """Test placeholder substitution in templates."""
    template = "Hey {user}! Welcome to {server}. Member #{count} (status: {unknown})."
    context = {
        "user": "@GamerOne",
        "server": "Legends Guild",
        "count": 42,
    }

    rendered = render_template(template, context)
    assert "@GamerOne" in rendered
    assert "Legends Guild" in rendered
    assert "Member #42" in rendered
    # Unmatched tokens remain intact without crashing
    assert "{unknown}" in rendered


@pytest.mark.asyncio
async def test_resolve_image_url_direct_and_conversions() -> None:
    """Test resolution of various image link types."""
    from src.utils.validators import resolve_image_url

    # 1. Direct links
    direct = "https://example.com/art.png"
    assert await resolve_image_url(direct) == direct

    # 2. Imgur page link
    imgur_page = "https://imgur.com/aBcDeFg"
    assert await resolve_image_url(imgur_page) == "https://i.imgur.com/aBcDeFg.png"

    # 3. Google Drive view link
    gdrive = "https://drive.google.com/file/d/1a2b3c4d5e/view?usp=sharing"
    assert await resolve_image_url(gdrive) == "https://drive.google.com/uc?export=view&id=1a2b3c4d5e"

    # 4. Pinterest direct CDN link
    pinimg = "https://i.pinimg.com/originals/ab/cd/ef/abcdef.jpg"
    assert await resolve_image_url(pinimg) == pinimg

    # 5. Wrapped in angle brackets
    wrapped = "<https://i.pinimg.com/736x/12/34/56/123456.png>"
    assert await resolve_image_url(wrapped) == "https://i.pinimg.com/736x/12/34/56/123456.png"

