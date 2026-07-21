"""
experiment_runner.py
=====================
Top-level orchestrator for Phase 2.

`ExperimentRunner` is the single entry point `main.py` calls to go from
"a scenario catalog exists on disk" to "1000 executions have run (in
simulation mode) and `execution_plan.csv` has been written". It wires
together every other module in this package:

    scenario_catalog.csv
            |
            v
    ExecutionScheduler   (scheduler.py)   -> ordered ScheduledExecution list
            |
            v
    RunIdGenerator + ScenarioExecutor     -> ExecutionRecord per run
    (run_manager.py)    (executor.py)         (via ProcessManager, process_manager.py)
            |
            v
    RunManager.write_execution_plan()     -> execution_plan.csv

--- Resume / checkpoint patch -------------------------------------------
If `execution_plan.csv` already exists when `run()` starts, its rows are
loaded first. Any `(scenario_id, round_number)` pair already present is
treated as already completed and is skipped when the schedule is walked.
Run IDs resume from the highest sequence number already on disk, so
resumed runs never collide with previously issued run IDs. After every
run, `execution_plan.csv` is rewritten (checkpointed) so an interruption
never loses more than the one run in flight. If nothing remains to run,
`"Execution already completed. Nothing to run."` is printed and no
process manager work is done.
"""

from __future__ import annotations

import csv
from pathlib import Path

from config.constants import USABLE_REPETITIONS_PER_SCENARIO
from config.settings import settings
from execution.executor import ScenarioExecutor
from execution.process_manager import ProcessManager, SimulatedProcessManager
from execution.run_manager import RunIdGenerator, RunManager
from execution.scheduler import ExecutionScheduler, ScenarioReference
from utils.logger import get_logger

logger = get_logger(__name__)

#: Location of this phase's output file. Co-located with the execution
#: package, mirroring how Phase 1 keeps `scenario_catalog.csv` inside
#: `scenarios/`.
EXECUTION_PLAN_CSV: Path = settings.paths.backend_root / "execution" / "execution_plan.csv"


class ExperimentRunnerError(Exception):
    """Raised when the Phase 2 batch cannot be prepared or completed."""


class ExperimentRunner:
    """
    Loads the scenario catalog, builds the execution schedule, runs every
    planned execution, and writes `execution_plan.csv`.
    """

    def __init__(
        self,
        catalog_path: Path | None = None,
        repetitions: int = USABLE_REPETITIONS_PER_SCENARIO,
        process_manager: ProcessManager | None = None,
        output_path: Path = EXECUTION_PLAN_CSV,
    ) -> None:
        """
        Args:
            catalog_path: Path to `scenario_catalog.csv`. Defaults to the
                Phase 1 output location registered in `config/settings.py`.
            repetitions: Number of rounds to schedule per scenario.
                Defaults to the spec's 10 (`USABLE_REPETITIONS_PER_SCENARIO`).
            process_manager: Execution backend. Defaults to
                `SimulatedProcessManager` since FlightGear integration is
                not implemented yet. A future phase can inject a real
                FlightGear-backed `ProcessManager` here without any other
                change to this class.
            output_path: Where to write `execution_plan.csv`.
        """
        self._catalog_path = catalog_path or settings.paths.scenario_catalog_csv
        self._repetitions = repetitions
        self._process_manager = process_manager or SimulatedProcessManager()
        self._output_path = output_path

    def run(self) -> dict[str, int]:
        """
        Execute the full Phase 2 batch end to end, resuming from any
        existing `execution_plan.csv` checkpoint if present.

        Returns:
            A summary dict, e.g. {"total": 1000, "pass": 1000}.

        Raises:
            ExperimentRunnerError: if the catalog cannot be read or is empty.
        """
        scenarios = self._load_scenarios()

        scheduler = ExecutionScheduler(scenarios=scenarios, repetitions=self._repetitions)
        schedule = scheduler.build_schedule()

        run_manager = RunManager()
        completed_keys: set[tuple[str, int]] = set()

        if self._output_path.exists():
            existing_records = RunManager.read_execution_plan(self._output_path)
            for existing_record in existing_records:
                run_manager.record(existing_record)
                completed_keys.add((existing_record.scenario_id, existing_record.round_number))
            if existing_records:
                logger.info(
                    "Resuming from checkpoint: %d of %d planned runs already completed",
                    len(existing_records),
                    len(schedule),
                )

        remaining_schedule = [
            scheduled
            for scheduled in schedule
            if (scheduled.scenario_id, scheduled.round_number) not in completed_keys
        ]

        if not remaining_schedule:
            logger.info("Execution already completed. Nothing to run.")
            print("Execution already completed. Nothing to run.")
            return run_manager.summary()

        executor = ScenarioExecutor(process_manager=self._process_manager)
        run_id_generator = RunIdGenerator(
            start_at=RunIdGenerator.next_start_at(
                [record.run_id for record in run_manager.records]
            )
        )

        logger.info(
            "Starting execution of %d remaining planned runs (%d already complete)",
            len(remaining_schedule),
            len(completed_keys),
        )
        for scheduled in remaining_schedule:
            run_id = run_id_generator.next_id()
            record = executor.execute_run(run_id=run_id, scheduled=scheduled)
            run_manager.record(record)
            # Checkpoint after every run so an interruption loses at most
            # the one run currently in flight.
            run_manager.write_execution_plan(self._output_path)

        summary = run_manager.summary()
        logger.info("Execution complete: %s", summary)
        return summary

    def _load_scenarios(self) -> list[ScenarioReference]:
        """
        Read `scenario_catalog.csv` and return scenarios in file order.

        Returns:
            One `ScenarioReference` per catalog row, preserving row order
            so the schedule's "S001..S100" sequence matches the catalog.

        Raises:
            ExperimentRunnerError: if the file is missing, unreadable, or
                contains no rows.
        """
        if not self._catalog_path.exists():
            raise ExperimentRunnerError(
                f"Scenario catalog not found at {self._catalog_path}. "
                "Run Phase 1 scenario generation first."
            )

        scenarios: list[ScenarioReference] = []
        try:
            with self._catalog_path.open(mode="r", newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    scenarios.append(
                        ScenarioReference(
                            scenario_id=row["scenario_id"],
                            test_id=row["test_id"],
                        )
                    )
        except (OSError, csv.Error, KeyError) as exc:
            raise ExperimentRunnerError(
                f"Failed to read scenario catalog at {self._catalog_path}: {exc}"
            ) from exc

        if not scenarios:
            raise ExperimentRunnerError(
                f"Scenario catalog at {self._catalog_path} contains no rows"
            )

        logger.info("Loaded %d scenarios from %s", len(scenarios), self._catalog_path)
        return scenarios