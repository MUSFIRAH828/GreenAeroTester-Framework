"""
config.py
---------
Central, typed configuration for the GreenAeroTest pilot pipeline.

This module is not part of the originally requested folder list but is
added under src/ because every other module needs the same set of
configurable constants (FlightGear path, timeouts, cooldown, etc.).
Centralizing them here avoids hardcoded paths/values being duplicated
across executor.py, energy_collector.py, data_store.py and
experiment_runner.py, and gives you a single place to edit before a run.

All values can be overridden via environment variables so the pipeline
can be reconfigured without touching source code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_path(var_name: str, default: str) -> str:
    """Read a path-like value from the environment, falling back to default."""
    return os.environ.get(var_name, default)


def _env_float(var_name: str, default: float) -> float:
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(var_name: str, default: int) -> int:
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Immutable configuration container for the pilot pipeline.

    All paths are resolved relative to the project root unless an
    absolute path is supplied via the corresponding environment
    variable.
    """

    # ------------------------------------------------------------------
    # Project layout
    # ------------------------------------------------------------------
    project_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )

    # ------------------------------------------------------------------
    # FlightGear / simulator configuration
    # ------------------------------------------------------------------
    flightgear_exe_path: str = field(
        default_factory=lambda: _env_path(
            "GAT_FLIGHTGEAR_EXE",
            r"C:\Program Files\FlightGear 2020.3\bin\fgfs.exe",
        )
    )
    fdm: str = field(default_factory=lambda: os.environ.get("GAT_FDM", "jsbsim"))

    # ------------------------------------------------------------------
    # Timing configuration
    # ------------------------------------------------------------------
    run_duration_sec: int = field(
        default_factory=lambda: _env_int("GAT_RUN_DURATION_SEC", 90)
    )
    timeout_sec: int = field(
        default_factory=lambda: _env_int("GAT_TIMEOUT_SEC", 180)
    )
    cooldown_sec: float = field(
        default_factory=lambda: _env_float("GAT_COOLDOWN_SEC", 10.0)
    )
    process_poll_interval_sec: float = field(
        default_factory=lambda: _env_float("GAT_POLL_INTERVAL_SEC", 1.0)
    )

    # ------------------------------------------------------------------
    # Energy / power estimation configuration
    # ------------------------------------------------------------------
    # Used by the default TDP-based estimation strategy in
    # energy_collector.py. Replace with a measured value for your
    # workstation, or swap in a CodeCarbon-backed strategy later.
    estimated_tdp_watts: float = field(
        default_factory=lambda: _env_float("GAT_ESTIMATED_TDP_WATTS", 65.0)
    )
    idle_power_watts: float = field(
        default_factory=lambda: _env_float("GAT_IDLE_POWER_WATTS", 12.0)
    )
    carbon_intensity_g_per_kwh: float = field(
        default_factory=lambda: _env_float("GAT_CARBON_INTENSITY_G_PER_KWH", 400.0)
    )
    energy_sample_interval_sec: float = field(
        default_factory=lambda: _env_float("GAT_ENERGY_SAMPLE_INTERVAL_SEC", 1.0)
    )
    measurement_source: str = field(
        default_factory=lambda: os.environ.get(
            "GAT_MEASUREMENT_SOURCE", "cpu_tdp_estimation"
        )
    )

    # ------------------------------------------------------------------
    # Pilot execution plan
    # ------------------------------------------------------------------
    repetitions: int = field(default_factory=lambda: _env_int("GAT_REPETITIONS", 10))
    environment_id: str = field(
        default_factory=lambda: os.environ.get("GAT_ENVIRONMENT_ID", "ENV001")
    )
    experiment_id: str = field(
        default_factory=lambda: os.environ.get("GAT_EXPERIMENT_ID", "EXP001")
    )
    random_seed: int = field(default_factory=lambda: _env_int("GAT_RANDOM_SEED", 42))

    # ------------------------------------------------------------------
    # Derived paths (computed, not overridable individually)
    # ------------------------------------------------------------------
    @property
    def scenarios_dir(self) -> Path:
        return self.project_root / "scenarios"

    @property
    def scenario_catalog_path(self) -> Path:
        return self.scenarios_dir / "scenario_catalog.csv"

    @property
    def scripts_dir(self) -> Path:
        return self.project_root / "scripts"

    @property
    def run_scenario_script_path(self) -> Path:
        return self.scripts_dir / "run_scenario.ps1"

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def test_runs_raw_path(self) -> Path:
        return self.data_dir / "test_runs_raw.csv"

    @property
    def energy_metrics_raw_path(self) -> Path:
        return self.data_dir / "energy_metrics_raw.csv"

    @property
    def outputs_dir(self) -> Path:
        return self.project_root / "outputs"

    @property
    def logs_dir(self) -> Path:
        return self.outputs_dir / "logs"

    @property
    def flight_csv_dir(self) -> Path:
        return self.outputs_dir / "flight_csv"

    @property
    def power_traces_dir(self) -> Path:
        return self.outputs_dir / "raw_power_traces"

    def ensure_directories(self) -> None:
        """Create every output directory the pipeline writes to, if missing."""
        for directory in (
            self.data_dir,
            self.logs_dir,
            self.flight_csv_dir,
            self.power_traces_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
