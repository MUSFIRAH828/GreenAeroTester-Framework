"""
scenario_generator.py
======================
Programmatic generation of the full 100-scenario catalog
(10 flight phases x 5 weather profiles x 2 system modes).

This module owns ONLY scenario generation. It does not launch FlightGear,
collect energy, validate runs, score assurance, or prioritize tests -- those
responsibilities belong to Phase 2+ modules (`executor.py`,
`energy_collector.py`, `validators.py`, `assurance_scorer.py`,
`prioritizer.py`).

Usage:
    generator = ScenarioGenerator()
    scenarios = generator.generate_all()
    generator.write_outputs(scenarios)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.constants import (
    FLIGHT_PHASES,
    NUM_FLIGHT_PHASES,
    NUM_SYSTEM_MODES,
    NUM_WEATHER_PROFILES,
    SCENARIO_GENERATION_SEED,
    SCENARIO_ID_DIGITS,
    SCENARIO_ID_PREFIX,
    SYSTEM_MODES,
    TEST_ID_DIGITS,
    TEST_ID_PREFIX,
    TOTAL_SCENARIOS,
    WEATHER_PROFILES,
    FlightPhaseInfo,
    SystemModeInfo,
    WeatherProfileInfo,
)
from config.settings import settings
from models.enums import SystemMode
from models.scenario import Scenario
from utils.file_manager import FileManager
from utils.logger import get_logger

logger = get_logger(__name__)


class ScenarioGenerationError(Exception):
    """Raised when the generator cannot produce a valid, complete catalog."""


@dataclass(frozen=True)
class ScenarioGeneratorConfig:
    """
    Tunable knobs for a generation run.

    Kept separate from `Scenario` itself so the generator's behavior
    (seed, extension, output roots) can be swapped -- e.g. in unit tests --
    without touching the data model.
    """

    random_seed: int = SCENARIO_GENERATION_SEED
    scenario_file_extension: str = settings.scenario_file_extension
    generated_dir: Path = settings.paths.scenarios_generated_dir
    output_root: str = "outputs"  # base for each scenario's own run-output subdir


class ScenarioGenerator:
    """
    Builds the deterministic 10 x 5 x 2 scenario matrix described in
    Dataset Implementation Specification, Section 3.

    Determinism is guaranteed by:
    1. Iterating the three taxonomies in a fixed, spec-defined order
       (flight phase -> weather profile -> system mode), matching the
       pseudocode in Spec 3.4 exactly.
    2. Deriving each scenario's `random_seed` from a single base seed via
       a fixed formula, so re-running the generator always reproduces the
       same catalog, byte-for-byte.
    """

    def __init__(self, config: ScenarioGeneratorConfig | None = None) -> None:
        self.config = config or ScenarioGeneratorConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_all(self) -> list[Scenario]:
        """
        Generate all 100 `Scenario` objects in deterministic order.

        Returns:
            A list of exactly `TOTAL_SCENARIOS` (100) `Scenario` instances,
            ordered as: phase 1..10 x weather 1..5 x mode [nominal, faulted].

        Raises:
            ScenarioGenerationError: if the generated count does not match
                the expected total (defensive check -- should never trigger
                given the fixed taxonomies in constants.py).
        """
        logger.info(
            "Generating scenario catalog: %d phases x %d weather profiles x "
            "%d modes = %d scenarios",
            NUM_FLIGHT_PHASES,
            NUM_WEATHER_PROFILES,
            NUM_SYSTEM_MODES,
            TOTAL_SCENARIOS,
        )

        scenarios: list[Scenario] = []
        sequence_number = 0  # drives scenario_id / test_id / seed derivation

        for phase in FLIGHT_PHASES:
            for weather in WEATHER_PROFILES:
                for mode in SYSTEM_MODES:
                    sequence_number += 1
                    scenario = self._build_scenario(
                        sequence_number=sequence_number,
                        phase=phase,
                        weather=weather,
                        mode=mode,
                    )
                    scenarios.append(scenario)

        if len(scenarios) != TOTAL_SCENARIOS:
            raise ScenarioGenerationError(
                f"Expected {TOTAL_SCENARIOS} scenarios, generated {len(scenarios)}"
            )

        logger.info("Generated %d scenarios successfully", len(scenarios))
        return scenarios

    def write_outputs(self, scenarios: list[Scenario]) -> None:
        """
        Persist the generated catalog to disk:

        1. `scenario_catalog.csv`     -- one summary row per scenario.
        2. `scenario_parameters.csv`  -- one full-detail row per scenario.
        3. One placeholder scenario definition file per scenario, written
           under `scenarios/generated/`.

        Args:
            scenarios: The full list of generated scenarios (normally the
                output of `generate_all()`).
        """
        settings.paths.ensure_all()

        FileManager.write_csv(
            path=settings.paths.scenario_catalog_csv,
            fieldnames=list(scenarios[0].to_catalog_row().keys()),
            rows=(s.to_catalog_row() for s in scenarios),
        )

        FileManager.write_csv(
            path=settings.paths.scenario_parameters_csv,
            fieldnames=list(scenarios[0].to_parameters_row().keys()),
            rows=(s.to_parameters_row() for s in scenarios),
        )

        for scenario in scenarios:
            self._write_placeholder_scenario_file(scenario)

        logger.info(
            "Scenario generation outputs written: catalog=%s, parameters=%s, "
            "generated_files_dir=%s",
            settings.paths.scenario_catalog_csv,
            settings.paths.scenario_parameters_csv,
            self.config.generated_dir,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_scenario(
        self,
        sequence_number: int,
        phase: FlightPhaseInfo,
        weather: WeatherProfileInfo,
        mode: SystemModeInfo,
    ) -> Scenario:
        """Construct one fully-populated `Scenario` from taxonomy rows."""
        scenario_id = self._format_id(
            SCENARIO_ID_PREFIX, sequence_number, SCENARIO_ID_DIGITS
        )
        test_id = self._format_id(TEST_ID_PREFIX, sequence_number, TEST_ID_DIGITS)

        is_faulted = mode.code == SystemMode.FAULTED
        applied_fault = phase.fault_used_in_faulted_mode if is_faulted else ""

        scenario_file_name = (
            f"{scenario_id}_{phase.code.value}_{weather.code.value}_"
            f"{mode.code.value}{self.config.scenario_file_extension}"
        )
        scenario_file_path = str(self.config.generated_dir / scenario_file_name)
        output_dir = f"{self.config.output_root}/{test_id}"

        # Deterministic per-scenario seed derived from the base seed, so the
        # whole catalog is reproducible from a single configured value.
        derived_seed = self.config.random_seed + sequence_number

        return Scenario(
            scenario_id=scenario_id,
            test_id=test_id,
            flight_phase_code=phase.code,
            flight_phase_name=phase.display_name,
            phase_fault_definition=phase.fault_used_in_faulted_mode,
            weather_code=weather.code,
            weather_name=weather.display_name,
            weather_meaning=weather.implementation_meaning,
            mode_code=mode.code,
            mode_name=mode.display_name,
            mode_meaning=mode.meaning,
            is_faulted=is_faulted,
            applied_fault=applied_fault,
            scenario_file_name=scenario_file_name,
            scenario_file_path=scenario_file_path,
            output_dir=output_dir,
            random_seed=derived_seed,
        )

    def _write_placeholder_scenario_file(self, scenario: Scenario) -> None:
        """
        Write a placeholder scenario definition file to
        `scenarios/generated/`.

        This is NOT a real, executable FlightGear/JSBSim launch
        configuration -- building that is explicitly out of scope for
        Phase 1. It is a structured, human-readable placeholder capturing
        every parameter the Phase 2 executor will need in order to build
        the real configuration and launch command.
        """
        content = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<!-- PLACEHOLDER scenario definition. Not yet a runnable\n"
            "     FlightGear/JSBSim configuration. To be completed by the\n"
            "     Phase 2 scenario-to-config builder. -->\n"
            "<scenario_definition>\n"
            f"  <scenario_id>{scenario.scenario_id}</scenario_id>\n"
            f"  <test_id>{scenario.test_id}</test_id>\n"
            f"  <flight_phase code=\"{scenario.flight_phase_code.value}\">"
            f"{scenario.flight_phase_name}</flight_phase>\n"
            f"  <weather_profile code=\"{scenario.weather_code.value}\">"
            f"{scenario.weather_name}</weather_profile>\n"
            f"  <system_mode code=\"{scenario.mode_code.value}\">"
            f"{scenario.mode_name}</system_mode>\n"
            f"  <is_faulted>{str(scenario.is_faulted).lower()}</is_faulted>\n"
            f"  <applied_fault>{scenario.applied_fault}</applied_fault>\n"
            f"  <run_duration_sec>{scenario.run_duration_sec}</run_duration_sec>\n"
            f"  <random_seed>{scenario.random_seed}</random_seed>\n"
            "</scenario_definition>\n"
        )
        destination = self.config.generated_dir / scenario.scenario_file_name
        FileManager.ensure_dir(destination.parent)
        destination.write_text(content, encoding="utf-8")

    @staticmethod
    def _format_id(prefix: str, number: int, digits: int) -> str:
        """Format an incrementing integer into a zero-padded ID, e.g. S0001."""
        return f"{prefix}{number:0{digits}d}"
