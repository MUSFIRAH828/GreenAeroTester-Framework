"""
main.py
=======
Pipeline entry point: Phase 1 (scenario generation) + Phase 2 (execution).

Phase 1 generates the deterministic 100-scenario catalog and writes it to
disk. Phase 2 then reads that catalog, builds the 100 x 10 = 1000-run
execution schedule, executes every run (currently in simulation mode --
FlightGear integration is not implemented yet), and writes
`execution/execution_plan.csv`.

Run with:
    cd backend
    python main.py

Later phases will extend this file further (or introduce `run_pipeline.py`
at the repo root, per the full spec's Section 6 structure) to add energy
collection, validation, assurance scoring, prioritization, and reporting
after execution.
"""

from __future__ import annotations

import sys

from config.settings import settings
from execution.experiment_runner import ExperimentRunner, ExperimentRunnerError
from scenarios.scenario_generator import ScenarioGenerationError, ScenarioGenerator
from utils.logger import configure_logging, get_logger


def main() -> int:
    """
    Run Phase 1 (scenario generation) followed by Phase 2 (execution).

    Returns:
        Process exit code (0 = success, 1 = failure).
    """
    settings.paths.ensure_all()
    configure_logging(
        log_level=settings.log_level,
        log_to_file=settings.log_to_file,
        logs_dir=settings.paths.logs_dir,
    )
    logger = get_logger(__name__)

    logger.info("=== %s backend | Phase 1: Scenario Generation ===", settings.project_name)
    logger.info(
        "Simulator: %s | FDM: %s", settings.simulator_name, settings.flight_dynamics_model
    )

    try:
        generator = ScenarioGenerator()
        scenarios = generator.generate_all()
        generator.write_outputs(scenarios)
    except ScenarioGenerationError:
        logger.exception("Scenario generation failed validation checks")
        return 1
    except OSError:
        logger.exception("A filesystem error occurred while writing generator outputs")
        return 1
    except Exception:  # noqa: BLE001 - top-level safety net for Phase 1 CLI entry point
        logger.exception("Unexpected error during Phase 1 execution")
        return 1

    logger.info(
        "Phase 1 complete. %d scenarios generated. Catalog: %s | Parameters: %s",
        len(scenarios),
        settings.paths.scenario_catalog_csv,
        settings.paths.scenario_parameters_csv,
    )

    logger.info("=== %s backend | Phase 2: Execution Engine (simulation mode) ===",
                settings.project_name)
    try:
        runner = ExperimentRunner()
        summary = runner.run()
    except ExperimentRunnerError:
        logger.exception("Phase 2 execution batch failed")
        return 1
    except Exception:  # noqa: BLE001 - top-level safety net for Phase 2 CLI entry point
        logger.exception("Unexpected error during Phase 2 execution")
        return 1

    logger.info("Phase 2 complete. Execution summary: %s", summary)
    print("\n=== Execution Summary ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
