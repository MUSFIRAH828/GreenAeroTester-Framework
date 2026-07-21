"""
settings.py
===========
Environment-specific configuration: filesystem paths, directory layout,
and default runtime knobs.

Unlike `constants.py` (spec taxonomy, never changes), everything in this
file is allowed to vary between machines/environments. Centralizing paths
here means Phase 2+ modules (executor, energy collector, data_store, ...)
never hardcode a path string -- they import `settings` instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------
# BACKEND_ROOT resolves to the `backend/` directory regardless of the
# current working directory the script is launched from.
BACKEND_ROOT: Path = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    """
    Central registry of every directory the backend reads from or writes to.

    Frozen so paths cannot be accidentally reassigned at runtime; call
    `ensure_all()` once at startup to make sure every directory exists.
    """

    backend_root: Path = BACKEND_ROOT

    # scenarios/
    scenarios_dir: Path = BACKEND_ROOT / "scenarios"
    scenarios_generated_dir: Path = BACKEND_ROOT / "scenarios" / "generated"
    scenario_catalog_csv: Path = BACKEND_ROOT / "scenarios" / "scenario_catalog.csv"
    scenario_parameters_csv: Path = BACKEND_ROOT / "scenarios" / "scenario_parameters.csv"

    # logs (used by utils/logger.py)
    logs_dir: Path = BACKEND_ROOT / "logs"

    def ensure_all(self) -> None:
        """Create every directory referenced above if it does not exist yet."""
        directories = (
            self.scenarios_dir,
            self.scenarios_generated_dir,
            self.logs_dir,
        )
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    """
    Top-level application settings.

    Only scenario-generation-relevant settings are populated in Phase 1.
    Execution, energy-measurement, and dashboard settings will be added to
    this dataclass in later phases without breaking existing callers,
    since new fields will carry sensible defaults.
    """

    paths: Paths = field(default_factory=Paths)

    # Project identity
    project_name: str = "GreenAeroTest"

    # Simulator identity (used for documentation / metadata only in Phase 1)
    simulator_name: str = "FlightGear"
    flight_dynamics_model: str = "JSBSim"

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True

    # Scenario generation
    scenario_file_extension: str = ".xml"  # placeholder FlightGear scenario config format


# Single shared instance imported by every other module.
settings = Settings()
