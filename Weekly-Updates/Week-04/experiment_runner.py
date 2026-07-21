"""
experiment_runner.py
---------------------
Drives the pilot execution plan:

    Run 1: S001, S002, S003, S004, S005
    Run 2: S001, S002, S003, S004, S005
    ...
    Run 10: S001, S002, S003, S004, S005

    => 5 scenarios x 10 repetitions = 50 total executions.

The OUTER loop is the repetition number (1..10, "execution block").
The INNER loop iterates through the five scenarios in catalog order.
This matches the randomized-block execution protocol described in the
specification (every block contains all scenarios exactly once) while
keeping the pilot's block order deterministic, since the pilot's goal
is to validate the execution path rather than run the full randomized
generator.

For each (repetition, scenario) pair:
    1. A unique run_id is generated.
    2. ScenarioExecutor launches FlightGear and waits for the outcome.
    3. EnergyCollector samples CPU/memory/power for the duration of the run.
    4. DataStore appends both the raw run record and the raw energy record.

If interrupted, re-running this module resumes from the last completed
(scenario, run_no) pair instead of restarting the whole 50-run plan,
and reruns timeout/crash/incomplete attempts until every scenario has
its full set of usable repetitions.
"""

from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from config import Config
from data_store import DataStore
from energy_collector import EnergyCollector
from executor import ScenarioDefinition, ScenarioExecutor, ScenarioLoadError

logger = logging.getLogger(__name__)

RERUNNABLE_RESULTS = {"timeout", "crash", "incomplete"}


@dataclass
class CatalogEntry:
    scenario_id: str
    test_id: str
    scenario_file: str


class ExperimentRunner:
    """Orchestrates the full pilot run: nested loops, run-id generation,
    execution, energy collection, and persistence.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._executor = ScenarioExecutor(config)
        self._data_store = DataStore(config)
        self._run_counter = self._initialize_run_counter()

    def run(self) -> None:
        """Execute the full 5-scenario x 10-repetition pilot plan."""
        catalog = self._load_catalog()
        if len(catalog) == 0:
            raise RuntimeError(
                f"No scenarios found in {self._config.scenario_catalog_path}"
            )

        completed = self._data_store.completed_scenario_run_numbers()

        total_planned = len(catalog) * self._config.repetitions
        completed_count = sum(len(v) for v in completed.values())
        logger.info(
            "Starting pilot execution: %s scenarios x %s repetitions = %s planned runs "
            "(%s already completed, resuming).",
            len(catalog),
            self._config.repetitions,
            total_planned,
            completed_count,
        )

        for run_no in range(1, self._config.repetitions + 1):
            for entry in catalog:
                already_done = run_no in completed.get(entry.scenario_id, set())
                if already_done:
                    logger.info(
                        "Skipping %s run_no=%s (already completed).",
                        entry.scenario_id,
                        run_no,
                    )
                    continue

                self._execute_with_reruns(entry, run_no, execution_block=run_no)

        logger.info("Pilot execution complete: 50 planned executions processed.")

    def _execute_with_reruns(
        self, entry: CatalogEntry, run_no: int, execution_block: int
    ) -> None:
        """Execute a single (scenario, run_no) slot, rerunning on
        timeout/crash/incomplete until a usable pass/fail outcome is
        recorded, or attempts are exhausted.
        """
        max_attempts = self._config.repetitions  # generous cap; avoids infinite retry storms
        attempt_no = 1

        try:
            scenario = self._executor.load_scenario(entry.scenario_id, entry.scenario_file)
        except ScenarioLoadError:
            logger.exception(
                "Failed to load scenario %s; skipping this run_no=%s.",
                entry.scenario_id,
                run_no,
            )
            return

        while attempt_no <= max_attempts:
            run_id = self._next_run_id()
            logger.info(
                "Executing scenario=%s run_no=%s attempt_no=%s run_id=%s",
                entry.scenario_id,
                run_no,
                attempt_no,
                run_id,
            )

            energy_collector = EnergyCollector(self._config)
            energy_collector.start()
            result = self._executor.execute(
                scenario=scenario,
                run_id=run_id,
                run_no=run_no,
                attempt_no=attempt_no,
                execution_block=execution_block,
            )
            measurement = energy_collector.stop()

            self._data_store.append_run_record(result)
            self._data_store.append_energy_record(
                run_id=run_id,
                test_id=entry.test_id,
                scenario_id=entry.scenario_id,
                measurement=measurement,
            )

            if result.result not in RERUNNABLE_RESULTS:
                logger.info(
                    "scenario=%s run_no=%s resolved as '%s' after %s attempt(s).",
                    entry.scenario_id,
                    run_no,
                    result.result,
                    attempt_no,
                )
                break

            logger.warning(
                "scenario=%s run_no=%s attempt_no=%s returned '%s'; will retry.",
                entry.scenario_id,
                run_no,
                attempt_no,
                result.result,
            )
            attempt_no += 1
            self._cooldown()

        else:
            logger.error(
                "scenario=%s run_no=%s exhausted %s attempts without a usable outcome.",
                entry.scenario_id,
                run_no,
                max_attempts,
            )

        self._cooldown()

    def _cooldown(self) -> None:
        if self._config.cooldown_sec > 0:
            time.sleep(self._config.cooldown_sec)

    def _load_catalog(self) -> List[CatalogEntry]:
        path = self._config.scenario_catalog_path
        if not path.exists():
            raise FileNotFoundError(f"Scenario catalog not found: {path}")

        entries: List[CatalogEntry] = []
        with path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                entries.append(
                    CatalogEntry(
                        scenario_id=row["scenario_id"],
                        test_id=row["test_id"],
                        scenario_file=row["scenario_file"],
                    )
                )
        return entries

    def _initialize_run_counter(self) -> int:
        """Resume the R###### numbering sequence from the highest run_id
        already present in test_runs_raw.csv, so reruns never collide
        with previously recorded run_ids.
        """
        existing_ids = self._data_store.completed_run_ids()
        max_seen = 0
        for run_id in existing_ids:
            if run_id.startswith("R") and run_id[1:].isdigit():
                max_seen = max(max_seen, int(run_id[1:]))
        return max_seen

    def _next_run_id(self) -> str:
        self._run_counter += 1
        return f"R{self._run_counter:06d}"
