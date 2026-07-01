"""
GreenAeroTester - Prioritization Page
========================================
Lets users generate an energy-aware test prioritization using one of six
algorithms (Default CI, Random, Runtime Based, Failure History, Energy
Aware, Knapsack), respecting an energy budget and mandatory-first rule.
All ranking logic here is a frontend stand-in for prioritizer.py /
knapsack_selector.py, which Intern 1 will implement on the backend.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Prioritization | GreenAeroTester", page_icon="🎯", layout="wide")

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
.stButton>button { background:var(--bg-surface); color:var(--text-primary); border:1px solid var(--border-color); border-radius:10px; font-weight:600; width:100%; }
.stButton>button:hover { border-color:var(--accent-teal); color:var(--accent-teal); }
hr { border-color: var(--border-color); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"
ALGORITHMS = ["Default CI", "Random", "Runtime Based", "Failure History", "Energy Aware", "Knapsack"]


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
# DUMMY TEST POOL
# ----------------------------------------------------------------------------
@st.cache_data
def generate_test_pool(n: int = 60, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
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
    return df


test_pool = generate_test_pool()

# ----------------------------------------------------------------------------
# DEFENSIVE SESSION STATE (in case this page is opened directly)
# ----------------------------------------------------------------------------
if "current_algorithm" not in st.session_state:
    st.session_state.current_algorithm = "Energy Aware"
if "energy_budget" not in st.session_state:
    st.session_state.energy_budget = 500.0


def rank_default_ci(df):
    return df.sort_values("ci_order")


def rank_random(df, seed=None):
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def rank_runtime_based(df):
    return df.sort_values("median_runtime_s")


def rank_failure_history(df):
    return df.sort_values("failure_count", ascending=False)


def rank_energy_aware(df):
    # Utility = assurance value gained per unit energy spent
    scored = df.copy()
    scored["utility"] = scored["assurance_score"] / scored["median_energy_wh"]
    return scored.sort_values("utility", ascending=False)


def rank_knapsack(df, budget):
    # 0/1 knapsack maximizing assurance_score within the energy budget (mandatory forced in first)
    mandatory = df[df["mandatory"]].copy()
    optional = df[~df["mandatory"]].copy()
    remaining_budget = max(budget - mandatory["median_energy_wh"].sum(), 0)

    optional = optional.sort_values(by="assurance_score", ascending=False)
    selected_rows, used = [], 0.0
    for _, row in optional.iterrows():
        if used + row["median_energy_wh"] <= remaining_budget:
            selected_rows.append(row)
            used += row["median_energy_wh"]
    selected_optional = pd.DataFrame(selected_rows) if selected_rows else pd.DataFrame(columns=df.columns)
    ordered = pd.concat([mandatory, selected_optional], ignore_index=True)
    return ordered


ALGO_FUNCS = {
    "Default CI": lambda df, budget: rank_default_ci(df),
    "Random": lambda df, budget: rank_random(df, seed=None),
    "Runtime Based": lambda df, budget: rank_runtime_based(df),
    "Failure History": lambda df, budget: rank_failure_history(df),
    "Energy Aware": lambda df, budget: rank_energy_aware(df),
    "Knapsack": lambda df, budget: rank_knapsack(df, budget),
}

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="gat-header">
        <div><h1>🎯 Test Prioritization</h1><p>Rank and select tests using energy-aware and baseline algorithms</p></div>
        <span class="gat-badge badge-pending">DUMMY DATA</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# CONTROLS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Configuration</div>', unsafe_allow_html=True)
ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1, 1])
with ctrl1:
    algorithm = st.selectbox("Algorithm", ALGORITHMS,
                              index=ALGORITHMS.index(st.session_state.current_algorithm)
                              if st.session_state.current_algorithm in ALGORITHMS else 0)
with ctrl2:
    energy_budget = st.number_input("Energy Budget (Wh)", min_value=1.0, max_value=500.0,
                                     value=float(st.session_state.energy_budget), step=5.0)
with ctrl3:
    runtime_budget = st.number_input("Runtime Budget (s, optional)", min_value=0.0, value=0.0, step=100.0,
                                      help="Set to 0 to ignore the runtime budget constraint.")

btn1, btn2, btn3 = st.columns(3)
generate_clicked = btn1.button("⚙️ Generate Prioritization", use_container_width=True)
reset_clicked = btn2.button("♻️ Reset", use_container_width=True)
export_clicked_placeholder = btn3.empty()

if reset_clicked:
    st.session_state.current_algorithm = "Energy Aware"
    st.session_state.energy_budget = 500.0
    st.cache_data.clear()
    st.rerun()

if generate_clicked:
    st.session_state.current_algorithm = algorithm
    st.session_state.energy_budget = energy_budget

# Generate the ranking every run so the page always shows a result
ranked_df = ALGO_FUNCS[algorithm](test_pool, energy_budget).reset_index(drop=True)
ranked_df.insert(0, "rank", range(1, len(ranked_df) + 1))

if runtime_budget > 0:
    cumulative_runtime = ranked_df["median_runtime_s"].cumsum()
    ranked_df = ranked_df[cumulative_runtime <= runtime_budget].copy() if algorithm != "Knapsack" else ranked_df

selected_energy = ranked_df["median_energy_wh"].sum()
selected_mandatory = int(ranked_df["mandatory"].sum())

# ----------------------------------------------------------------------------
# SUMMARY CARDS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Prioritization Summary</div>', unsafe_allow_html=True)
p1, p2, p3, p4 = st.columns(4)
with p1:
    metric_card("Selected Tests", f"{len(ranked_df)}", f"of {len(test_pool)} total")
with p2:
    metric_card("Mandatory Tests Included", f"{selected_mandatory}", f"of {int(test_pool['mandatory'].sum())} total")
with p3:
    metric_card("Energy Used", f"{selected_energy:.1f} Wh", f"budget: {energy_budget:.0f} Wh")
with p4:
    metric_card("Avg Assurance Retained", f"{ranked_df['assurance_score'].mean():.1f}" if len(ranked_df) else "0.0")

# ----------------------------------------------------------------------------
# RANKED TABLE + EXPORT
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Ranked Test List</div>', unsafe_allow_html=True)
display_df = ranked_df[["rank", "test_id", "mandatory", "median_runtime_s", "median_energy_wh",
                         "failure_count", "assurance_score"]]
st.dataframe(display_df, use_container_width=True, hide_index=True)

csv_bytes = display_df.to_csv(index=False).encode("utf-8")
export_clicked_placeholder.download_button(
    "⬇️ Export Ranking", data=csv_bytes,
    file_name=f"prioritization_{algorithm.replace(' ', '_').lower()}.csv",
    mime="text/csv", use_container_width=True,
)

# ----------------------------------------------------------------------------
# COMPARISON CHARTS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Ranking Insight</div>', unsafe_allow_html=True)
ch1, ch2 = st.columns(2)
with ch1:
    fig = px.bar(display_df.head(20), x="test_id", y="median_energy_wh", color="mandatory",
                 title="Energy by Rank (Top 20)", color_discrete_map={True: "#F59E0B", False: "#2DD4BF"})
    st.plotly_chart(style_fig(fig), use_container_width=True)
with ch2:
    fig = px.line(display_df, x="rank", y="assurance_score", title="Assurance Score by Rank Position",
                  color_discrete_sequence=["#A78BFA"])
    st.plotly_chart(style_fig(fig), use_container_width=True)

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown("""<div class="gat-footer">GreenAeroTester Dashboard &middot; Prioritization</div>""", unsafe_allow_html=True)
