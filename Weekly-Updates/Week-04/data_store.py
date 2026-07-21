"""
data_store.py
-------------
Appends every execution attempt to test_runs_raw.csv and
energy_metrics_raw.csv. Existing rows are never overwritten: if a run is
interrupted and resumed, the pipeline simply keeps appending, and the
CSV header is written exactly once per file.
"""

from __future__ import annotations

import csv
import logging
import threading
from pathlib import Path
from typing import Dict, List

from config import Config
from executor import ExecutionResult
from energy_collector import EnergyMeasurement

logger = logging.getLogger(__name__)

TEST_RUNS_FIELDNAMES: List[str] = [
    "run_id",
    "test_id",
    "scenario_id",
    "run_no",
    "attempt_no",
    "execution_block",
    "start_time",
    "end_time",
    "runtime_sec",
    "result",
    "return_code",
    "timeout_flag",
    "output_csv",
    "log_file",
    "environment_id",
    "random_seed",
]

ENERGY_METRICS_FIELDNAMES: List[str] = [
    "run_id",
    "test_id",
    "scenario_id",
    "avg_cpu_percent",
    "peak_cpu_percent",
    "avg_memory_mb",
    "peak_memory_mb",
    "avg_power_watts",
    "peak_power_watts",
    "energy_joules",
    "energy_wh",
    "idle_energy_joules",
    "net_energy_joules",
    "carbon_intensity_g_per_kwh",
    "estimated_carbon_gco2",
    "measurement_source",
    "measurement_notes",
    "samples_collected",
]


class DataStore:
    """Thread-safe append-only CSV writer for raw run and energy records."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._config.ensure_directories()
        self._ensure_file_with_header(
            self._config.test_runs_raw_path, TEST_RUNS_FIELDNAMES
        )
        self._ensure_file_with_header(
            self._config.energy_metrics_raw_path, ENERGY_METRICS_FIELDNAMES
        )

    @staticmethod
    def _ensure_file_with_header(path: Path, fieldnames: List[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.stat().st_size == 0:
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
            logger.debug("Initialized CSV with header: %s", path)

    def append_run_record(self, result: ExecutionResult) -> None:
        """Append one raw execution attempt to test_runs_raw.csv."""
        row: Dict[str, object] = {
            "run_id": result.run_id,
            "test_id": result.test_id,
            "scenario_id": result.scenario_id,
            "run_no": result.run_no,
            "attempt_no": result.attempt_no,
            "execution_block": result.execution_block,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "runtime_sec": result.runtime_sec,
            "result": result.result,
            "return_code": result.return_code,
            "timeout_flag": result.timeout_flag,
            "output_csv": result.output_csv,
            "log_file": result.log_file,
            "environment_id": result.environment_id,
            "random_seed": result.random_seed,
        }
        self._append_row(self._config.test_runs_raw_path, TEST_RUNS_FIELDNAMES, row)

    def append_energy_record(
        self, run_id: str, test_id: str, scenario_id: str, measurement: EnergyMeasurement
    ) -> None:
        """Append one energy measurement row, matched 1:1 to a run_id in test_runs_raw.csv."""
        row: Dict[str, object] = {
            "run_id": run_id,
            "test_id": test_id,
            "scenario_id": scenario_id,
            "avg_cpu_percent": measurement.avg_cpu_percent,
            "peak_cpu_percent": measurement.peak_cpu_percent,
            "avg_memory_mb": measurement.avg_memory_mb,
            "peak_memory_mb": measurement.peak_memory_mb,
            "avg_power_watts": measurement.avg_power_watts,
            "peak_power_watts": measurement.peak_power_watts,
            "energy_joules": measurement.energy_joules,
            "energy_wh": measurement.energy_wh,
            "idle_energy_joules": measurement.idle_energy_joules,
            "net_energy_joules": measurement.net_energy_joules,
            "carbon_intensity_g_per_kwh": measurement.carbon_intensity_g_per_kwh,
            "estimated_carbon_gco2": measurement.estimated_carbon_gco2,
            "measurement_source": measurement.measurement_source,
            "measurement_notes": measurement.measurement_notes,
            "samples_collected": measurement.samples_collected,
        }
        self._append_row(self._config.energy_metrics_raw_path, ENERGY_METRICS_FIELDNAMES, row)

    def _append_row(self, path: Path, fieldnames: List[str], row: Dict[str, object]) -> None:
        with self._lock:
            with path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writerow(row)

    def completed_run_ids(self) -> set:
        """Return the set of run_ids already present in test_runs_raw.csv.

        Used by experiment_runner.py to support resume-after-interruption
        without ever restarting the entire dataset.
        """
        path = self._config.test_runs_raw_path
        if not path.exists():
            return set()
        with self._lock:
            with path.open("r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                return {row["run_id"] for row in reader}

    def completed_scenario_run_numbers(self) -> Dict[str, set]:
        """Return {scenario_id: {run_no, ...}} for attempts already recorded
        as a non-rerunnable outcome (pass or fail) in test_runs_raw.csv.

        Used to resume without repeating scenarios that already have a
        usable result for a given run_no.
        """
        path = self._config.test_runs_raw_path
        completed: Dict[str, set] = {}
        if not path.exists():
            return completed
        with self._lock:
            with path.open("r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if row.get("result") in ("pass", "fail"):
                        scenario_id = row["scenario_id"]
                        run_no = int(row["run_no"])
                        completed.setdefault(scenario_id, set()).add(run_no)
        return completed
