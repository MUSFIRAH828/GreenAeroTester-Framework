"""
constants.py
============
Static, spec-derived lookup tables and counting rules.

Everything here is copied directly from the Dataset Implementation
Specification and is intentionally NOT configurable at runtime (unlike
`settings.py`, which holds paths and environment-specific values). If the
underlying taxonomy of the project ever changes, it changes here and
nowhere else.
"""

from __future__ import annotations

from typing import Final, NamedTuple

from models.enums import FlightPhase, SystemMode, WeatherProfile


class FlightPhaseInfo(NamedTuple):
    """Static metadata for one flight phase row (Spec 3.1)."""

    code: FlightPhase
    display_name: str
    fault_used_in_faulted_mode: str


class WeatherProfileInfo(NamedTuple):
    """Static metadata for one weather profile row (Spec 3.2)."""

    code: WeatherProfile
    display_name: str
    implementation_meaning: str


class SystemModeInfo(NamedTuple):
    """Static metadata for one system mode row (Spec 3.3)."""

    code: SystemMode
    display_name: str
    meaning: str


# ---------------------------------------------------------------------------
# 3.1 Flight Phases
# ---------------------------------------------------------------------------
FLIGHT_PHASES: Final[list[FlightPhaseInfo]] = [
    FlightPhaseInfo(FlightPhase.TAKEOFF, "Takeoff", "Engine response degradation"),
    FlightPhaseInfo(FlightPhase.CLIMB, "Climb", "Elevator/control-surface degradation"),
    FlightPhaseInfo(FlightPhase.CRUISE, "Cruise", "GPS loss or navigation dropout"),
    FlightPhaseInfo(FlightPhase.TURN_MANEUVER, "Turn / maneuver", "Heading or IMU noise"),
    FlightPhaseInfo(FlightPhase.DESCENT, "Descent", "Altimeter bias"),
    FlightPhaseInfo(FlightPhase.APPROACH, "Approach", "Airspeed sensor noise"),
    FlightPhaseInfo(FlightPhase.LANDING, "Landing", "Landing-gear or braking degradation"),
    FlightPhaseInfo(FlightPhase.GO_AROUND, "Go-around", "Throttle response delay"),
    FlightPhaseInfo(FlightPhase.HOLDING_LOITER, "Holding / loiter", "Communication interruption"),
    FlightPhaseInfo(
        FlightPhase.EMERGENCY_LANDING,
        "Emergency landing",
        "Engine degradation with emergency profile",
    ),
]

# ---------------------------------------------------------------------------
# 3.2 Weather Profiles
# ---------------------------------------------------------------------------
WEATHER_PROFILES: Final[list[WeatherProfileInfo]] = [
    WeatherProfileInfo(WeatherProfile.CALM, "Calm", "Low wind, no gust, nominal visibility"),
    WeatherProfileInfo(WeatherProfile.LIGHT_WIND, "Light wind", "Low-to-moderate steady wind"),
    WeatherProfileInfo(
        WeatherProfile.CROSSWIND, "Crosswind", "Directional crosswind appropriate to phase"
    ),
    WeatherProfileInfo(
        WeatherProfile.GUST_TURBULENCE,
        "Gust / turbulence",
        "Moderate gust and turbulence profile",
    ),
    WeatherProfileInfo(
        WeatherProfile.LOW_VISIBILITY_RAIN,
        "Low visibility / rain",
        "Reduced visibility and precipitation setting",
    ),
]

# ---------------------------------------------------------------------------
# 3.3 System Modes
# ---------------------------------------------------------------------------
SYSTEM_MODES: Final[list[SystemModeInfo]] = [
    SystemModeInfo(
        SystemMode.NOMINAL,
        "Nominal",
        "No injected subsystem fault; weather profile still applies.",
    ),
    SystemModeInfo(
        SystemMode.FAULTED,
        "Faulted",
        "Inject the phase-specific fault listed in Section 3.1.",
    ),
]

# ---------------------------------------------------------------------------
# 2.1 Quantitative targets / counting rules
# ---------------------------------------------------------------------------
NUM_FLIGHT_PHASES: Final[int] = len(FLIGHT_PHASES)          # 10
NUM_WEATHER_PROFILES: Final[int] = len(WEATHER_PROFILES)    # 5
NUM_SYSTEM_MODES: Final[int] = len(SYSTEM_MODES)            # 2

TOTAL_SCENARIOS: Final[int] = (
    NUM_FLIGHT_PHASES * NUM_WEATHER_PROFILES * NUM_SYSTEM_MODES
)  # 10 x 5 x 2 = 100

USABLE_REPETITIONS_PER_SCENARIO: Final[int] = 10
TOTAL_CLEAN_RUN_RECORDS: Final[int] = TOTAL_SCENARIOS * USABLE_REPETITIONS_PER_SCENARIO  # 1000
RUN_DURATION_SECONDS: Final[int] = 90

# ---------------------------------------------------------------------------
# 4. ID formats
# ---------------------------------------------------------------------------
SCENARIO_ID_PREFIX: Final[str] = "S"
SCENARIO_ID_DIGITS: Final[int] = 4          # S0001 .. S0100
TEST_ID_PREFIX: Final[str] = "T"
TEST_ID_DIGITS: Final[int] = 4              # T0001 .. T0100
RUN_ID_PREFIX: Final[str] = "R"
RUN_ID_DIGITS: Final[int] = 6               # R000001, R001237, ...
EXPERIMENT_ID_PREFIX: Final[str] = "EXP"
EXPERIMENT_ID_DIGITS: Final[int] = 3        # EXP001
ENVIRONMENT_ID_PREFIX: Final[str] = "ENV"
ENVIRONMENT_ID_DIGITS: Final[int] = 3       # ENV001

# ---------------------------------------------------------------------------
# 3.4 Deterministic generation seed
# ---------------------------------------------------------------------------
# A fixed seed guarantees the 100-scenario catalog can be regenerated
# byte-for-byte identical across machines and runs, satisfying the
# "deterministic ordering and random seed" requirement in Spec 3.4.
SCENARIO_GENERATION_SEED: Final[int] = 42
