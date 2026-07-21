"""
enums.py
========
Enumerations shared across the GreenAeroTest backend.

These enums encode the fixed taxonomy defined in the Dataset Implementation
Specification (Section 3): 10 flight phases, 5 weather profiles, and 2
system modes. Keeping them as enums (rather than raw strings scattered
through the codebase) gives us:

- A single source of truth for valid codes.
- IDE/type-checker support (typos become errors, not silent bugs).
- Safe iteration when generating the 10 x 5 x 2 scenario matrix.

Phase 2+ modules (executor, energy collector, validators, etc.) will import
these same enums so that "flight phase" or "system mode" is never
represented as an ad-hoc string in more than one place.
"""

from __future__ import annotations

from enum import Enum


class FlightPhase(str, Enum):
    """The 10 flight phases used to build the scenario matrix (Spec 3.1)."""

    TAKEOFF = "P01"
    CLIMB = "P02"
    CRUISE = "P03"
    TURN_MANEUVER = "P04"
    DESCENT = "P05"
    APPROACH = "P06"
    LANDING = "P07"
    GO_AROUND = "P08"
    HOLDING_LOITER = "P09"
    EMERGENCY_LANDING = "P10"


class WeatherProfile(str, Enum):
    """The 5 weather profiles used to build the scenario matrix (Spec 3.2)."""

    CALM = "W01"
    LIGHT_WIND = "W02"
    CROSSWIND = "W03"
    GUST_TURBULENCE = "W04"
    LOW_VISIBILITY_RAIN = "W05"


class SystemMode(str, Enum):
    """The 2 system modes used to build the scenario matrix (Spec 3.3)."""

    NOMINAL = "M0"
    FAULTED = "M1"


class RunResult(str, Enum):
    """
    Possible outcomes of a single execution attempt (Spec 5.1).

    Not used for execution in Phase 1, but defined here now so that the
    `Scenario`/future `Run` models and the executor built in Phase 2 share
    a single, consistent vocabulary of outcomes from the very start.
    """

    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    CRASH = "crash"
    INCOMPLETE = "incomplete"
