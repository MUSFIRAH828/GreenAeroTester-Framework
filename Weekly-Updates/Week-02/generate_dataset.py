"""
Generates frontend_dataset.csv — ONE CSV, ~100 rows (one row per Test ID),
built entirely from backend outputs already present in this folder.

No backend algorithm is rerun. Every value is either:
  (a) taken directly from a backend CSV, or
  (b) aggregated (median/mode/majority-vote) from run-level backend CSVs up
      to test-level, or
  (c) a straightforward, documented unit/label conversion of a backend value
      (e.g. a 0-1 fraction -> 0-100 scale, or a DAL bucket derived from a
      backend safety-criticality score).
Nothing is randomly generated.
"""
import re
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Load backend outputs
# ---------------------------------------------------------------------------
test_catalog   = pd.read_csv("test_catalog.csv")
test_runs      = pd.read_csv("test_runs_clean.csv")
energy_metrics = pd.read_csv("energy_metrics_clean.csv")
run_outliers   = pd.read_csv("run_outliers.csv")           # has test_id, links energy_metrics -> test
assurance      = pd.read_csv("assurance_features.csv")
test_stats     = pd.read_csv("test_statistics.csv")
prioritization = pd.read_csv("prioritization_decisions.csv")

# ---------------------------------------------------------------------------
# 1) Bring test_id onto energy_metrics_clean (it only has run_id/scenario_id)
#    via run_outliers, which already carries run_id -> test_id.
# ---------------------------------------------------------------------------
energy_with_test = energy_metrics.merge(
    run_outliers[["run_id", "test_id"]], on="run_id", how="left"
)

# ---------------------------------------------------------------------------
# 2) Run-level -> test-level aggregation (median for numeric energy/power/cpu
#    fields, majority vote for the categorical run status). This is the ONLY
#    aggregation step; it mirrors the same "median per test" methodology the
#    backend already used in test_statistics.csv.
# ---------------------------------------------------------------------------
energy_agg = energy_with_test.groupby("test_id").agg(
    software_energy_wh=("energy_wh", "median"),
    avg_power_w=("avg_power_watts", "median"),
    cpu_usage=("avg_cpu_percent", "median"),
).reset_index()

RESULT_TO_STATUS = {"pass": "Clean", "fail": "Failed", "timeout": "Timeout"}
test_runs["status_mapped"] = test_runs["result"].map(RESULT_TO_STATUS).fillna("Failed")

def majority_status(s):
    return s.value_counts().idxmax()

status_agg = test_runs.groupby("test_id")["status_mapped"].apply(majority_status).rename("status")

# Representative run per test = the run whose runtime is closest to the
# test's own median runtime (a real backend run, not a fabricated one) —
# used to supply a valid, unique run_id + timestamp per test row.
runtime_median_by_test = test_runs.groupby("test_id")["runtime_sec"].median().rename("_median_rt")
tr = test_runs.merge(runtime_median_by_test, on="test_id")
tr["_dist"] = (tr["runtime_sec"] - tr["_median_rt"]).abs()
representative_run = (
    tr.sort_values("_dist")
      .groupby("test_id")
      .first()[["run_id", "start_time"]]
      .rename(columns={"run_id": "run_id_rep", "start_time": "timestamp"})
)

# ---------------------------------------------------------------------------
# 3) Mandatory + carbon are already computed per test_id by the backend
#    (prioritization_decisions.csv) and are identical across all 6
#    algorithms for the same test_id (verified), so any single algorithm's
#    rows can be used as the per-test lookup without recomputing anything.
# ---------------------------------------------------------------------------
prio_by_test = (
    prioritization.drop_duplicates(subset="test_id")
    .set_index("test_id")[["mandatory", "median_carbon_gco2"]]
    .rename(columns={"median_carbon_gco2": "carbon_gco2"})
)

# ---------------------------------------------------------------------------
# 4) Fault type — extracted from test_catalog's free-text description
#    (backend already encodes the specific fault subtype there).
# ---------------------------------------------------------------------------
def extract_fault(desc):
    m = re.search(r"fault:\s*([^)]+)\)", str(desc))
    return m.group(1).strip() if m else "None"

test_catalog = test_catalog.copy()
test_catalog["fault_type"] = test_catalog["description"].apply(extract_fault)

# ---------------------------------------------------------------------------
# 5) Assurance sub-component columns, rescaled from the backend's 0-1 scale
#    to the 0-100 scale the Assurance page's labels expect
#    ("Safety Criticality (0-100)", etc.) — a unit conversion only.
# ---------------------------------------------------------------------------
assurance = assurance.copy()
assurance["safety_criticality"]      = assurance["safety_score"] * 100
assurance["requirement_coverage"]    = assurance["requirement_coverage_score"] * 100
assurance["fault_history"]           = assurance["fault_history_score"] * 100
assurance["recent_change_relevance"] = assurance["change_relevance_score"] * 100
assurance["novelty"]                 = assurance["novelty_score"] * 100
assurance["flakiness"]               = assurance["flakiness_penalty"] * 100
assurance["certification_relevance"] = assurance["certification_relevance_score"] * 100

def safety_bucket(v):
    if pd.isna(v):
        return np.nan
    if v >= 85:
        return "DAL-A"
    if v >= 65:
        return "DAL-B"
    if v >= 45:
        return "DAL-C"
    return "DAL-D"

assurance["safety_level"] = assurance["safety_criticality"].apply(safety_bucket)

# ---------------------------------------------------------------------------
# 6) Assemble the one-row-per-test table.
# ---------------------------------------------------------------------------
base = test_catalog[["test_id", "scenario_id", "flight_phase_name", "weather_name", "fault_type"]].rename(
    columns={"flight_phase_name": "flight_phase", "weather_name": "weather_condition"}
)

df = (
    base
    .merge(test_stats[["test_id", "median_runtime_sec"]], on="test_id", how="left")
    .rename(columns={"median_runtime_sec": "runtime_s"})
    .merge(energy_agg, on="test_id", how="left")
    .merge(status_agg, on="test_id", how="left")
    .merge(representative_run, on="test_id", how="left")
    .merge(prio_by_test, on="test_id", how="left")
    .merge(
        assurance[[
            "test_id", "assurance_score", "safety_level", "safety_criticality",
            "requirement_coverage", "fault_history", "recent_change_relevance",
            "novelty", "flakiness", "certification_relevance",
        ]],
        on="test_id", how="left",
    )
)

df = df.rename(columns={"run_id_rep": "run_id"})

# Column order: required first, then optional groups in the order pages need them.
ordered_cols = [
    "run_id", "scenario_id", "test_id", "runtime_s", "software_energy_wh",
    "status", "flight_phase", "weather_condition", "fault_type",
    "mandatory", "safety_level", "assurance_score", "timestamp",
    "avg_power_w", "carbon_gco2", "cpu_usage",
    "safety_criticality", "requirement_coverage", "fault_history",
    "recent_change_relevance", "novelty", "flakiness", "certification_relevance",
]
df = df[ordered_cols]

# Round for readability without touching underlying precision materially.
round_map = {
    "runtime_s": 3, "software_energy_wh": 6, "assurance_score": 2,
    "avg_power_w": 3, "carbon_gco2": 6, "cpu_usage": 2,
    "safety_criticality": 1, "requirement_coverage": 1, "fault_history": 1,
    "recent_change_relevance": 1, "novelty": 1, "flakiness": 3, "certification_relevance": 1,
}
for c, d in round_map.items():
    df[c] = df[c].round(d)

# ---------------------------------------------------------------------------
# Sanity checks before writing
# ---------------------------------------------------------------------------
assert df["test_id"].is_unique, "test_id must be unique (one row per test)"
assert df["run_id"].is_unique, "run_id must be unique (validator checks duplicates)"
assert df["scenario_id"].is_unique, "scenario_id must be unique per test in this 1:1 dataset"
assert df.shape[0] == 100, f"expected 100 rows, got {df.shape[0]}"
assert df[["run_id", "scenario_id", "runtime_s", "software_energy_wh"]].notna().all().all(), \
    "required columns must have no missing values"

df.to_csv("frontend_dataset.csv", index=False)
print("Wrote frontend_dataset.csv:", df.shape)
print(df.head(3).to_string())
print()
print("Null counts per column:")
print(df.isna().sum())