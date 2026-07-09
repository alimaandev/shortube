from __future__ import annotations

import logging
import sys
from typing import Literal

_LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_LOGGERS: dict[str, logging.Logger] = {}


def setup_logging(
    name: str = "shortube",
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    format_string: str | None = None,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(_LOG_LEVELS.get(level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = format_string or (
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

    _LOGGERS[name] = logger
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
