"""
file_manager.py
================
Small, dependency-free filesystem helpers used across the backend.

Kept intentionally minimal in Phase 1 (directory creation + CSV writing).
Phase 2 modules that manage raw/processed/final datasets, logs, and power
traces will extend this module rather than duplicating path logic.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Sequence

from utils.logger import get_logger

logger = get_logger(__name__)


class FileManager:
    """Static helper namespace for common file/directory operations."""

    @staticmethod
    def ensure_dir(path: Path) -> Path:
        """Create `path` (and parents) if it does not already exist."""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def write_csv(
        path: Path,
        fieldnames: Sequence[str],
        rows: Iterable[dict[str, Any]],
    ) -> None:
        """
        Write `rows` to `path` as a CSV file with a header row.

        Overwrites any existing file at `path`. Parent directories are
        created automatically. Rows are written using `csv.DictWriter`, so
        every dict in `rows` must only contain keys present in `fieldnames`.

        Args:
            path: Destination CSV file path.
            fieldnames: Ordered column headers.
            rows: Iterable of row dictionaries.
        """
        FileManager.ensure_dir(path.parent)
        row_count = 0
        with path.open(mode="w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(fieldnames))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
                row_count += 1
        logger.info("Wrote %d rows to %s", row_count, path)

    @staticmethod
    def path_exists(path: Path) -> bool:
        """Return True if `path` exists on disk (file or directory)."""
        return path.exists()
