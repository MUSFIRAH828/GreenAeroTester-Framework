"""
prioritize.py  ─  GreenAeroTest Prototype  ─  v1.0
===================================================
Reads dataset/simulation_energy_dataset.csv (produced by run_pilot.py),
computes per-test average energy, calculates a utility score for each
optional test, applies the mandatory-first prioritization rule, writes
dataset/priority_order.csv, and saves dataset/energy_per_test.png.

Prioritization rule:
    1. All mandatory tests (mandatory_flag == 1) are selected first,
       ordered by descending assurance_score.
    2. Optional tests (mandatory_flag == 0) follow, ordered by
       descending utility_score = assurance_score / avg_energy_wh.

Usage:
    python prioritize.py
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")           # non-interactive backend — no display needed
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────────────────
DATASET_CSV      = os.path.join("dataset", "simulation_energy_dataset.csv")
SCENARIOS_CSV    = "scenarios.csv"
PRIORITY_CSV     = os.path.join("dataset", "priority_order.csv")
ENERGY_CHART_PNG = os.path.join("dataset", "energy_per_test.png")

# Output column order for priority_order.csv
PRIORITY_COLS = [
    "priority_rank",
    "test_id",
    "scenario_name",
    "mandatory_flag",
    "assurance_score",
    "avg_energy_wh",
    "avg_energy_joules",
    "avg_runtime_sec",
    "avg_cpu_percent",
    "avg_carbon_gco2",
    # ── CodeCarbon columns (real hardware-based measurement) ────────────────
    "avg_cc_duration_sec",
    "avg_cc_energy_kwh",
    "avg_cc_emissions_kgco2",
    "utility_score",
    "total_runs",
    "clean_runs",
    "timeout_runs",
    "selection_reason",
]


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — LOAD DATA
# ──────────────────────────────────────────────────────────────────────────────

def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (dataset_df, scenarios_df) or exit with a clear error."""
    if not os.path.exists(DATASET_CSV):
        sys.exit(
            f"[ERROR] {DATASET_CSV} not found.\n"
            "        Run  python run_pilot.py  first to generate it."
        )
    if not os.path.exists(SCENARIOS_CSV):
        sys.exit(f"[ERROR] {SCENARIOS_CSV} not found.")

    dataset_df   = pd.read_csv(DATASET_CSV)
    scenarios_df = pd.read_csv(SCENARIOS_CSV)

    print(f"[LOAD] {len(dataset_df)} rows from {DATASET_CSV}")
    print(f"       {len(scenarios_df)} scenarios from {SCENARIOS_CSV}")
    return dataset_df, scenarios_df


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — AGGREGATE PER TEST
# ──────────────────────────────────────────────────────────────────────────────

def aggregate(dataset_df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by test_id, compute average / count columns.
    'Clean' runs are those where result == 'pass'.
    Energy averages prefer clean runs; fall back to all runs if none exist.
    """
    # CodeCarbon columns are new — if an older dataset.csv was generated
    # before this integration, these columns won't exist yet. Fall back to
    # 0.0 in that case instead of crashing, so the prototype still runs.
    has_codecarbon = {"cc_duration_sec", "cc_energy_kwh", "cc_emissions_kgco2"}.issubset(dataset_df.columns)
    if not has_codecarbon:
        print(
            "[WARN] No CodeCarbon columns found in the dataset (cc_duration_sec, "
            "cc_energy_kwh, cc_emissions_kgco2).\n"
            "       Re-run  python run_pilot.py  to regenerate the dataset with "
            "CodeCarbon tracking. Using 0.0 placeholders for now."
        )

    rows = []
    for test_id, grp in dataset_df.groupby("test_id"):
        clean  = grp[grp["result"] == "pass"]
        energy_src = clean if not clean.empty else grp   # prefer clean runs

        rows.append({
            "test_id"           : test_id,
            "scenario_name"     : grp["scenario_name"].iloc[0],
            "avg_energy_wh"     : energy_src["energy_wh"].mean(),
            "avg_energy_joules" : energy_src["energy_joules"].mean(),
            "avg_runtime_sec"   : grp["runtime_sec"].mean(),
            "avg_cpu_percent"   : grp["avg_cpu_percent"].mean(),
            "avg_carbon_gco2"   : energy_src["carbon_gco2"].mean(),
            # ── CodeCarbon real-world metrics ────────────────────────────────
            "avg_cc_duration_sec"   : energy_src["cc_duration_sec"].mean() if has_codecarbon else 0.0,
            "avg_cc_energy_kwh"     : energy_src["cc_energy_kwh"].mean() if has_codecarbon else 0.0,
            "avg_cc_emissions_kgco2": energy_src["cc_emissions_kgco2"].mean() if has_codecarbon else 0.0,
            "total_runs"        : len(grp),
            "clean_runs"        : len(clean),
            "timeout_runs"      : (grp["result"] == "timeout").sum(),
        })

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 — MERGE SCENARIO METADATA & COMPUTE UTILITY SCORE
# ──────────────────────────────────────────────────────────────────────────────

def enrich(agg_df: pd.DataFrame, scenarios_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge mandatory_flag and assurance_score from scenarios.csv,
    then compute utility_score = assurance_score / avg_energy_wh.

    If avg_energy_wh is 0 (e.g. all runs were instant or incomplete),
    utility_score is set to 0 to avoid division-by-zero.
    """
    meta = scenarios_df[["test_id", "mandatory_flag", "assurance_score"]]
    merged = agg_df.merge(meta, on="test_id", how="left")

    merged["utility_score"] = merged.apply(
        lambda r: (r["assurance_score"] / r["avg_energy_wh"])
                  if r["avg_energy_wh"] > 0 else 0.0,
        axis=1,
    )
    return merged


# ──────────────────────────────────────────────────────────────────────────────
# STEP 4 — APPLY PRIORITIZATION RULE
# ──────────────────────────────────────────────────────────────────────────────

def prioritize(merged_df: pd.DataFrame) -> pd.DataFrame:
    """
    Rule:
        mandatory tests first  → sorted by assurance_score DESC
        optional tests second  → sorted by utility_score DESC

    Returns a DataFrame with a 'priority_rank' column (1 = highest priority)
    and a 'selection_reason' column.
    """
    mandatory = (
        merged_df[merged_df["mandatory_flag"] == 1]
        .copy()
        .sort_values("assurance_score", ascending=False)
    )
    mandatory["selection_reason"] = "mandatory"

    optional = (
        merged_df[merged_df["mandatory_flag"] == 0]
        .copy()
        .sort_values("utility_score", ascending=False)
    )
    optional["selection_reason"] = "utility_score"

    ranked = pd.concat([mandatory, optional], ignore_index=True)
    ranked.insert(0, "priority_rank", range(1, len(ranked) + 1))
    return ranked


# ──────────────────────────────────────────────────────────────────────────────
# STEP 5 — SAVE priority_order.csv
# ──────────────────────────────────────────────────────────────────────────────

def save_priority(ranked_df: pd.DataFrame):
    """Round float columns and write priority_order.csv."""
    out = ranked_df.copy()

    rounding = {
        "avg_energy_wh"    : 6,
        "avg_energy_joules": 4,
        "avg_runtime_sec"  : 2,
        "avg_cpu_percent"  : 2,
        "avg_carbon_gco2"  : 6,
        "avg_cc_duration_sec"    : 4,
        "avg_cc_energy_kwh"      : 8,
        "avg_cc_emissions_kgco2" : 8,
        "utility_score"    : 4,
    }
    for col, dp in rounding.items():
        if col in out.columns:
            out[col] = out[col].round(dp)

    # Keep only the defined output columns (drop extras if any)
    existing_cols = [c for c in PRIORITY_COLS if c in out.columns]
    try:
        out[existing_cols].to_csv(PRIORITY_CSV, index=False)
    except PermissionError:
        sys.exit(
            f"\n[ERROR] Could not write {PRIORITY_CSV} — permission denied.\n"
            f"        This almost always means the file is currently open in\n"
            f"        Excel (or another program). Close it and run this script again.\n"
            f"        If it's not open anywhere, check that the 'dataset' folder\n"
            f"        isn't marked read-only, or try running the terminal as Administrator."
        )
    print(f"\n[SAVED] {PRIORITY_CSV}")
    print(out[existing_cols].to_string(index=False))


# ──────────────────────────────────────────────────────────────────────────────
# STEP 6 — GENERATE energy_per_test.png
# ──────────────────────────────────────────────────────────────────────────────

def generate_chart(ranked_df: pd.DataFrame):
    """
    Four-panel dashboard (2x2 grid):
        Top-left     — average PC energy (Wh, psutil-based estimate) per test.
        Top-right    — utility score per test with priority rank annotated.
        Bottom-left  — CodeCarbon energy used (kWh, real hardware measurement).
        Bottom-right — CodeCarbon CO2 emissions (kg), with execution time
                        (seconds) annotated on each bar.
    Red bars = mandatory tests.  Blue bars = optional tests.
    """
    labels       = ranked_df["test_id"].tolist()
    energies     = ranked_df["avg_energy_wh"].tolist()
    utilities    = ranked_df["utility_score"].tolist()
    mandatory    = ranked_df["mandatory_flag"].tolist()
    ranks        = ranked_df["priority_rank"].tolist()
    cc_energy    = ranked_df["avg_cc_energy_kwh"].tolist()
    cc_emissions = ranked_df["avg_cc_emissions_kgco2"].tolist()
    cc_duration  = ranked_df["avg_cc_duration_sec"].tolist()

    colors = ["#d62728" if m else "#1f77b4" for m in mandatory]

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(13, 10))
    fig.suptitle(
        "GreenAeroTest Prototype  —  Energy, CO\u2082 & Priority Overview\n"
        "(top row: PC simulation estimate  |  bottom row: CodeCarbon real-hardware measurement)",
        fontsize=12, fontweight="bold",
    )

    # ── Left panel: average energy per test ──────────────────────────────────
    bars1 = ax1.bar(labels, energies, color=colors, edgecolor="black", linewidth=0.8)
    ax1.set_xlabel("Test ID", fontsize=11)
    ax1.set_ylabel("Average Energy (Wh)", fontsize=11)
    ax1.set_title("Average PC Energy per Test", fontsize=11)
    ax1.grid(axis="y", linestyle="--", alpha=0.45)
    ax1.set_ylim(0, max(energies) * 1.20 if energies else 1)

    for bar, val in zip(bars1, energies):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(energies) * 0.015,
            f"{val:.4f} Wh",
            ha="center", va="bottom", fontsize=8,
        )

    # ── Right panel: utility score with rank label ────────────────────────────
    bars2 = ax2.bar(labels, utilities, color=colors, edgecolor="black", linewidth=0.8)
    ax2.set_xlabel("Test ID", fontsize=11)
    ax2.set_ylabel("Utility Score  (assurance / avg_energy_wh)", fontsize=11)
    ax2.set_title("Utility Score & Priority Rank", fontsize=11)
    ax2.grid(axis="y", linestyle="--", alpha=0.45)
    ax2.set_ylim(0, max(utilities) * 1.20 if utilities else 1)

    for bar, rank, util in zip(bars2, ranks, utilities):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(utilities) * 0.015,
            f"Rank #{rank}\n{util:.2f}",
            ha="center", va="bottom", fontsize=8,
        )

    # ── Bottom-left panel: CodeCarbon energy used (kWh) ──────────────────────
    bars3 = ax3.bar(labels, cc_energy, color=colors, edgecolor="black", linewidth=0.8)
    ax3.set_xlabel("Test ID", fontsize=11)
    ax3.set_ylabel("Energy Used — CodeCarbon (kWh)", fontsize=11)
    ax3.set_title("Real Hardware Energy Used per Test (CodeCarbon)", fontsize=11)
    ax3.grid(axis="y", linestyle="--", alpha=0.45)
    max_cc_energy = max(cc_energy) if cc_energy and max(cc_energy) > 0 else 1
    ax3.set_ylim(0, max_cc_energy * 1.20)

    for bar, val in zip(bars3, cc_energy):
        ax3.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_cc_energy * 0.015,
            f"{val:.6f}",
            ha="center", va="bottom", fontsize=8,
        )

    # ── Bottom-right panel: CodeCarbon CO2 emissions, with exec time labels ──
    bars4 = ax4.bar(labels, cc_emissions, color=colors, edgecolor="black", linewidth=0.8)
    ax4.set_xlabel("Test ID", fontsize=11)
    ax4.set_ylabel("CO\u2082 Emissions — CodeCarbon (kg)", fontsize=11)
    ax4.set_title("CO\u2082 Emissions per Test  (label = execution time)", fontsize=11)
    ax4.grid(axis="y", linestyle="--", alpha=0.45)
    max_cc_emissions = max(cc_emissions) if cc_emissions and max(cc_emissions) > 0 else 1
    ax4.set_ylim(0, max_cc_emissions * 1.20)

    for bar, val, dur in zip(bars4, cc_emissions, cc_duration):
        ax4.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_cc_emissions * 0.015,
            f"{val:.6f} kg\n{dur:.1f}s",
            ha="center", va="bottom", fontsize=8,
        )

    # ── Shared legend ─────────────────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(color="#d62728", label="Mandatory test (always selected)"),
        mpatches.Patch(color="#1f77b4", label="Optional test (ranked by utility)"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=2,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.0),
    )

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    try:
        plt.savefig(ENERGY_CHART_PNG, dpi=150, bbox_inches="tight")
    except PermissionError:
        plt.close()
        sys.exit(
            f"\n[ERROR] Could not write {ENERGY_CHART_PNG} — permission denied.\n"
            f"        This almost always means the image is currently open in\n"
            f"        Photos, Paint, or another viewer. Close it and run this script again."
        )
    plt.close()
    print(f"[CHART] {ENERGY_CHART_PNG}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  GreenAeroTest  ─  prioritize.py  ─  v1.0")
    print("=" * 60)

    dataset_df, scenarios_df = load_data()

    # Basic sanity check
    if dataset_df.empty:
        sys.exit("[ERROR] Dataset is empty — no runs to prioritize.")

    print(f"\n  Results breakdown:")
    print(dataset_df["result"].value_counts().to_string())

    agg_df    = aggregate(dataset_df)
    merged_df = enrich(agg_df, scenarios_df)
    ranked_df = prioritize(merged_df)

    os.makedirs("dataset", exist_ok=True)
    save_priority(ranked_df)
    generate_chart(ranked_df)

    print("\n[DONE] Prioritization complete.")
    print(f"       {PRIORITY_CSV}")
    print(f"       {ENERGY_CHART_PNG}")


if __name__ == "__main__":
    main()