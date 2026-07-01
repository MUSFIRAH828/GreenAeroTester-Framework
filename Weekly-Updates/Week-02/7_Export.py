"""
GreenAeroTester - Export Center Page
=======================================
A professional Export Center offering download cards for every dataset,
metric file, chart bundle, and report described in the SRS's dataset
structure rule. Backed by dummy CSVs for now; ready to be pointed at the
real files under data/raw, data/processed, data/final, and results/.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Export | GreenAeroTester", page_icon="📤", layout="wide")

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
.gat-card { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:14px; padding:18px 20px; height:100%; }
.gat-card .label { color:var(--text-muted); font-size:0.72rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; }
.gat-card .value { color:var(--text-primary); font-family:'JetBrains Mono',monospace; font-size:1.15rem; font-weight:700; margin:6px 0 8px 0; }
.gat-section-title { color:var(--text-primary); font-size:1.05rem; font-weight:700; margin:26px 0 12px 0; padding-left:10px; border-left:3px solid var(--accent-teal); }
.gat-footer { margin-top:40px; padding:16px 0; border-top:1px solid var(--border-color); color:var(--text-muted); font-size:0.75rem; text-align:center; }
.stButton>button, .stDownloadButton>button { background:var(--bg-surface); color:var(--text-primary);
    border:1px solid var(--border-color); border-radius:10px; font-weight:600; width:100%; }
.stButton>button:hover, .stDownloadButton>button:hover { border-color:var(--accent-teal); color:var(--accent-teal); }
div[data-testid="stExpander"] { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:12px; }
hr { border-color: var(--border-color); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)


def badge(text, kind):
    return f'<span class="gat-badge badge-{kind}">{text}</span>'


# ----------------------------------------------------------------------------
# DUMMY EXPORT DATA GENERATORS (stand in for real backend/dataset files)
# ----------------------------------------------------------------------------
@st.cache_data
def make_dummy_csv(columns, n=50, seed=1):
    rng = np.random.default_rng(seed)
    data = {col: rng.normal(50, 15, n).round(2) for col in columns}
    return pd.DataFrame(data).to_csv(index=False).encode("utf-8")


EXPORT_CARDS = [
    {"name": "Raw Dataset", "file": "raw_dataset.csv", "desc": "Unfiltered runs including failed/timeout/crashed.",
     "status": "ready", "cols": ["runtime_s", "cpu_pct", "memory_mb"]},
    {"name": "Processed Dataset", "file": "processed_dataset.csv", "desc": "Cleaned and validated run records.",
     "status": "ready", "cols": ["runtime_s", "energy_wh", "carbon_g"]},
    {"name": "Final Dataset", "file": "final_dataset.csv", "desc": "Merged, analysis-ready dataset.",
     "status": "ready", "cols": ["energy_wh", "carbon_g", "assurance_score"]},
    {"name": "Energy Metrics", "file": "energy_metrics.csv", "desc": "Software + hardware energy metrics.",
     "status": "ready", "cols": ["software_energy_wh", "hardware_energy_wh", "power_w"]},
    {"name": "Assurance Results", "file": "assurance_results.csv", "desc": "Per-test assurance scoring output.",
     "status": "ready", "cols": ["safety_score", "coverage", "assurance_score"]},
    {"name": "Prioritization Results", "file": "prioritization_results.csv", "desc": "Latest generated ranking.",
     "status": "ready", "cols": ["rank", "energy_wh", "assurance_score"]},
    {"name": "Baseline Comparison", "file": "baseline_comparison.csv", "desc": "All-algorithm comparison table.",
     "status": "ready", "cols": ["runtime_s", "energy_wh", "efficiency"]},
    {"name": "Charts", "file": "charts_bundle.csv", "desc": "Figure data bundle backing dashboard charts.",
     "status": "pending", "cols": ["chart_id", "series"]},
    {"name": "Reports", "file": "reports_bundle.csv", "desc": "Auto-generated PDF/HTML summary reports.",
     "status": "pending", "cols": ["report_id", "section"]},
]

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="gat-header">
        <div><h1>📤 Export Center</h1><p>Download datasets, metrics, prioritization results, charts, and reports</p></div>
        <span class="gat-badge badge-pending">DUMMY DATA</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# PROJECT SUMMARY
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Project Summary</div>', unsafe_allow_html=True)
ps1, ps2, ps3, ps4 = st.columns(4)
with ps1:
    st.markdown('<div class="gat-card"><div class="label">Project</div><div class="value" style="font-size:1rem;">GreenAeroTester</div></div>', unsafe_allow_html=True)
with ps2:
    st.markdown('<div class="gat-card"><div class="label">Dataset Version</div><div class="value" style="font-size:1rem;">v0.1-dummy</div></div>', unsafe_allow_html=True)
with ps3:
    st.markdown('<div class="gat-card"><div class="label">Total Scenarios</div><div class="value" style="font-size:1rem;">42</div></div>', unsafe_allow_html=True)
with ps4:
    st.markdown('<div class="gat-card"><div class="label">Total Runs</div><div class="value" style="font-size:1rem;">320</div></div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# SYSTEM INFORMATION
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">System Information</div>', unsafe_allow_html=True)
with st.expander("Environment & pipeline details", expanded=False):
    sys_info = pd.DataFrame(
        {
            "Component": ["Frontend", "Backend Pipeline", "FlightGear", "Hardware Meter", "Dataset Source", "App Version"],
            "Status": ["Streamlit dashboard (this build)", "Not connected", "Offline", "Pending (ESP32)", "Local dummy generator",
                       st.session_state.get("app_version", "v0.1.0-frontend-preview")],
        }
    )
    st.dataframe(sys_info, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# EXPORT CARDS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Export Center</div>', unsafe_allow_html=True)
export_log = []
cols = st.columns(3)
for i, card in enumerate(EXPORT_CARDS):
    with cols[i % 3]:
        status_kind = "online" if card["status"] == "ready" else "pending"
        st.markdown(
            f"""<div class="gat-card">
                <div class="label">{card['name']}</div>
                <div class="value">{badge(card['status'].upper(), status_kind)}</div>
                <div style="color:var(--text-muted);font-size:0.78rem;margin-bottom:10px;">{card['desc']}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        csv_data = make_dummy_csv(card["cols"], seed=i + 1)
        clicked = st.download_button(
            f"⬇️ Download {card['name']}", data=csv_data, file_name=card["file"],
            mime="text/csv", key=f"dl_{card['file']}", disabled=(card["status"] != "ready"),
        )
        if clicked:
            export_log.append(card["name"])

# ----------------------------------------------------------------------------
# EXPORT HISTORY
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Export History</div>', unsafe_allow_html=True)
history_df = pd.DataFrame(
    {
        "Timestamp": [(datetime.now() - timedelta(hours=h)).strftime("%Y-%m-%d %H:%M") for h in [1, 5, 20, 48, 96]],
        "Item": ["Final Dataset", "Baseline Comparison", "Prioritization Results", "Raw Dataset", "Energy Metrics"],
        "Format": ["CSV", "CSV", "CSV", "CSV", "CSV"],
        "Status": ["Success", "Success", "Success", "Success", "Success"],
    }
)
st.dataframe(history_df, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown("""<div class="gat-footer">GreenAeroTester Dashboard &middot; Export Center</div>""", unsafe_allow_html=True)
