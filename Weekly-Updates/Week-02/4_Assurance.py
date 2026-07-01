"""
GreenAeroTester - Assurance Page
===================================
Surfaces per-test assurance scoring built from safety score, requirement
coverage, fault history, change relevance, novelty, flakiness, and
certification relevance - matching the SRS's assurance_features.csv schema.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Assurance | GreenAeroTester", page_icon="🛡️", layout="wide")

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
.badge-offline { background:rgba(239,68,68,0.15); color:var(--accent-danger); border:1px solid rgba(239,68,68,0.3); }
.badge-pending { background:rgba(245,158,11,0.15); color:var(--accent-amber); border:1px solid rgba(245,158,11,0.3); }
.gat-card { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:14px; padding:16px 18px; height:100%; }
.gat-card .label { color:var(--text-muted); font-size:0.72rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; }
.gat-card .value { color:var(--text-primary); font-family:'JetBrains Mono',monospace; font-size:1.55rem; font-weight:700; margin:6px 0 2px 0; }
.gat-section-title { color:var(--text-primary); font-size:1.05rem; font-weight:700; margin:26px 0 12px 0; padding-left:10px; border-left:3px solid var(--accent-teal); }
.gat-footer { margin-top:40px; padding:16px 0; border-top:1px solid var(--border-color); color:var(--text-muted); font-size:0.75rem; text-align:center; }
div[data-testid="stExpander"] { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:12px; }
hr { border-color: var(--border-color); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"


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


def risk_badge(score):
    if score >= 75:
        return '<span class="gat-badge badge-online">LOW RISK</span>'
    elif score >= 50:
        return '<span class="gat-badge badge-pending">MEDIUM RISK</span>'
    return '<span class="gat-badge badge-offline">HIGH RISK</span>'


# ----------------------------------------------------------------------------
# DUMMY ASSURANCE FEATURES (mirrors assurance_features.csv)
# ----------------------------------------------------------------------------
@st.cache_data
def generate_assurance_dataset(n: int = 90, seed: int = 13) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "test_id": [f"T{i:04d}" for i in range(1, n + 1)],
            "safety_score": np.clip(rng.normal(72, 15, n), 0, 100).round(1),
            "requirement_coverage": np.clip(rng.normal(78, 12, n), 0, 100).round(1),
            "fault_history": np.clip(rng.normal(30, 20, n), 0, 100).round(1),
            "change_relevance": np.clip(rng.normal(45, 22, n), 0, 100).round(1),
            "novelty": np.clip(rng.normal(35, 20, n), 0, 100).round(1),
            "flakiness": np.clip(rng.normal(20, 15, n), 0, 100).round(1),
            "certification_relevance": np.clip(rng.normal(65, 18, n), 0, 100).round(1),
            "mandatory": rng.random(n) < 0.32,
            "software_energy_wh": np.clip(rng.normal(1.9, 0.6, n), 0.1, None).round(3),
        }
    )
    # Weighted composite assurance score (higher fault history / flakiness reduces confidence)
    df["assurance_score"] = (
        0.28 * df["safety_score"]
        + 0.22 * df["requirement_coverage"]
        + 0.15 * df["certification_relevance"]
        + 0.15 * (100 - df["flakiness"])
        + 0.10 * df["change_relevance"]
        + 0.10 * df["novelty"]
    ).round(1)
    df["risk_level"] = np.where(df["assurance_score"] >= 75, "Low",
                          np.where(df["assurance_score"] >= 50, "Medium", "High"))
    return df


assurance_df = generate_assurance_dataset()

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="gat-header">
        <div><h1>🛡️ Assurance</h1><p>Confidence scoring across safety, coverage, fault history, and certification relevance</p></div>
        <span class="gat-badge badge-pending">DUMMY DATA</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# SUMMARY CARDS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Summary</div>', unsafe_allow_html=True)
a1, a2, a3, a4, a5, a6 = st.columns(6)
avg_score = assurance_df["assurance_score"].mean()
with a1:
    metric_card("Average Assurance Score", f"{avg_score:.1f}")
with a2:
    metric_card("Highest Score", f"{assurance_df['assurance_score'].max():.1f}")
with a3:
    metric_card("Lowest Score", f"{assurance_df['assurance_score'].min():.1f}")
with a4:
    metric_card("Coverage", f"{assurance_df['requirement_coverage'].mean():.1f} %")
with a5:
    metric_card("Requirement Satisfaction", f"{(assurance_df['requirement_coverage'] >= 70).mean():.0%}")
with a6:
    st.markdown(
        f"""<div class="gat-card"><div class="label">Risk Level</div>
        <div class="value" style="font-size:1.1rem;">{risk_badge(avg_score)}</div></div>""",
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------------
# CHARTS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Analytics</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    fig = px.histogram(assurance_df, x="assurance_score", nbins=25, title="Assurance Score Distribution",
                        color_discrete_sequence=["#2DD4BF"])
    st.plotly_chart(style_fig(fig), use_container_width=True)
with c2:
    fig = px.box(assurance_df, y="safety_score", title="Safety Score Spread", color_discrete_sequence=["#F59E0B"])
    st.plotly_chart(style_fig(fig), use_container_width=True)

c3, c4 = st.columns(2)
with c3:
    fig = px.scatter(assurance_df, x="fault_history", y="assurance_score", color="risk_level",
                      title="Fault History vs Assurance Score",
                      color_discrete_map={"Low": "#22C55E", "Medium": "#F59E0B", "High": "#EF4444"})
    st.plotly_chart(style_fig(fig), use_container_width=True)
with c4:
    feature_avgs = assurance_df[
        ["safety_score", "requirement_coverage", "fault_history", "change_relevance",
         "novelty", "flakiness", "certification_relevance"]
    ].mean()
    fig = px.bar_polar(r=feature_avgs.values, theta=feature_avgs.index, title="Average Feature Profile",
                        color_discrete_sequence=["#A78BFA"])
    st.plotly_chart(style_fig(fig), use_container_width=True)

c5, c6 = st.columns(2)
with c5:
    fig = px.scatter(assurance_df, x="software_energy_wh", y="assurance_score", color="mandatory",
                      title="Assurance vs Energy Scatter Plot",
                      color_discrete_map={True: "#2DD4BF", False: "#94A3B8"})
    st.plotly_chart(style_fig(fig), use_container_width=True)
with c6:
    risk_counts = assurance_df["risk_level"].value_counts().reindex(["Low", "Medium", "High"]).fillna(0)
    fig = px.pie(names=risk_counts.index, values=risk_counts.values, hole=0.5, title="Risk Level Breakdown",
                 color_discrete_map={"Low": "#22C55E", "Medium": "#F59E0B", "High": "#EF4444"})
    st.plotly_chart(style_fig(fig), use_container_width=True)

# ----------------------------------------------------------------------------
# TABLES
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Test-Level Assurance</div>', unsafe_allow_html=True)
tab1, tab2 = st.tabs(["Top Scoring Tests", "Lowest Scoring / High Risk Tests"])
with tab1:
    st.dataframe(
        assurance_df.sort_values("assurance_score", ascending=False).head(20),
        use_container_width=True, hide_index=True,
    )
with tab2:
    st.dataframe(
        assurance_df[assurance_df["risk_level"] == "High"].sort_values("assurance_score").head(20),
        use_container_width=True, hide_index=True,
    )

with st.expander("Full assurance feature table"):
    st.dataframe(assurance_df, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown("""<div class="gat-footer">GreenAeroTester Dashboard &middot; Assurance</div>""", unsafe_allow_html=True)
