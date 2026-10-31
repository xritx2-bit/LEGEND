"""Tests for security hardening, secret redaction, and reliability controls."""

import logging
import discord
from src.utils.logger import SecretRedactingFilter
from src.utils.permissions import get_safe_allowed_mentions


def test_secret_redacting_filter() -> None:
    """Verify that sensitive credentials are automatically redacted from log records."""
    redactor = SecretRedactingFilter()
    super_secret_token = "MTA1OTI4MzYxNzk5MzE1MDQ5NA.Gh6-8K.example_real_token_123456"
    redactor.register_secret(super_secret_token)

    # Simulate log record containing the secret
    record = logging.LogRecord(
        name="TestLogger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg=f"Connecting with token: {super_secret_token} now.",
        args=(),
        exc_info=None,
    )

    redactor.filter(record)
    assert super_secret_token not in record.msg
    assert "3456" in record.msg  # Last 4 visible
    assert "****************" in record.msg


def test_allowed_mentions_hardened_defaults() -> None:
    """Verify default mention settings strictly forbid accidental mass mentions."""
    mentions = get_safe_allowed_mentions(allow_everyone=False, allowed_role_id=None)
    assert mentions.everyone is False
    assert mentions.roles == []
    assert mentions.users is True


def test_allowed_mentions_strictly_bounds_role() -> None:
    """Verify role mention is confined only to the target role."""
    target_role = 55443322
    mentions = get_safe_allowed_mentions(allow_everyone=False, allowed_role_id=target_role)
    assert mentions.everyone is False
    assert len(mentions.roles) == 1
    assert mentions.roles[0].id == target_role
