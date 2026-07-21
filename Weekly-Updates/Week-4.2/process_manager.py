"""
process_manager.py
===================
Owns the actual "launch and wait for a process" boundary.

Today this boundary is a **simulation**: FlightGear integration does not
exist yet, so `SimulatedProcessManager` stands in for it by sleeping for a
short, randomized duration and returning a successful result. Every other
Phase 2 module (`executor.py`, `experiment_runner.py`) talks to this class
through the `ProcessManager` interface only -- none of them know or care
whether a real process was launched.

This isolation is deliberate: when real FlightGear/PowerShell launching is
implemented, only this file changes. A future `FlightGearProcessManager`
will implement the same `ProcessManager` interface (subprocess launch,
timeout handling, controlled exit) and can be swapped in without touching
`executor.py`, `scheduler.py`, `run_manager.py`, or `experiment_runner.py`.
"""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from models.enums import RunResult
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProcessOutcome:
    """The result of launching (or simulating) one scenario execution."""

    status: RunResult
    runtime_sec: float
    return_code: int


class ProcessManager(ABC):
    """
    Abstract boundary between the execution engine and "however a scenario
    actually gets run" (simulation today, FlightGear/PowerShell later).
    """

    @abstractmethod
    def run(self, scenario_id: str, run_id: str) -> ProcessOutcome:
        """
        Execute (or simulate) one scenario attempt and return its outcome.

        Args:
            scenario_id: The scenario being executed, e.g. "S0001".
            run_id: The unique run identifier for this attempt, e.g. "R000001".

        Returns:
            A `ProcessOutcome` describing what happened.
        """
        raise NotImplementedError


class SimulatedProcessManager(ProcessManager):
    """
    Simulation-mode process manager.

    Stands in for a real FlightGear + JSBSim launch. Instead of starting a
    simulator process, it:

    1. Waits a randomized 2-3 second interval (representing the run duration).
    2. Always returns `RunResult.PASS` with return code 0.

    This keeps the rest of the execution engine (scheduling, run-ID
    assignment, result recording) fully exercised end-to-end while the
    real simulator integration is still pending.
    """

    def __init__(self, min_duration_sec: float = 2.0, max_duration_sec: float = 3.0) -> None:
        """
        Args:
            min_duration_sec: Lower bound of the simulated run duration.
            max_duration_sec: Upper bound of the simulated run duration.

        Raises:
            ValueError: if the bounds are invalid.
        """
        if min_duration_sec <= 0 or max_duration_sec <= 0:
            raise ValueError("Duration bounds must be positive")
        if min_duration_sec > max_duration_sec:
            raise ValueError("min_duration_sec cannot exceed max_duration_sec")

        self._min_duration_sec = min_duration_sec
        self._max_duration_sec = max_duration_sec

    def run(self, scenario_id: str, run_id: str) -> ProcessOutcome:
        """
        Simulate one scenario execution attempt.

        Args:
            scenario_id: The scenario being "executed".
            run_id: The unique run identifier for this attempt.

        Returns:
            A `ProcessOutcome` with status `RunResult.PASS`, the actual
            simulated wall-clock duration, and return code 0.
        """
        duration = random.uniform(self._min_duration_sec, self._max_duration_sec)
        logger.debug(
            "Simulating execution of %s (run %s) for %.2fs", scenario_id, run_id, duration
        )
        start = time.perf_counter()
        try:
            time.sleep(duration)
        except Exception as exc:  # noqa: BLE001 - simulated I/O boundary
            raise RuntimeError(
                f"Simulated execution of {scenario_id} (run {run_id}) failed"
            ) from exc
        elapsed = time.perf_counter() - start

        return ProcessOutcome(status=RunResult.PASS, runtime_sec=elapsed, return_code=0)
