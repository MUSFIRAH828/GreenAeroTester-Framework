"""
GreenAeroTester - Baseline Comparison Page
=============================================
Runs all six prioritization algorithms against the same dummy test pool and
compares them on runtime, energy, carbon, assurance, mandatory coverage, and
efficiency - mirroring the SRS's baseline_comparison.csv output.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Baseline | GreenAeroTester", page_icon="📈", layout="wide")

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root { --bg-primary:#0B1120; --bg-surface:#131B2E; --bg-surface-2:#0F1729; --border-color:#1F2A44;
    --accent-teal:#2DD4BF; --accent-amber:#F59E0B; --accent-danger:#EF4444; --accent-success:#22C55E;
    --text-primary:#E5E7EB; --text-muted:#94A3B8; }
html, body, [class*="css"] { font-family:'Inter',sans-serif; }
.stApp { background-color: var(--bg-primary); }
section[data-testid="stSidebar"] { background-color: var(--bg-surface-2); border-right:1px solid var(--border-color); }
.gat-header { display:flex; align-items:center; justify-content:space-between; padding:20px 24px; margin-bottom:22px;
    border-radius:14px; background:linear-gradient(135deg,#0F1729 0%,#131B2E 100%); border:1px solid var(--border-color); }
.gat-header h1 { color:var(--text-primary); font-size:1.6rem; font-weight:800; margin:0; }
.gat-header p { color:var(--text-muted); font-size:0.85rem; margin:4px 0 0 0; }
.gat-badge { font-family:'JetBrains Mono',monospace; font-size:0.72rem; font-weight:600; padding:4px 10px; border-radius:20px; letter-spacing:0.03em; }
.badge-online { background:rgba(34,197,94,0.15); color:var(--accent-success); border:1px solid rgba(34,197,94,0.3); }
.badge-pending { background:rgba(245,158,11,0.15); color:var(--accent-amber); border:1px solid rgba(245,158,11,0.3); }
.gat-card { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:14px; padding:16px 18px; height:100%; }
.gat-card .label { color:var(--text-muted); font-size:0.72rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; }
.gat-card .value { color:var(--text-primary); font-family:'JetBrains Mono',monospace; font-size:1.55rem; font-weight:700; margin:6px 0 2px 0; }
.gat-section-title { color:var(--text-primary); font-size:1.05rem; font-weight:700; margin:26px 0 12px 0; padding-left:10px; border-left:3px solid var(--accent-teal); }
.gat-footer { margin-top:40px; padding:16px 0; border-top:1px solid var(--border-color); color:var(--text-muted); font-size:0.75rem; text-align:center; }
hr { border-color: var(--border-color); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"
ALGORITHMS = ["Default CI", "Random", "Runtime Based", "Failure History", "Energy Aware", "Knapsack"]
ALGO_COLORS = {
    "Default CI": "#94A3B8", "Random": "#F472B6", "Runtime Based": "#60A5FA",
    "Failure History": "#F59E0B", "Energy Aware": "#2DD4BF", "Knapsack": "#A78BFA",
}
CARBON_INTENSITY_G_PER_WH = 0.442  # 442 gCO2/kWh -> g per Wh


def style_fig(fig, height=340):
    fig.update_layout(
        template=PLOTLY_TEMPLATE, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#E5E7EB", size=12),
        margin=dict(l=10, r=10, t=40, b=10), height=height,
    )
    return fig


def metric_card(label, value, sub=""):
    st.markdown(
        f"""<div class="gat-card"><div class="label">{label}</div>
        <div class="value">{value}</div><div style="color:var(--text-muted);font-size:0.76rem;">{sub}</div></div>""",
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# DUMMY TEST POOL (same shape as Prioritization page, regenerated locally)
# ----------------------------------------------------------------------------
@st.cache_data
def generate_test_pool(n: int = 60, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "test_id": [f"T{i:04d}" for i in range(1, n + 1)],
            "mandatory": rng.random(n) < 0.3,
            "median_runtime_s": np.clip(rng.normal(180, 45, n), 30, None).round(1),
            "median_energy_wh": np.clip(rng.normal(1.9, 0.6, n), 0.1, None).round(3),
            "failure_count": rng.poisson(1.2, n),
            "assurance_score": np.clip(rng.normal(65, 18, n), 0, 100).round(1),
            "ci_order": np.arange(1, n + 1),
        }
    )


def select_within_budget(ordered_df, budget, mandatory_first=True):
    """Given a ranking order, select tests greedily within the energy budget,
    always keeping mandatory tests."""
    mandatory = ordered_df[ordered_df["mandatory"]]
    optional = ordered_df[~ordered_df["mandatory"]]
    used = mandatory["median_energy_wh"].sum()
    selected = [mandatory]
    for _, row in optional.iterrows():
        if used + row["median_energy_wh"] <= budget:
            selected.append(pd.DataFrame([row]))
            used += row["median_energy_wh"]
    return pd.concat(selected, ignore_index=True) if selected else ordered_df.iloc[0:0]


@st.cache_data
def run_all_algorithms(budget: float = 250.0, seed: int = 5) -> pd.DataFrame:
    pool = generate_test_pool(seed=seed)
    rng = np.random.default_rng(99)
    results = []

    orderings = {
        "Default CI": pool.sort_values("ci_order"),
        "Random": pool.sample(frac=1, random_state=99).reset_index(drop=True),
        "Runtime Based": pool.sort_values("median_runtime_s"),
        "Failure History": pool.sort_values("failure_count", ascending=False),
        "Energy Aware": pool.assign(utility=pool["assurance_score"] / pool["median_energy_wh"])
                             .sort_values("utility", ascending=False),
        "Knapsack": pool.sort_values("assurance_score", ascending=False),
    }

    for algo, ordered in orderings.items():
        selected = select_within_budget(ordered, budget)
        total_runtime = selected["median_runtime_s"].sum()
        total_energy = selected["median_energy_wh"].sum()
        total_carbon = total_energy * CARBON_INTENSITY_G_PER_WH
        avg_assurance = selected["assurance_score"].mean() if len(selected) else 0
        mandatory_coverage = (
            selected["mandatory"].sum() / max(pool["mandatory"].sum(), 1)
        ) * 100
        efficiency = avg_assurance / total_energy if total_energy > 0 else 0
        results.append(
            {
                "Algorithm": algo,
                "Selected Tests": len(selected),
                "Runtime (s)": round(total_runtime, 1),
                "Energy (Wh)": round(total_energy, 2),
                "Carbon (g)": round(total_carbon, 2),
                "Assurance": round(avg_assurance, 1),
                "Mandatory Coverage (%)": round(mandatory_coverage, 1),
                "Efficiency (Assurance/Wh)": round(efficiency, 2),
            }
        )
    return pd.DataFrame(results)


# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="gat-header">
        <div><h1>📈 Baseline Comparison</h1><p>Compare all prioritization algorithms head-to-head under the same energy budget</p></div>
        <span class="gat-badge badge-pending">DUMMY DATA</span>
    </div>
    """,
    unsafe_allow_html=True,
)

budget = st.slider("Comparison Energy Budget (Wh)", min_value=20.0, max_value=400.0, value=250.0, step=10.0)
comparison_df = run_all_algorithms(budget=budget)

# ----------------------------------------------------------------------------
# BEST ALGORITHM RECOMMENDATION
# ----------------------------------------------------------------------------
best_row = comparison_df.sort_values("Efficiency (Assurance/Wh)", ascending=False).iloc[0]
st.markdown('<div class="gat-section-title">Recommendation</div>', unsafe_allow_html=True)
st.markdown(
    f"""<div class="gat-card">
        <div class="label">Best Algorithm (highest assurance-per-energy efficiency)</div>
        <div class="value" style="color:var(--accent-teal);">{best_row['Algorithm']}</div>
        <div style="color:var(--text-muted);font-size:0.8rem;">
            {best_row['Selected Tests']} tests selected · {best_row['Energy (Wh)']} Wh ·
            assurance {best_row['Assurance']} · mandatory coverage {best_row['Mandatory Coverage (%)']}%
        </div></div>""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# COMPARISON TABLE
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Comparison Table</div>', unsafe_allow_html=True)
st.dataframe(comparison_df, use_container_width=True, hide_index=True)
st.download_button(
    "⬇️ Export Baseline Comparison", data=comparison_df.to_csv(index=False).encode("utf-8"),
    file_name="baseline_comparison.csv", mime="text/csv",
)

# ----------------------------------------------------------------------------
# COMPARISON CHARTS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Comparison Charts</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    fig = px.bar(comparison_df, x="Algorithm", y="Runtime (s)", color="Algorithm",
                 color_discrete_map=ALGO_COLORS, title="Runtime by Algorithm")
    st.plotly_chart(style_fig(fig), use_container_width=True)
with c2:
    fig = px.bar(comparison_df, x="Algorithm", y="Energy (Wh)", color="Algorithm",
                 color_discrete_map=ALGO_COLORS, title="Energy by Algorithm")
    st.plotly_chart(style_fig(fig), use_container_width=True)

c3, c4 = st.columns(2)
with c3:
    fig = px.bar(comparison_df, x="Algorithm", y="Carbon (g)", color="Algorithm",
                 color_discrete_map=ALGO_COLORS, title="Carbon by Algorithm")
    st.plotly_chart(style_fig(fig), use_container_width=True)
with c4:
    fig = px.bar(comparison_df, x="Algorithm", y="Assurance", color="Algorithm",
                 color_discrete_map=ALGO_COLORS, title="Assurance Retained by Algorithm")
    st.plotly_chart(style_fig(fig), use_container_width=True)

c5, c6 = st.columns(2)
with c5:
    fig = px.bar(comparison_df, x="Algorithm", y="Mandatory Coverage (%)", color="Algorithm",
                 color_discrete_map=ALGO_COLORS, title="Mandatory Coverage by Algorithm")
    st.plotly_chart(style_fig(fig), use_container_width=True)
with c6:
    fig = px.bar(comparison_df, x="Algorithm", y="Efficiency (Assurance/Wh)", color="Algorithm",
                 color_discrete_map=ALGO_COLORS, title="Efficiency by Algorithm")
    st.plotly_chart(style_fig(fig), use_container_width=True)

st.markdown('<div class="gat-section-title">Multi-Metric Radar</div>', unsafe_allow_html=True)
radar_metrics = ["Runtime (s)", "Energy (Wh)", "Carbon (g)", "Assurance", "Mandatory Coverage (%)"]
norm_df = comparison_df.copy()
for m in radar_metrics:
    max_val = norm_df[m].max() or 1
    norm_df[m + "_norm"] = norm_df[m] / max_val

fig = go.Figure()
for _, row in norm_df.iterrows():
    fig.add_trace(
        go.Scatterpolar(
            r=[row[m + "_norm"] for m in radar_metrics] + [row[radar_metrics[0] + "_norm"]],
            theta=radar_metrics + [radar_metrics[0]],
            fill="toself", name=row["Algorithm"],
            line=dict(color=ALGO_COLORS.get(row["Algorithm"])),
        )
    )
fig.update_layout(title="Normalized Multi-Metric Comparison", polar=dict(radialaxis=dict(visible=True, range=[0, 1])))
st.plotly_chart(style_fig(fig, 460), use_container_width=True)

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown("""<div class="gat-footer">GreenAeroTester Dashboard &middot; Baseline Comparison</div>""", unsafe_allow_html=True)
