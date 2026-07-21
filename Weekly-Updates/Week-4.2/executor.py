"""
executor.py
===========
Executes exactly one scheduled run.

`ScenarioExecutor` is the glue between a `ScheduledExecution` (what to run
and when, from `scheduler.py`), a `ProcessManager` (how to actually run
it -- simulated today, real FlightGear later, from `process_manager.py`),
and an `ExecutionRecord` (the result, defined in `run_manager.py`).

It owns per-run console reporting (the "Starting Run ... / Scenario ... /
Round ... / PASS" output the spec asks for) and per-run exception
isolation, so that one failed attempt cannot crash the entire 1000-run
batch in `experiment_runner.py`.
"""

from __future__ import annotations

from execution.process_manager import ProcessManager
from execution.run_manager import ExecutionRecord, RunManager
from execution.scheduler import ScheduledExecution
from models.enums import RunResult
from utils.logger import get_logger

logger = get_logger(__name__)


class ScenarioExecutor:
    """
    Executes single scheduled runs against a `ProcessManager` and produces
    `ExecutionRecord` results.

    Deliberately stateless with respect to the batch as a whole -- it does
    not know about rounds 1..10 or the other 999 runs; it only knows how
    to execute the one `ScheduledExecution` it is given. Batch-level
    orchestration belongs to `experiment_runner.py`.
    """

    def __init__(self, process_manager: ProcessManager) -> None:
        """
        Args:
            process_manager: The execution backend to run scenarios
                against (e.g. `SimulatedProcessManager` in Phase 2).
        """
        self._process_manager = process_manager

    def execute_run(self, run_id: str, scheduled: ScheduledExecution) -> ExecutionRecord:
        """
        Execute one scheduled run and return its result as an `ExecutionRecord`.

        Prints the required console status block:

            Starting Run R000001
            Scenario S0001
            Round 1
            PASS

        If the underlying process manager raises, the run is recorded as
        `RunResult.CRASH` with zero runtime rather than propagating the
        exception -- one bad run must not stop the rest of the batch.

        Args:
            run_id: The unique run identifier assigned to this attempt.
            scheduled: The scheduled execution describing what to run.

        Returns:
            The completed `ExecutionRecord` for this run.
        """
        print(f"Starting Run {run_id}")
        print(f"Scenario {scheduled.scenario_id}")
        print(f"Round {scheduled.round_number}")

        timestamp = RunManager.utc_timestamp()

        try:
            outcome = self._process_manager.run(
                scenario_id=scheduled.scenario_id, run_id=run_id
            )
            status = outcome.status
            runtime_sec = outcome.runtime_sec
        except Exception:  # noqa: BLE001 - isolate one run's failure from the batch
            logger.exception(
                "Run %s (scenario %s, round %d) raised an unexpected error",
                run_id,
                scheduled.scenario_id,
                scheduled.round_number,
            )
            status = RunResult.CRASH
            runtime_sec = 0.0

        print(status.value.upper())

        return ExecutionRecord(
            run_id=run_id,
            scenario_id=scheduled.scenario_id,
            test_id=scheduled.test_id,
            round_number=scheduled.round_number,
            status=status,
            timestamp=timestamp,
            runtime_sec=runtime_sec,
        )
