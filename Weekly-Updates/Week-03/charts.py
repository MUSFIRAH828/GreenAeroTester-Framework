"""
utils/charts.py
================
Reusable Plotly chart factory for GreenAeroTester.

Every function takes a DataFrame (from :mod:`utils.load_data`) and returns
a ready-to-render ``plotly.graph_objects.Figure``. None of them hardcode
colors or chart type — they all pull from :mod:`utils.theme` via
``get_chart_colors()`` / ``get_chart_type()``, so changing a palette preset
or flipping Dark/Light on the Settings page updates every chart that calls
into this module, everywhere, automatically.

Two categories of chart type are supported (set independently in Settings):

* **Trend charts** (Bar / Line / Area / Scatter) — used for time series and
  numeric distributions: energy, carbon, runtime, CPU, memory.
* **Category charts** (Bar / Pie / Donut) — used for categorical
  breakdowns: status distribution, flight phase, mandatory vs optional.

Adoption note: pages 1-7 currently build charts inline with their own
``go.Figure`` calls (a constraint of an earlier deliverable) and do not yet
call into this module. Any new page — like Settings — or a future refactor
of pages 1-7 can call these functions directly.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.theme import get_chart_colors, get_chart_type, get_theme_colors


def _base_layout(fig: go.Figure, title: str, colors: dict, height: int = 360,
                  xaxis_title: Optional[str] = None, yaxis_title: Optional[str] = None,
                  showlegend: bool = True) -> go.Figure:
    """Applies consistent, theme-aware layout to any figure."""
    theme = get_theme_colors()
    fig.update_layout(
        template=theme["plotly_template"],
        title=dict(text=title, font=dict(color=colors["title"], size=15, family="Space Grotesk, sans-serif")),
        paper_bgcolor=colors["background"] if colors["background"] != "transparent" else "rgba(0,0,0,0)",
        plot_bgcolor=colors["background"] if colors["background"] != "transparent" else "rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=colors["text"], size=12),
        margin=dict(l=10, r=10, t=46, b=10),
        height=height,
        showlegend=showlegend,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=colors["legend"])),
       xaxis=dict(
            title=dict(text=xaxis_title, font=dict(color=colors["axis_label"])),
            gridcolor=colors["grid"], zerolinecolor=colors["grid"],
            color=colors["axis_label"], tickfont=dict(color=colors["axis_label"]),
        ),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(color=colors["axis_label"])),
            gridcolor=colors["grid"], zerolinecolor=colors["grid"],
            color=colors["axis_label"], tickfont=dict(color=colors["axis_label"]),
        ),
    )
    return fig


def _trend_trace(x, y, colors: dict, chart_type: str, name: str = ""):
    """Builds a single trace matching the requested trend chart type."""
    if chart_type == "Bar":
        return go.Bar(x=x, y=y, name=name, marker=dict(color=colors["bar"]))
    if chart_type == "Line":
        return go.Scatter(x=x, y=y, mode="lines", name=name, line=dict(color=colors["line"], width=2.5))
    if chart_type == "Area":
        return go.Scatter(x=x, y=y, mode="lines", name=name, fill="tozeroy",
                           line=dict(color=colors["line"], width=2), fillcolor=colors["area_fill"])
    if chart_type == "Scatter":
        return go.Scattergl(x=x, y=y, mode="markers", name=name,
                             marker=dict(color=colors["bar"], size=6, opacity=0.8))
    raise ValueError(f"Unknown trend chart type: {chart_type}")


def _category_figure(labels, values, colors: dict, chart_type: str, orientation: str = "v") -> go.Figure:
    """Builds a categorical breakdown figure (Bar / Pie / Donut). orientation='h' flips
    a Bar chart to horizontal (labels on y, values on x) — Pie/Donut ignore it."""
    if chart_type == "Bar":
        palette = colors["pie"]
        bar_colors = [palette[i % len(palette)] for i in range(len(labels))]
        if orientation == "h":
            return go.Figure(go.Bar(x=list(values), y=list(labels), orientation="h",
                                     marker=dict(color=bar_colors)))
        return go.Figure(go.Bar(x=list(labels), y=list(values), marker=dict(color=bar_colors)))
    hole = 0.55 if chart_type == "Donut" else 0.0
    return go.Figure(go.Pie(
        labels=list(labels), values=list(values), hole=hole,
        marker=dict(colors=colors["pie"]), textinfo="label+percent", sort=False,
    ))


# ---------------------------------------------------------------------------
# Category charts
# ---------------------------------------------------------------------------
def chart_status_distribution(df: pd.DataFrame, chart_type: Optional[str] = None,
                               colors: Optional[dict] = None) -> go.Figure:
    """Run status breakdown (Clean / Failed / Timeout / Crashed)."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("category")
    counts = df["result"].value_counts()
    fig = _category_figure(counts.index, counts.values, colors, chart_type)
    return _base_layout(fig, "Run Status Distribution", colors, showlegend=(chart_type != "Bar"))


def chart_flight_phase_distribution(df: pd.DataFrame, chart_type: Optional[str] = None,
                                     colors: Optional[dict] = None) -> go.Figure:
    """Scenario/run counts by flight phase."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("category")
    counts = df["flight_phase"].value_counts()
    fig = _category_figure(counts.index, counts.values, colors, chart_type)
    return _base_layout(fig, "Flight Phase Distribution", colors, showlegend=(chart_type != "Bar"))


def chart_mandatory_vs_optional(df: pd.DataFrame, chart_type: Optional[str] = None,
                                 colors: Optional[dict] = None) -> go.Figure:
    """Mandatory vs optional test counts (deduplicated at test level)."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("category")
    per_test = df.drop_duplicates("test_id")
    counts = per_test["mandatory"].map({True: "Mandatory", False: "Optional"}).value_counts()
    fig = _category_figure(counts.index, counts.values, colors, chart_type)
    return _base_layout(fig, "Mandatory vs Optional Tests", colors, showlegend=(chart_type != "Bar"))


def chart_assurance_distribution(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Histogram of per-test assurance scores."""
    colors = colors or get_chart_colors()
    per_test = df.drop_duplicates("test_id")
    fig = go.Figure(go.Histogram(x=per_test["assurance_score"], nbinsx=25, marker=dict(color=colors["bar"])))
    return _base_layout(fig, "Assurance Score Distribution", colors,
                         xaxis_title="Score", yaxis_title="# Tests", showlegend=False)


# ---------------------------------------------------------------------------
# Trend / numeric charts
# ---------------------------------------------------------------------------
def _resample_trend(df: pd.DataFrame, value_col: str, agg: str = "sum", freq: str = "2h") -> pd.Series:
    s = df.set_index("timestamp")[value_col]
    return getattr(s.resample(freq), agg)()


def chart_energy_over_time(df: pd.DataFrame, chart_type: Optional[str] = None,
                            colors: Optional[dict] = None) -> go.Figure:
    """Software energy consumption trend (kWh) over the simulated timeline."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("trend")
    series = _resample_trend(df, "software_energy_wh", "sum") / 1000.0
    fig = go.Figure(_trend_trace(series.index, series.values, colors, chart_type, "Software Energy (kWh)"))
    return _base_layout(fig, "Energy Over Time", colors, yaxis_title="kWh", showlegend=False)


def chart_carbon_analytics(df: pd.DataFrame, chart_type: Optional[str] = None,
                            colors: Optional[dict] = None) -> go.Figure:
    """Carbon emissions trend (kg CO2e), derived consistently from energy."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("trend")
    series = _resample_trend(df, "carbon_emissions_g", "sum") / 1000.0
    fig = go.Figure(_trend_trace(series.index, series.values, colors, chart_type, "Carbon (kg CO2e)"))
    return _base_layout(fig, "Carbon Analytics", colors, yaxis_title="kg CO2e", showlegend=False)


def chart_carbon_by_fault_type(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Carbon emissions grouped by fault type (horizontal bar)."""
    colors = colors or get_chart_colors()
    grouped = (df.groupby("fault_type")["carbon_emissions_g"].sum() / 1000.0).sort_values()
    fig = go.Figure(go.Bar(x=grouped.values, y=grouped.index, orientation="h",
                            marker=dict(color=colors["bar"])))
    return _base_layout(fig, "Carbon Emissions by Fault Type", colors, xaxis_title="kg CO2e", showlegend=False)


def chart_runtime_trend(df: pd.DataFrame, chart_type: Optional[str] = None,
                         colors: Optional[dict] = None) -> go.Figure:
    """Average runtime (seconds) trend over the simulated timeline."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("trend")
    series = _resample_trend(df, "runtime_sec", "mean")
    fig = go.Figure(_trend_trace(series.index, series.values, colors, chart_type, "Avg Runtime (s)"))
    return _base_layout(fig, "Runtime Trend", colors, yaxis_title="Seconds", showlegend=False)


def chart_cpu_usage_trend(df: pd.DataFrame, chart_type: Optional[str] = None,
                           colors: Optional[dict] = None) -> go.Figure:
    """Average CPU usage (%) trend over the simulated timeline."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("trend")
    series = _resample_trend(df, "cpu_usage_pct", "mean")
    fig = go.Figure(_trend_trace(series.index, series.values, colors, chart_type, "Avg CPU (%)"))
    return _base_layout(fig, "CPU Usage Trend", colors, yaxis_title="%", showlegend=False)


def chart_memory_usage_trend(df: pd.DataFrame, chart_type: Optional[str] = None,
                              colors: Optional[dict] = None) -> go.Figure:
    """Average memory usage (MB) trend over the simulated timeline."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("trend")
    series = _resample_trend(df, "memory_usage_mb", "mean")
    fig = go.Figure(_trend_trace(series.index, series.values, colors, chart_type, "Avg Memory (MB)"))
    return _base_layout(fig, "Memory Usage Trend", colors, yaxis_title="MB", showlegend=False)


def chart_energy_distribution(df: pd.DataFrame, chart_type: Optional[str] = None,
                               colors: Optional[dict] = None) -> go.Figure:
    """Per-run software energy distribution, grouped by flight phase (box-style via bar of medians)."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("trend")
    grouped = df.groupby("flight_phase")["software_energy_wh"].median().sort_values()
    fig = go.Figure(_trend_trace(grouped.index, grouped.values, colors, chart_type, "Median Energy (Wh)"))
    return _base_layout(fig, "Energy Distribution by Flight Phase", colors, yaxis_title="Wh", showlegend=False)


# ---------------------------------------------------------------------------
# Prioritization / baseline (priority) charts
# ---------------------------------------------------------------------------
def chart_priority_chart(comparison_df: pd.DataFrame, metric: str = "assurance_retained_pct",
                          chart_type: Optional[str] = None, colors: Optional[dict] = None) -> go.Figure:
    """Single-metric comparison across prioritization methods (e.g. from get_baseline_data).

    Parameters
    ----------
    comparison_df : DataFrame
        Must contain a ``method`` column and the requested ``metric`` column.
    metric : str
        Column to plot per method.
    """
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("trend")
    fig = go.Figure(_trend_trace(comparison_df["method"], comparison_df[metric], colors, chart_type))
    pretty = metric.replace("_", " ").title()
    return _base_layout(fig, f"Prioritization Comparison — {pretty}", colors, showlegend=False)


def chart_baseline_comparison(comparison_df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Grouped bar of energy (kWh) vs carbon (kg CO2e) across all methods."""
    colors = colors or get_chart_colors()
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Energy (kWh)", x=comparison_df["method"],
                          y=comparison_df.get("total_energy_kwh", comparison_df.get("total_energy_j", 0) / 3.6e6),
                          marker_color=colors["bar"]))
    fig.add_trace(go.Bar(name="Carbon (kg CO2e)", x=comparison_df["method"],
                          y=comparison_df.get("total_carbon_kg", comparison_df.get("total_carbon_g", 0) / 1000.0),
                          marker_color=colors["line"]))
    fig.update_layout(barmode="group")
    return _base_layout(fig, "Baseline Comparison — Energy vs Carbon", colors, showlegend=True)


# ---------------------------------------------------------------------------
# Software vs Hardware comparison charts
# ---------------------------------------------------------------------------
# 3_Energy.py simulates hardware readings on the fly (no physical power meter
# is wired in yet — SRS §8) using a small, seeded, bounded deviation from the
# software (CPU-based) estimate: +3% systematic bias, ±7% noise, clipped to
# [-20%, +35%]. That simulation is page-local to 3_Energy.py and uses its own
# enriched view (subsystem, filtered date range, etc.), so the numbers here
# won't match that page exactly — but this gives every other page (Settings
# included) a reusable, equally-deterministic hw-vs-sw comparison built
# straight from the shared dataset's own power_w / runtime_sec / flight_phase
# / timestamp columns, using the SAME seed and noise model.
CARBON_INTENSITY_G_PER_KWH = 475.0
_HW_SEED_OFFSET = 100


def _with_simulated_hardware(df: pd.DataFrame) -> pd.DataFrame:
    """Returns df with hw_power_w / hw_energy_wh / hw_carbon_g columns added
    (deterministic, seeded — same call always returns the same numbers)."""
    from utils.load_data import SEED  # local import avoids a hard circular dependency
    rng = np.random.default_rng(SEED + _HW_SEED_OFFSET)
    n = len(df)
    noise = np.clip(rng.normal(loc=0.03, scale=0.07, size=n), -0.20, 0.35)
    hw_power = (df["power_w"].to_numpy() * (1 + noise)).clip(min=1.0)
    hw_energy_j = hw_power * df["runtime_sec"].to_numpy()
    hw_energy_wh = hw_energy_j / 3600.0
    hw_carbon_g = (hw_energy_j / 3.6e6) * CARBON_INTENSITY_G_PER_KWH

    out = df.copy()
    out["hw_power_w"] = hw_power
    out["hw_energy_wh"] = hw_energy_wh
    out["hw_carbon_g"] = hw_carbon_g
    return out


def chart_hw_sw_energy_by_phase(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Grouped bar: software vs simulated-hardware energy (kWh) by flight phase."""
    colors = colors or get_chart_colors()
    hw_df = _with_simulated_hardware(df)
    by_phase = hw_df.groupby("flight_phase")[["software_energy_wh", "hw_energy_wh"]].sum() / 1000.0
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Software (kWh)", x=by_phase.index, y=by_phase["software_energy_wh"],
                          marker_color=colors["bar"]))
    fig.add_trace(go.Bar(name="Hardware (kWh, simulated)", x=by_phase.index, y=by_phase["hw_energy_wh"],
                          marker_color=colors["line"]))
    fig.update_layout(barmode="group")
    return _base_layout(fig, "Software vs Hardware — Energy by Flight Phase", colors, yaxis_title="kWh")


def chart_hw_sw_energy_trend(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Line trend: software vs simulated-hardware energy (kWh) over time."""
    colors = colors or get_chart_colors()
    hw_df = _with_simulated_hardware(df)
    sw_t = _resample_trend(hw_df, "software_energy_wh", "sum") / 1000.0
    hw_t = _resample_trend(hw_df, "hw_energy_wh", "sum") / 1000.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sw_t.index, y=sw_t.values, mode="lines", name="Software (kWh)",
                              line=dict(color=colors["bar"], width=2.5)))
    fig.add_trace(go.Scatter(x=hw_t.index, y=hw_t.values, mode="lines", name="Hardware (kWh, simulated)",
                              line=dict(color=colors["line"], width=2.5, dash="dot")))
    return _base_layout(fig, "Software vs Hardware — Energy Trend", colors, yaxis_title="kWh")


def chart_hw_sw_avg_power(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Bar: average power (W), software estimate vs simulated hardware."""
    colors = colors or get_chart_colors()
    hw_df = _with_simulated_hardware(df)
    avg_sw = hw_df["power_w"].mean()
    avg_hw = hw_df["hw_power_w"].mean()
    fig = go.Figure(go.Bar(
        x=["Software (avg)", "Hardware (avg, simulated)"], y=[avg_sw, avg_hw],
        marker=dict(color=[colors["bar"], colors["line"]]),
    ))
    return _base_layout(fig, "Average Power — Software vs Hardware", colors,
                         yaxis_title="Watts", showlegend=False)


def chart_hw_sw_energy_distribution(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Overlaid histogram: per-run software vs simulated-hardware energy (Wh)."""
    colors = colors or get_chart_colors()
    hw_df = _with_simulated_hardware(df)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=hw_df["software_energy_wh"], name="Software",
                                marker_color=colors["bar"], opacity=0.65, nbinsx=30))
    fig.add_trace(go.Histogram(x=hw_df["hw_energy_wh"], name="Hardware (simulated)",
                                marker_color=colors["line"], opacity=0.65, nbinsx=30))
    fig.update_layout(barmode="overlay")
    return _base_layout(fig, "Energy Distribution — Software vs Hardware (Wh)", colors, xaxis_title="Wh per run")

# ---------------------------------------------------------------------------
# Home / Dataset / Baseline page charts (added so Settings preview + a future
# refactor of those pages can share one source of truth)
# ---------------------------------------------------------------------------
def chart_home_status_donut(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Donut breakdown of run status — Home page style."""
    colors = colors or get_chart_colors()
    counts = df["result"].value_counts()
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=0.62,
        marker=dict(colors=colors["pie"]), textinfo="label+percent", sort=False,
    ))
    return _base_layout(fig, "Run Status Breakdown", colors, showlegend=False)


def chart_home_energy_by_phase(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Horizontal bar: total software energy (kWh) by flight phase — Home page style."""
    colors = colors or get_chart_colors()
    by_phase = df.groupby("flight_phase")["software_energy_wh"].sum().sort_values() / 1000.0
    fig = go.Figure(go.Bar(x=by_phase.values, y=by_phase.index, orientation="h",
                            marker=dict(color=colors["bar"])))
    return _base_layout(fig, "Software Energy by Flight Phase (kWh)", colors, showlegend=False)


def chart_home_runs_over_time(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Area chart: runs executed per hour — Home page style."""
    colors = colors or get_chart_colors()
    runs_by_hour = df.set_index("timestamp").resample("h").size()
    fig = go.Figure(go.Scatter(
        x=runs_by_hour.index, y=runs_by_hour.values, fill="tozeroy", mode="lines",
        line=dict(color=colors["line"], width=2), fillcolor=colors["area_fill"],
    ))
    return _base_layout(fig, "Runs Executed Per Hour", colors, showlegend=False)


def chart_weather_condition_mix(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Donut breakdown of weather condition across scenarios."""
    colors = colors or get_chart_colors()
    counts = df.drop_duplicates("test_id")["weather"].value_counts()
    fig = go.Figure(go.Pie(labels=counts.index, values=counts.values, hole=0.55,
                            marker=dict(colors=colors["pie"])))
    return _base_layout(fig, "Weather Condition Mix", colors, showlegend=True)


def chart_fault_type_distribution(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Bar: scenario counts by fault/failure type."""
    colors = colors or get_chart_colors()
    counts = df.drop_duplicates("test_id")["fault_type"].value_counts()
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker=dict(color=colors["bar"])))
    return _base_layout(fig, "Fault Type Distribution", colors, showlegend=False)


def chart_safety_level_distribution(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Bar: scenario counts by safety level (DAL-A..D order)."""
    colors = colors or get_chart_colors()
    from utils.load_data import SAFETY_LEVELS  # local import avoids a hard circular dependency
    counts = df.drop_duplicates("test_id")["safety_level"].value_counts().reindex(SAFETY_LEVELS)
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker=dict(color=colors["line"])))
    return _base_layout(fig, "Safety Level (DAL) Distribution", colors, showlegend=False)


def chart_hw_sw_diff_trend(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Line trend: hardware-vs-software energy difference (%) over time, simulated."""
    colors = colors or get_chart_colors()
    hw_df = _with_simulated_hardware(df)
    hw_df["diff_pct"] = 100 * (hw_df["hw_energy_wh"] - hw_df["software_energy_wh"]) / hw_df["software_energy_wh"]
    diff_t = hw_df.set_index("timestamp")["diff_pct"].resample("2h").mean()
    fig = go.Figure(go.Scatter(x=diff_t.index, y=diff_t.values, mode="lines+markers",
                                line=dict(color=colors["line"], width=2), marker=dict(size=4)))
    fig.add_hline(y=0, line_dash="dot", line_color=colors["grid"])
    return _base_layout(fig, "Difference Trend — Hardware vs Software (%)", colors,
                         yaxis_title="Difference (%)", showlegend=False)


def chart_hw_sw_accuracy_scatter(df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Scatter: software vs simulated-hardware energy per run, with a perfect-agreement line."""
    colors = colors or get_chart_colors()
    hw_df = _with_simulated_hardware(df)
    lo = min(hw_df["software_energy_wh"].min(), hw_df["hw_energy_wh"].min())
    hi = max(hw_df["software_energy_wh"].max(), hw_df["hw_energy_wh"].max())
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=hw_df["software_energy_wh"], y=hw_df["hw_energy_wh"], mode="markers",
                                marker=dict(size=5, color=colors["bar"], opacity=0.6), name="Runs"))
    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines",
                              line=dict(color=colors["grid"], width=1.5, dash="dash"), name="Perfect agreement"))
    return _base_layout(fig, "Software vs Hardware Energy — Estimation Accuracy", colors,
                         xaxis_title="Software Energy (Wh)", yaxis_title="Hardware Energy (Wh, simulated)")


def chart_baseline_energy_carbon_grouped(comparison_df: pd.DataFrame, colors: Optional[dict] = None) -> go.Figure:
    """Grouped bar: total energy (kWh) vs total carbon (kg CO2e) per prioritization method."""
    colors = colors or get_chart_colors()
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Energy (kWh)", x=comparison_df["method"],
                          y=comparison_df["total_energy_kwh"], marker_color=colors["bar"]))
    fig.add_trace(go.Bar(name="Carbon (kg CO2e)", x=comparison_df["method"],
                          y=comparison_df["total_carbon_kg"], marker_color=colors["line"]))
    fig.update_layout(barmode="group", xaxis_tickangle=-25)
    return _base_layout(fig, "Total Energy vs Carbon by Method", colors)
# ---------------------------------------------------------------------------
# GENERIC reusable charts — used by pages 2 (Dataset), 4 (Assurance),
# 5 (Prioritization), 6 (Baseline) so those pages' own charts are built from
# THIS module instead of page-local go.Figure calls. Each takes plain data
# (a Series, arrays, etc.) rather than the canonical dataset, so any page can
# feed it its own data while still going through get_chart_colors() /
# get_chart_type() for a Settings-controlled look.
# ---------------------------------------------------------------------------
def chart_category_breakdown(counts: pd.Series, title: str, chart_type: Optional[str] = None,
                              colors: Optional[dict] = None, orientation: str = "v",
                              category_kind: str = "category") -> go.Figure:
    """Generic category breakdown (Bar/Pie/Donut) from a value_counts() Series.
    Used for: flight phase, weather, fault type, safety level distributions.
    category_kind picks which Settings chart-type slot to honor when chart_type
    isn't explicitly given: 'category' (Bar/Pie/Donut) is the normal choice."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type(category_kind)
    fig = _category_figure(counts.index, counts.values, colors, chart_type, orientation=orientation)
    return _base_layout(fig, title, colors, showlegend=(chart_type != "Bar"))


def chart_generic_histogram(values: pd.Series, title: str, xaxis_title: Optional[str] = None,
                             yaxis_title: str = "# Tests", nbins: int = 25,
                             colors: Optional[dict] = None) -> go.Figure:
    """Generic histogram — used for assurance-score-style distributions on any page."""
    colors = colors or get_chart_colors()
    fig = go.Figure(go.Histogram(x=values, nbinsx=nbins, marker=dict(color=colors["bar"])))
    return _base_layout(fig, title, colors, xaxis_title=xaxis_title, yaxis_title=yaxis_title, showlegend=False)


def chart_two_group_scatter(x, y, group_mask, group_labels: tuple, title: str,
                             xaxis_title: Optional[str] = None, yaxis_title: Optional[str] = None,
                             text=None, colors: Optional[dict] = None) -> go.Figure:
    """Scatter split into two named, legend-labeled groups (e.g. mandatory vs
    optional), colored with two palette colors (pie[0]/pie[1]) instead of
    fixed theme colors, so it still preserves the two-group meaning while
    following the saved palette."""
    colors = colors or get_chart_colors()
    c0, c1 = colors["pie"][0], colors["pie"][1]
    x = pd.Series(x).reset_index(drop=True)
    y = pd.Series(y).reset_index(drop=True)
    mask = pd.Series(group_mask).reset_index(drop=True)
    text = pd.Series(text).reset_index(drop=True) if text is not None else None

    fig = go.Figure()
    for is_group_a, label, color in [(True, group_labels[0], c0), (False, group_labels[1], c1)]:
        sel = mask == is_group_a
        fig.add_trace(go.Scattergl(
            x=x[sel], y=y[sel], mode="markers", name=label,
            marker=dict(size=6, color=color, opacity=0.75),
            text=text[sel] if text is not None else None,
        ))
    return _base_layout(fig, title, colors, xaxis_title=xaxis_title, yaxis_title=yaxis_title, showlegend=True)


def chart_box_by_group(df: pd.DataFrame, group_col: str, value_col: str, group_order: list,
                        title: str, colors: Optional[dict] = None) -> go.Figure:
    """Box plot of value_col split by group_col, drawn in group_order."""
    colors = colors or get_chart_colors()
    fig = go.Figure()
    palette = colors["pie"]
    for i, grp in enumerate(group_order):
        subset = df[df[group_col] == grp][value_col]
        fig.add_trace(go.Box(y=subset, name=str(grp), marker=dict(color=palette[i % len(palette)])))
    return _base_layout(fig, title, colors, showlegend=False)


def chart_grouped_counts(categories: list, values: list, title: str,
                          colors: Optional[dict] = None) -> go.Figure:
    """Bar of arbitrary category counts (e.g. Safety-critical / Mandatory / Optional),
    one palette color per category."""
    colors = colors or get_chart_colors()
    palette = colors["pie"]
    bar_colors = [palette[i % len(palette)] for i in range(len(categories))]
    fig = go.Figure(go.Bar(x=categories, y=values, marker=dict(color=bar_colors)))
    return _base_layout(fig, title, colors, showlegend=False)


def chart_weights_radar(component_labels: list, weight_values: list, title: str = "Weight Distribution",
                         colors: Optional[dict] = None) -> go.Figure:
    """Radar/spider chart — e.g. assurance-score component weights."""
    colors = colors or get_chart_colors()
    fig = go.Figure(go.Scatterpolar(
        r=weight_values, theta=component_labels, fill="toself",
        line=dict(color=colors["line"]),
    ))
    fig.update_layout(
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(gridcolor=colors["grid"], color=colors["axis_label"])),
        showlegend=False,
    )
    return _base_layout(fig, title, colors, showlegend=False)


def chart_budget_curve(budgets: list, curve_vals: list, chosen_budget: Optional[float], title: str,
                        xaxis_title: str = "Energy Budget (%)", yaxis_title: str = "Assurance Retained (%)",
                        colors: Optional[dict] = None, chart_type: Optional[str] = None) -> go.Figure:
    """Line/scatter curve (e.g. assurance retained vs energy budget), with an
    optional vertical marker at the currently-chosen budget."""
    colors = colors or get_chart_colors()
    chart_type = chart_type or get_chart_type("trend")
    fig = go.Figure(_trend_trace(budgets, curve_vals, colors, chart_type))
    if chosen_budget is not None:
        fig.add_vline(x=chosen_budget, line_dash="dot", line_color=colors["line"])
    return _base_layout(fig, title, colors, xaxis_title=xaxis_title, yaxis_title=yaxis_title, showlegend=False)


def chart_single_series_bar(categories: list, values: list, title: str, color_key: str = "bar",
                             xaxis_title: Optional[str] = None, yaxis_title: Optional[str] = None,
                             colors: Optional[dict] = None) -> go.Figure:
    """Plain single-color bar chart — e.g. 'Energy Saved (%)' by method.
    color_key picks which palette color to use ('bar' or 'line')."""
    colors = colors or get_chart_colors()
    fig = go.Figure(go.Bar(x=categories, y=values, marker=dict(color=colors[color_key])))
    return _base_layout(fig, title, colors, xaxis_title=xaxis_title, yaxis_title=yaxis_title, showlegend=False)


def chart_highlight_bar(categories: list, values: list, highlighted: list, title: str,
                         xaxis_title: Optional[str] = None, yaxis_title: Optional[str] = None,
                         colors: Optional[dict] = None) -> go.Figure:
    """Bar chart where entries in `highlighted` (a bool list, same length as
    categories) get the palette's 'line' color and the rest get 'bar' — e.g.
    highlighting the winning method among several compared methods."""
    colors = colors or get_chart_colors()
    bar_colors = [colors["line"] if h else colors["bar"] for h in highlighted]
    fig = go.Figure(go.Bar(x=categories, y=values, marker=dict(color=bar_colors)))
    return _base_layout(fig, title, colors, xaxis_title=xaxis_title, yaxis_title=yaxis_title, showlegend=False)