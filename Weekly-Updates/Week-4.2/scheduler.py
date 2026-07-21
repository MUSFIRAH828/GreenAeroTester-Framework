"""
scheduler.py
============
Builds the execution schedule for Phase 2.

The Ten-Run Execution Protocol (spec Section 5) requires that the 10
repetitions be executed in **randomized/rotating blocks** rather than
running one scenario ten consecutive times:

    Round 1: S001, S002, ..., S100
    Round 2: S001, S002, ..., S100
    ...
    Round 10: S001, S002, ..., S100

This module owns exactly that ordering rule. It does not execute
anything, collect energy, or write any output files -- it only decides
*what* runs in *what* order, producing a flat, already-sequenced list of
`ScheduledExecution` entries that `experiment_runner.py` iterates over.

Keeping the schedule as a pure, side-effect-free computation makes it
trivial to unit test ("does round 3 contain each scenario exactly once,
in catalog order?") without touching the filesystem or sleeping.
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ScenarioReference:
    """
    The minimal scenario identity needed to schedule and execute a run.

    Deliberately narrow (just IDs) rather than the full `Scenario` model
    from Phase 1 -- the scheduler and executor only need to know *which*
    scenario to run, not every generation-time parameter.
    """

    scenario_id: str
    test_id: str


@dataclass(frozen=True)
class ScheduledExecution:
    """One planned execution: a specific scenario run within a specific round."""

    sequence_number: int  # 1-based position across the entire schedule (1..1000)
    round_number: int     # 1-based repetition number (1..10)
    scenario_id: str
    test_id: str


class SchedulingError(Exception):
    """Raised when a schedule cannot be built consistently."""


class ExecutionScheduler:
    """
    Produces the full, ordered list of planned executions.

    The outer loop is repetitions (rounds); the inner loop is scenarios,
    iterated in the exact order they were read from
    `scenario_catalog.csv` -- matching the "S001..S100 per round" rule
    from the spec exactly, with no scenario ever repeated back-to-back.
    """

    def __init__(self, scenarios: list[ScenarioReference], repetitions: int) -> None:
        """
        Args:
            scenarios: Ordered list of scenarios to schedule, normally read
                from `scenario_catalog.csv` in catalog order.
            repetitions: Number of rounds each scenario must appear in.

        Raises:
            SchedulingError: if `scenarios` is empty or `repetitions` < 1.
        """
        if not scenarios:
            raise SchedulingError("Cannot build a schedule from an empty scenario list")
        if repetitions < 1:
            raise SchedulingError(f"repetitions must be >= 1, got {repetitions}")

        self._scenarios = scenarios
        self._repetitions = repetitions

    def build_schedule(self) -> list[ScheduledExecution]:
        """
        Build the full round-major, scenario-minor execution schedule.

        Returns:
            A list of `len(scenarios) * repetitions` `ScheduledExecution`
            entries, ordered round 1 (all scenarios) -> round 2 (all
            scenarios) -> ... -> round N (all scenarios).
        """
        schedule: list[ScheduledExecution] = []
        sequence_number = 0

        for round_number in range(1, self._repetitions + 1):
            for scenario in self._scenarios:
                sequence_number += 1
                schedule.append(
                    ScheduledExecution(
                        sequence_number=sequence_number,
                        round_number=round_number,
                        scenario_id=scenario.scenario_id,
                        test_id=scenario.test_id,
                    )
                )

        expected_total = len(self._scenarios) * self._repetitions
        if len(schedule) != expected_total:
            raise SchedulingError(
                f"Expected {expected_total} scheduled executions, built {len(schedule)}"
            )

        logger.info(
            "Built execution schedule: %d scenarios x %d rounds = %d planned executions",
            len(self._scenarios),
            self._repetitions,
            len(schedule),
        )
        return schedule
