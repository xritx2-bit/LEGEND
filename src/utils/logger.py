"""Centralized logging configuration."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class SecretRedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive credentials from log output."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets: set[str] = set()

    def register_secret(self, secret: str) -> None:
        """Register a sensitive token or key to be redacted from all future logs."""
        clean = secret.strip()
        if clean and len(clean) > 4:
            self._secrets.add(clean)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for s in self._secrets:
                if s in record.msg:
                    masked = f"{'*' * (len(s) - 4)}{s[-4:]}"
                    record.msg = record.msg.replace(s, masked)
        return True


_global_secret_filter = SecretRedactingFilter()


def register_log_secret(secret: str) -> None:
    """Register a secret with the global logger redactor."""
    _global_secret_filter.register_secret(secret)


def setup_logger(log_level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """Configure structured logging to console and rotating file."""
    logger = logging.getLogger("LegendBot")
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(_global_secret_filter)
    logger.addHandler(console_handler)

    # File Handler (rotating: max 5MB, up to 3 backups)
    try:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=log_path / "bot.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(_global_secret_filter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning("Could not initialize file logging handler: %s", e)

    return logger


