"""
GreenAeroTester Dashboard - Shared Utilities
==============================================
Centralized data loading, caching, and validation helpers used by every
page in the dashboard. Designed to fail gracefully: if a backend file does
not exist yet (because Intern 1 / Intern 3 haven't generated it), pages
should still load and show a clear "data not available yet" message
instead of crashing.

Place this file at: web/utils.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
# web/utils.py -> project root is one level up from web/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIRS = {
    "raw": PROJECT_ROOT / "data" / "raw",
    "processed": PROJECT_ROOT / "data" / "processed",
    "final": PROJECT_ROOT / "data" / "final",
}

RESULTS_DIRS = {
    "figures": PROJECT_ROOT / "results" / "figures",
    "tables": PROJECT_ROOT / "results" / "tables",
    "reports": PROJECT_ROOT / "results" / "reports",
}

# Canonical dataset files expected from the backend / hardware pipelines.
# Search order: final -> processed -> raw (most refined first).
DATASET_FILES = {
    "test_catalog": "test_catalog.csv",
    "scenario_parameters": "scenario_parameters.csv",
    "test_runs": "test_runs.csv",
    "software_energy_metrics": "software_energy_metrics.csv",
    "hardware_energy_metrics": "hardware_energy_metrics.csv",
    "merged_energy_metrics": "merged_energy_metrics.csv",
    "assurance_features": "assurance_features.csv",
    "prioritization_decisions": "prioritization_decisions.csv",
    "baseline_comparison": "baseline_comparison.csv",
    "environment_metadata": "environment_metadata.csv",
}

SEARCH_ORDER = ["final", "processed", "raw"]


def find_dataset_path(key: str) -> Optional[Path]:
    """Return the first existing path for a known dataset key, searching
    final -> processed -> raw. Returns None if not found anywhere."""
    filename = DATASET_FILES.get(key)
    if filename is None:
        return None
    for stage in SEARCH_ORDER:
        candidate = DATA_DIRS[stage] / filename
        if candidate.exists():
            return candidate
    return None


@st.cache_data(show_spinner=False)
def load_dataset(key: str) -> Optional[pd.DataFrame]:
    """Load a known dataset by key. Returns None (not an exception) if the
    file does not exist yet, so calling pages can render a friendly
    placeholder instead of crashing the app."""
    path = find_dataset_path(key)
    if path is None:
        return None
    try:
        df = pd.read_csv(path)
        return df
    except Exception as exc:  # noqa: BLE001 - surface any parse error to UI
        st.session_state.setdefault("load_errors", []).append(
            f"Failed to read {path.name}: {exc}"
        )
        return None


def missing_data_notice(key: str, page_name: str = "this page") -> None:
    """Render a consistent, friendly notice when a dataset is missing."""
    filename = DATASET_FILES.get(key, key)
    st.info(
        f"**{filename}** has not been generated yet, so {page_name} cannot "
        f"display real data. This file is expected in one of:\n\n"
        f"- `data/final/{filename}`\n"
        f"- `data/processed/{filename}`\n"
        f"- `data/raw/{filename}`\n\n"
        f"Once the backend / hardware pipeline produces it, this page will "
        f"populate automatically on refresh."
    )


def safe_value(value, fmt: str = "{:.2f}", default: str = "—") -> str:
    """Format a numeric value safely, returning a placeholder for NaN/None."""
    if value is None or pd.isna(value):
        return default
    try:
        return fmt.format(value)
    except (ValueError, TypeError):
        return str(value)


def clean_run_summary(test_runs: Optional[pd.DataFrame]) -> dict:
    """Compute run-status counts (clean / failed / timeout / crashed) from
    a test_runs dataframe. Expects a 'result_status' column if present;
    falls back gracefully if the column is absent or the df is None."""
    summary = {"total": 0, "clean": 0, "failed": 0, "timeout": 0, "crashed": 0, "other": 0}
    if test_runs is None or test_runs.empty:
        return summary

    summary["total"] = len(test_runs)
    status_col = None
    for candidate in ("result_status", "status", "run_status"):
        if candidate in test_runs.columns:
            status_col = candidate
            break

    if status_col is None:
        return summary

    statuses = test_runs[status_col].astype(str).str.lower().str.strip()
    summary["clean"] = int((statuses == "clean").sum() + (statuses == "pass").sum() + (statuses == "success").sum())
    summary["failed"] = int((statuses == "failed").sum() + (statuses == "fail").sum())
    summary["timeout"] = int((statuses == "timeout").sum())
    summary["crashed"] = int((statuses == "crashed").sum() + (statuses == "crash").sum())
    known = summary["clean"] + summary["failed"] + summary["timeout"] + summary["crashed"]
    summary["other"] = summary["total"] - known
    return summary


def get_load_errors() -> list[str]:
    return st.session_state.get("load_errors", [])
