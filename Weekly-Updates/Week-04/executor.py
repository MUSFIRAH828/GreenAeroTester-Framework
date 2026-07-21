"""
executor.py
-----------
Responsible for launching a single FlightGear scenario run via
scripts/run_scenario.ps1, waiting for it to finish (respecting a hard
timeout), and returning a structured ExecutionResult describing the
outcome (pass / fail / timeout / crash / incomplete).
"""

from __future__ import annotations

import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import Config

logger = logging.getLogger(__name__)

VALID_RESULTS = {"pass", "fail", "timeout", "crash", "incomplete"}


@dataclass
class ScenarioDefinition:
    """Parsed content of a scenario XML file."""

    scenario_id: str
    test_id: str
    aircraft_id: str
    airport: str
    runway: str
    fdm: str
    duration_sec: int
    wind_dir_deg: float
    wind_speed_kt: float
    visibility_m: float
    scenario_file_path: Path


@dataclass
class ExecutionResult:
    """Outcome of a single scenario execution attempt."""

    run_id: str
    test_id: str
    scenario_id: str
    run_no: int
    attempt_no: int
    execution_block: int
    start_time: str
    end_time: str
    runtime_sec: float
    result: str
    return_code: Optional[int]
    timeout_flag: bool
    output_csv: str
    log_file: str
    environment_id: str
    random_seed: int


class ScenarioLoadError(Exception):
    """Raised when a scenario XML file cannot be parsed or is malformed."""


class ScenarioExecutor:
    """Launches FlightGear scenario runs and classifies their outcome."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def load_scenario(self, scenario_id: str, scenario_file_name: str) -> ScenarioDefinition:
        """Parse a scenario XML file into a ScenarioDefinition.

        Raises:
            ScenarioLoadError: if the file is missing or malformed.
        """
        scenario_path = self._config.scenarios_dir / scenario_file_name
        if not scenario_path.exists():
            raise ScenarioLoadError(f"Scenario file not found: {scenario_path}")

        try:
            tree = ET.parse(scenario_path)
            root = tree.getroot()

            meta = root.find("meta")
            aircraft = root.find("aircraft")
            initial_conditions = root.find("initial_conditions")
            run_parameters = root.find("run_parameters")
            environment = root.find("environment")

            if (
                meta is None
                or aircraft is None
                or initial_conditions is None
                or run_parameters is None
                or environment is None
            ):
                raise ScenarioLoadError(
                    f"Scenario file {scenario_path} is missing required sections."
                )

            test_id = meta.findtext("test_id")
            aircraft_id = aircraft.findtext("aircraft_id")
            fdm = aircraft.findtext("fdm", default=self._config.fdm)
            airport = initial_conditions.findtext("airport")
            runway = initial_conditions.findtext("runway")
            duration_text = run_parameters.findtext("duration_sec")
            wind_dir_text = environment.findtext("wind_dir_deg")
            wind_speed_text = environment.findtext("wind_speed_kt")
            visibility_text = environment.findtext("visibility_m")

            if not all([test_id, aircraft_id, airport, runway, duration_text]):
                raise ScenarioLoadError(
                    f"Scenario file {scenario_path} has missing required fields."
                )
            if not all([wind_dir_text, wind_speed_text, visibility_text]):
                raise ScenarioLoadError(
                    f"Scenario file {scenario_path} is missing required environment fields."
                )

            return ScenarioDefinition(
                scenario_id=scenario_id,
                test_id=test_id,
                aircraft_id=aircraft_id,
                airport=airport,
                runway=runway,
                fdm=fdm,
                duration_sec=int(duration_text),
                wind_dir_deg=float(wind_dir_text),
                wind_speed_kt=float(wind_speed_text),
                visibility_m=float(visibility_text),
                scenario_file_path=scenario_path,
            )
        except ET.ParseError as exc:
            raise ScenarioLoadError(f"Failed to parse {scenario_path}: {exc}") from exc

    def execute(
        self,
        scenario: ScenarioDefinition,
        run_id: str,
        run_no: int,
        attempt_no: int,
        execution_block: int,
    ) -> ExecutionResult:
        """Run one scenario execution attempt and return its result.

        Handles PowerShell/FlightGear timeouts, non-zero exits, malformed
        output, and unexpected exceptions gracefully. This method never
        raises for expected failure modes; the outcome is always encoded
        in the returned ExecutionResult.result field.
        """
        log_file = self._config.logs_dir / f"{scenario.test_id}_{run_id}.log"
        flight_csv = self._config.flight_csv_dir / f"{scenario.test_id}_{run_id}.csv"

        start_dt = datetime.now(timezone.utc)
        result_status = "incomplete"
        return_code: Optional[int] = None
        timeout_flag = False

        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self._config.run_scenario_script_path),
            "-FlightGearExe",
            self._config.flightgear_exe_path,
            "-ScenarioFile",
            str(scenario.scenario_file_path),
            "-AircraftId",
            scenario.aircraft_id,
            "-Airport",
            scenario.airport,
            "-Runway",
            scenario.runway,
            "-Fdm",
            scenario.fdm,
            "-WindDirDeg",
            str(scenario.wind_dir_deg),
            "-WindSpeedKt",
            str(scenario.wind_speed_kt),
            "-VisibilityM",
            str(scenario.visibility_m),
            "-DurationSec",
            str(scenario.duration_sec),
            "-LogFile",
            str(log_file),
            "-FlightCsvFile",
            str(flight_csv),
        ]

        logger.info(
            "Starting run_id=%s test_id=%s scenario_id=%s attempt=%s",
            run_id,
            scenario.test_id,
            scenario.scenario_id,
            attempt_no,
        )

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._config.timeout_sec,
                check=False,
            )
            return_code = completed.returncode
            result_status = self._classify_result(completed.returncode, completed.stdout)

        except subprocess.TimeoutExpired:
            logger.warning("run_id=%s timed out after %ss", run_id, self._config.timeout_sec)
            result_status = "timeout"
            timeout_flag = True
            return_code = None

        except FileNotFoundError as exc:
            # powershell.exe itself (or the runner script) could not be found.
            logger.error("run_id=%s crashed: %s", run_id, exc)
            self._append_crash_note(log_file, str(exc))
            result_status = "crash"
            return_code = None

        except OSError as exc:
            logger.error("run_id=%s crashed with OS error: %s", run_id, exc)
            self._append_crash_note(log_file, str(exc))
            result_status = "crash"
            return_code = None

        except Exception as exc:  # noqa: BLE001 - must always yield a classified result
            logger.exception("run_id=%s hit an unexpected exception", run_id)
            self._append_crash_note(log_file, f"Unexpected exception: {exc}")
            result_status = "crash"
            return_code = None

        end_dt = datetime.now(timezone.utc)
        runtime_sec = max(0.0, (end_dt - start_dt).total_seconds())

        return ExecutionResult(
            run_id=run_id,
            test_id=scenario.test_id,
            scenario_id=scenario.scenario_id,
            run_no=run_no,
            attempt_no=attempt_no,
            execution_block=execution_block,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            runtime_sec=round(runtime_sec, 3),
            result=result_status,
            return_code=return_code,
            timeout_flag=timeout_flag,
            output_csv=str(flight_csv),
            log_file=str(log_file),
            environment_id=self._config.environment_id,
            random_seed=self._config.random_seed,
        )

    @staticmethod
    def _classify_result(return_code: int, stdout: str) -> str:
        """Classify a completed (non-timeout) subprocess run as pass/fail/crash/incomplete."""
        json_line = ScenarioExecutor._extract_json_line(stdout)
        if json_line is not None:
            status = json_line.get("status")
            if status in VALID_RESULTS:
                return status

        # No parseable JSON summary from the PowerShell script: fall back
        # to the process return code as the best available signal.
        if return_code == 0:
            return "pass"
        if return_code in (1, 2):
            return "crash"
        return "incomplete"

    @staticmethod
    def _extract_json_line(stdout: str) -> Optional[dict]:
        if not stdout:
            return None
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _append_crash_note(log_file: Path, message: str) -> None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a", encoding="utf-8") as fh:
                fh.write(f"[{datetime.now(timezone.utc).isoformat()}] EXECUTOR CRASH NOTE: {message}\n")
        except OSError:
            logger.exception("Failed to write crash note to %s", log_file)
