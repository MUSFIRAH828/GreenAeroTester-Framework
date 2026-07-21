"""
run_manager.py
===============
Run identity management and result recording for Phase 2.

Two responsibilities live here, deliberately kept together because they
share the same lifecycle (one run ID is minted, one result eventually
fills it in):

1. `RunIdGenerator` -- mints unique, zero-padded run IDs (`R000001`, ...)
   using the exact prefix/digit rules already defined in
   `config/constants.py` (unchanged from Phase 1).
2. `RunManager` -- collects `ExecutionRecord` results as they complete and
   writes them to `execution_plan.csv` once the run is finished.

Phase 3 (validators, aggregation) will read `execution_plan.csv` produced
here as one of its inputs, alongside the raw/energy files a later
execution phase will add.

--- Resume / checkpoint patch -------------------------------------------
`RunManager.read_execution_plan()` lets the Phase 2 orchestrator
(`experiment_runner.py`) load whatever `execution_plan.csv` rows already
exist on disk from a previous, interrupted run, so completed runs can be
skipped instead of re-executed. No existing schema or method signature
was changed -- this is purely an additive read path.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from config.constants import RUN_ID_DIGITS, RUN_ID_PREFIX
from models.enums import RunResult
from utils.file_manager import FileManager
from utils.logger import get_logger

logger = get_logger(__name__)


class RunManagerError(Exception):
    """Raised when run recording or persistence cannot complete safely."""


@dataclass(frozen=True)
class ExecutionRecord:
    """
    One completed (or attempted) execution, ready to be written as a row
    of `execution_plan.csv`.
    """

    run_id: str
    scenario_id: str
    test_id: str
    round_number: int
    status: RunResult
    timestamp: str
    runtime_sec: float

    def to_row(self) -> dict[str, object]:
        """Flatten to the `execution_plan.csv` row schema."""
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "test_id": self.test_id,
            "round_number": self.round_number,
            "execution_status": self.status.value,
            "timestamp": self.timestamp,
            "runtime_sec": round(self.runtime_sec, 3),
        }


class RunIdGenerator:
    """
    Mints unique, sequential, zero-padded run IDs.

    Uses the exact `RUN_ID_PREFIX` / `RUN_ID_DIGITS` constants defined in
    Phase 1's `config/constants.py`, so run IDs generated here
    (`R000001`, `R000002`, ...) are formatted identically to every other
    ID family in the project (`S0001`, `T0001`, ...).
    """

    def __init__(self, start_at: int = 1) -> None:
        """
        Args:
            start_at: The first sequence number to mint (defaults to 1,
                producing R000001 first). Raised sequence numbers support
                a "resume after interruption" mode without colliding with
                already-issued run IDs.
        """
        if start_at < 1:
            raise RunManagerError(f"start_at must be >= 1, got {start_at}")
        self._next_sequence_number = start_at

    def next_id(self) -> str:
        """Return the next unique run ID and advance the internal counter."""
        run_id = f"{RUN_ID_PREFIX}{self._next_sequence_number:0{RUN_ID_DIGITS}d}"
        self._next_sequence_number += 1
        return run_id

    @staticmethod
    def next_start_at(existing_run_ids: list[str]) -> int:
        """
        Compute the correct `start_at` to resume minting run IDs after a
        set of already-issued run IDs (e.g. loaded from a checkpointed
        `execution_plan.csv`), so resumed runs never reuse or collide with
        a previously written run ID.

        Args:
            existing_run_ids: Run IDs already present on disk.

        Returns:
            1 if there are no existing run IDs, otherwise
            `max(existing sequence numbers) + 1`.
        """
        max_sequence = 0
        for run_id in existing_run_ids:
            suffix = run_id[len(RUN_ID_PREFIX):]
            try:
                max_sequence = max(max_sequence, int(suffix))
            except ValueError:
                continue
        return max_sequence + 1


@dataclass
class RunManager:
    """
    Accumulates `ExecutionRecord` results in memory during a run and
    persists them to `execution_plan.csv` when the batch completes.
    """

    records: list[ExecutionRecord] = field(default_factory=list)

    def record(self, execution_record: ExecutionRecord) -> None:
        """Append one completed execution's result to the in-memory log."""
        self.records.append(execution_record)

    def write_execution_plan(self, path: Path) -> None:
        """
        Persist all recorded executions to `path` as `execution_plan.csv`.

        Args:
            path: Destination CSV file path.

        Raises:
            RunManagerError: if no records have been collected yet.
        """
        if not self.records:
            raise RunManagerError("No execution records to write -- run the schedule first")

        FileManager.write_csv(
            path=path,
            fieldnames=list(self.records[0].to_row().keys()),
            rows=(record.to_row() for record in self.records),
        )
        logger.info("Execution plan written: %s (%d rows)", path, len(self.records))

    def summary(self) -> dict[str, int]:
        """
        Compute a simple pass/fail/other breakdown plus the total count.

        Returns:
            A dict such as {"total": 1000, "pass": 1000, "fail": 0, ...}
            covering every `RunResult` value observed, always including
            "total".
        """
        counts: dict[str, int] = {"total": len(self.records)}
        for record in self.records:
            counts[record.status.value] = counts.get(record.status.value, 0) + 1
        return counts

    @staticmethod
    def utc_timestamp() -> str:
        """Return the current UTC time as an ISO-8601 string for record-keeping."""
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    # ------------------------------------------------------------------
    # Resume / checkpoint support (patch)
    # ------------------------------------------------------------------
    @staticmethod
    def read_execution_plan(path: Path) -> list[ExecutionRecord]:
        """
        Read a previously written `execution_plan.csv` back into
        `ExecutionRecord` objects.

        Used by `experiment_runner.py` on startup to discover which runs
        already completed in a prior (possibly interrupted) invocation,
        so they can be skipped instead of re-executed.

        Args:
            path: Path to an existing `execution_plan.csv`.

        Returns:
            The rows of `path`, parsed back into `ExecutionRecord`
            instances, in file order. Returns an empty list if the file
            has a header but no data rows.

        Raises:
            RunManagerError: if the file cannot be read or a row is
                malformed (missing/invalid field).
        """
        records: list[ExecutionRecord] = []
        try:
            with path.open(mode="r", newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    records.append(
                        ExecutionRecord(
                            run_id=row["run_id"],
                            scenario_id=row["scenario_id"],
                            test_id=row["test_id"],
                            round_number=int(row["round_number"]),
                            status=RunResult(row["execution_status"]),
                            timestamp=row["timestamp"],
                            runtime_sec=float(row["runtime_sec"]),
                        )
                    )
        except (OSError, csv.Error, KeyError, ValueError) as exc:
            raise RunManagerError(
                f"Failed to read existing execution plan at {path}: {exc}"
            ) from exc

        logger.info("Loaded %d existing execution records from %s", len(records), path)
        return records