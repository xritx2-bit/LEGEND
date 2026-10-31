"""Tests for standardized embed builders."""

import discord
from src.ui.embeds import (
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    create_error_embed,
    create_info_embed,
    create_success_embed,
    create_warning_embed,
)


def test_create_info_embed() -> None:
    """Test info embed structure, color, and footer."""
    embed = create_info_embed("Info Title", "Info Description", footer="Custom Footer")
    assert embed.title == "Info Title"
    assert embed.description == "Info Description"
    assert embed.color == COLOR_PRIMARY
    assert embed.footer.text == "Custom Footer"
    assert embed.timestamp is not None


def test_create_success_embed() -> None:
    """Test success embed structure and color."""
    embed = create_success_embed("Operation Complete", "Successfully updated settings.")
    assert "Operation Complete" in (embed.title or "")
    assert embed.color == COLOR_SUCCESS


def test_create_warning_embed() -> None:
    """Test warning embed structure and color."""
    embed = create_warning_embed("Attention", "Action requires confirmation.")
    assert "Attention" in (embed.title or "")
    assert embed.color == COLOR_WARNING


def test_create_error_embed() -> None:
    """Test error embed structure and color."""
    embed = create_error_embed("Failed", "Invalid input received.")
    assert "Failed" in (embed.title or "")
    assert embed.color == COLOR_ERROR
