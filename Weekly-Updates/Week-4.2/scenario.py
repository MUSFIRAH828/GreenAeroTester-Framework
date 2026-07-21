"""
scenario.py
===========
Data model for a single generated scenario.

A `Scenario` is the in-memory representation of one row of the 10 (flight
phase) x 5 (weather) x 2 (mode) factorial matrix defined in Spec Section 3.
The `scenario_generator.py` module builds 100 of these, and this class
knows how to flatten itself into the two CSV formats required by the spec:

- scenario_catalog.csv      -> `to_catalog_row()`
- scenario_parameters.csv   -> `to_parameters_row()`

Keeping the "what a scenario is" model separate from the "how we generate
100 of them" logic (scenario_generator.py) keeps each file focused and
makes the model reusable by Phase 2 modules (executor, validators, etc.)
without pulling in generation logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.constants import RUN_DURATION_SECONDS
from models.enums import FlightPhase, SystemMode, WeatherProfile


@dataclass(frozen=True)
class Scenario:
    """
    Immutable representation of a single generated scenario.

    Frozen because a scenario, once generated and written to the catalog,
    should never be silently mutated -- any change should go through the
    generator so the catalog and parameters files stay consistent.
    """

    # --- Identity -----------------------------------------------------
    scenario_id: str          # e.g. "S0001"
    test_id: str              # e.g. "T0001" (1:1 with scenario_id)

    # --- Flight phase ---------------------------------------------------
    flight_phase_code: FlightPhase
    flight_phase_name: str
    phase_fault_definition: str  # fault used IF this scenario is faulted

    # --- Weather ---------------------------------------------------------
    weather_code: WeatherProfile
    weather_name: str
    weather_meaning: str

    # --- System mode -------------------------------------------------------
    mode_code: SystemMode
    mode_name: str
    mode_meaning: str

    # --- Derived / applied fault --------------------------------------------
    is_faulted: bool
    applied_fault: str  # equals phase_fault_definition if faulted, else ""

    # --- File system -----------------------------------------------------
    scenario_file_name: str
    scenario_file_path: str
    output_dir: str

    # --- Reproducibility / execution metadata -----------------------------
    random_seed: int
    run_duration_sec: int = RUN_DURATION_SECONDS

    def to_catalog_row(self) -> dict[str, object]:
        """
        Flatten to the row schema for `scenario_catalog.csv`
        (Spec 7: "One row per scenario").
        """
        return {
            "scenario_id": self.scenario_id,
            "test_id": self.test_id,
            "flight_phase_code": self.flight_phase_code.value,
            "flight_phase_name": self.flight_phase_name,
            "weather_code": self.weather_code.value,
            "weather_name": self.weather_name,
            "mode_code": self.mode_code.value,
            "mode_name": self.mode_name,
            "is_faulted": self.is_faulted,
            "applied_fault": self.applied_fault,
            "scenario_file_name": self.scenario_file_name,
            "output_dir": self.output_dir,
        }

    def to_parameters_row(self) -> dict[str, object]:
        """
        Flatten to the row schema for `scenario_parameters.csv`
        (Spec 7: "Full parameter values per scenario").

        Carries every field, including descriptive metadata that is
        useful for scenario file generation in Phase 2 but would be
        redundant in the lightweight catalog file.
        """
        return {
            "scenario_id": self.scenario_id,
            "test_id": self.test_id,
            "flight_phase_code": self.flight_phase_code.value,
            "flight_phase_name": self.flight_phase_name,
            "phase_fault_definition": self.phase_fault_definition,
            "weather_code": self.weather_code.value,
            "weather_name": self.weather_name,
            "weather_meaning": self.weather_meaning,
            "mode_code": self.mode_code.value,
            "mode_name": self.mode_name,
            "mode_meaning": self.mode_meaning,
            "is_faulted": self.is_faulted,
            "applied_fault": self.applied_fault,
            "scenario_file_name": self.scenario_file_name,
            "scenario_file_path": self.scenario_file_path,
            "output_dir": self.output_dir,
            "random_seed": self.random_seed,
            "run_duration_sec": self.run_duration_sec,
        }
