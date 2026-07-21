#!/usr/bin/env python3
"""
run_pipeline.py
----------------
Entry point for the GreenAeroTest 5-scenario pilot pipeline.

Usage:
    python run_pipeline.py

Executes the full pilot plan:
    5 scenarios x 10 repetitions = 50 total FlightGear runs,
    with the outer loop over repetitions and the inner loop over
    scenarios (never 10 consecutive runs of the same scenario).

Every attempt (pass, fail, timeout, crash, incomplete) is appended to
data/test_runs_raw.csv and data/energy_metrics_raw.csv. The script is
safe to re-run: it will resume from the last completed
(scenario, run_no) pair rather than restarting the whole plan.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow `python run_pipeline.py` to import modules from src/ without
# requiring the project to be installed as a package.
SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from config import Config  # noqa: E402
from experiment_runner import ExperimentRunner  # noqa: E402


def configure_logging(config: Config) -> None:
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    pipeline_log_path = config.logs_dir / "pipeline.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(pipeline_log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def main() -> int:
    config = Config()
    config.ensure_directories()
    configure_logging(config)

    logger = logging.getLogger("run_pipeline")
    logger.info("GreenAeroTest pilot pipeline starting.")
    logger.info("Project root: %s", config.project_root)
    logger.info("FlightGear executable: %s", config.flightgear_exe_path)
    logger.info(
        "Plan: 5 scenarios x %s repetitions = %s total runs.",
        config.repetitions,
        5 * config.repetitions,
    )

    try:
        runner = ExperimentRunner(config)
        runner.run()
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user. Progress has been saved; re-run to resume.")
        return 130
    except Exception:
        logger.exception("Pipeline terminated due to an unhandled error.")
        return 1

    logger.info("GreenAeroTest pilot pipeline finished successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
