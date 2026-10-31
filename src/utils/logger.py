"""Centralized logging configuration."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


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
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning("Could not initialize file logging handler: %s", e)

    return logger
