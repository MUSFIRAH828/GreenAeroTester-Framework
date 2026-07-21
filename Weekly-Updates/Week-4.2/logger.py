"""
logger.py
=========
Centralized logging setup.

Every module in the backend should obtain its logger via `get_logger(__name__)`
rather than calling `logging.getLogger` directly, so that formatting, log
level, and file output stay consistent across the whole project.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    logs_dir: Path | None = None,
    log_filename: str = "greenaerotest.log",
) -> None:
    """
    Configure the root logger exactly once for the whole process.

    Safe to call multiple times; subsequent calls are no-ops. This is
    normally invoked once from `main.py` at process startup.

    Args:
        log_level: Standard logging level name, e.g. "INFO", "DEBUG".
        log_to_file: If True, also write logs to `logs_dir/log_filename`.
        logs_dir: Directory to write the log file into (created if missing).
        log_filename: Name of the log file.
    """
    global _configured
    if _configured:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_to_file:
        if logs_dir is None:
            raise ValueError("logs_dir must be provided when log_to_file=True")
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(logs_dir / log_filename, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a module-scoped logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logging.getLogger(name)
