"""
GreenAeroTester - Application Shell
=====================================
This file is ONLY the application shell. It configures the page, injects the
global dark theme, builds the sidebar/navigation, initializes shared session
state, and renders a lightweight footer. No dashboard analytics live here -
those belong in pages/1_Home.py onward.

Author: Frontend Team (Intern 2)
Status: Frontend-only build. Backend integration pending.
"""

import streamlit as st
from datetime import datetime

# ----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="GreenAeroTester | Aviation Energy Test Framework",
    page_icon="🛩️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# 2. GLOBAL THEME / STYLING
# ----------------------------------------------------------------------------
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
    --bg-primary: #0B1120;
    --bg-surface: #131B2E;
    --bg-surface-2: #0F1729;
    --border-color: #1F2A44;
    --accent-teal: #2DD4BF;
    --accent-amber: #F59E0B;
    --accent-danger: #EF4444;
    --accent-success: #22C55E;
    --text-primary: #E5E7EB;
    --text-muted: #94A3B8;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: var(--bg-primary); }

section[data-testid="stSidebar"] {
    background-color: var(--bg-surface-2);
    border-right: 1px solid var(--border-color);
}

.gat-logo-box {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 10px; margin-bottom: 6px;
    border-bottom: 1px solid var(--border-color);
}
.gat-logo-icon {
    font-size: 1.8rem; line-height: 1;
}
.gat-logo-text h2 { color: var(--text-primary); font-size: 1.05rem; font-weight: 800; margin: 0; }
.gat-logo-text p { color: var(--text-muted); font-size: 0.68rem; margin: 0; letter-spacing: 0.04em; }

.gat-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 20px 24px; margin-bottom: 22px; border-radius: 14px;
    background: linear-gradient(135deg, #0F1729 0%, #131B2E 100%);
    border: 1px solid var(--border-color);
}
.gat-header h1 { color: var(--text-primary); font-size: 1.7rem; font-weight: 800; margin: 0; }
.gat-header p { color: var(--text-muted); font-size: 0.85rem; margin: 4px 0 0 0; }
.gat-badge {
    font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 600;
    padding: 4px 10px; border-radius: 20px; letter-spacing: 0.03em;
}
.badge-online { background: rgba(34,197,94,0.15); color: var(--accent-success); border: 1px solid rgba(34,197,94,0.3); }
.badge-offline { background: rgba(239,68,68,0.15); color: var(--accent-danger); border: 1px solid rgba(239,68,68,0.3); }
.badge-pending { background: rgba(245,158,11,0.15); color: var(--accent-amber); border: 1px solid rgba(245,158,11,0.3); }

.gat-card {
    background: var(--bg-surface); border: 1px solid var(--border-color);
    border-radius: 14px; padding: 18px 20px; height: 100%;
}
.gat-card .label { color: var(--text-muted); font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.gat-card .value { color: var(--text-primary); font-family: 'JetBrains Mono', monospace; font-size: 1.7rem; font-weight: 700; margin: 6px 0 2px 0; }
.gat-card .delta-up { color: var(--accent-success); font-size: 0.78rem; }
.gat-card .delta-down { color: var(--accent-danger); font-size: 0.78rem; }
.gat-card .delta-flat { color: var(--text-muted); font-size: 0.78rem; }

.gat-section-title {
    color: var(--text-primary); font-size: 1.05rem; font-weight: 700;
    margin: 26px 0 12px 0; padding-left: 10px; border-left: 3px solid var(--accent-teal);
}

.gat-footer {
    margin-top: 40px; padding: 16px 0; border-top: 1px solid var(--border-color);
    color: var(--text-muted); font-size: 0.75rem; text-align: center;
}

div[data-testid="stMetric"] {
    background: var(--bg-surface); border: 1px solid var(--border-color);
    border-radius: 12px; padding: 14px 16px;
}
div[data-testid="stMetricValue"] { color: var(--text-primary); font-family: 'JetBrains Mono', monospace; }
div[data-testid="stMetricLabel"] { color: var(--text-muted); }

.stButton>button {
    background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);
    border-radius: 10px; font-weight: 600; transition: all 0.15s ease;
}
.stButton>button:hover { border-color: var(--accent-teal); color: var(--accent-teal); }
.stButton>button[kind="primary"] { background: var(--accent-teal); color: #06251F; border: none; }

div[data-testid="stExpander"] { background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 12px; }
hr { border-color: var(--border-color); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# 3. GLOBAL SESSION STATE (shared across all pages, ready for backend wiring)
# ----------------------------------------------------------------------------
_defaults = {
    "backend_connected": False,          # Flips to True once Intern 1's backend is wired in
    "flightgear_status": "offline",      # offline | online | pending
    "hardware_meter_status": "pending",  # ESP32 meter status (Intern 3)
    "dataset_loaded": True,              # Dummy dataset is always "loaded" for now
    "simulation_running": False,
    "simulation_progress": 0,
    "current_algorithm": "Energy Aware",
    "energy_budget": 500.0,
    "last_refresh": datetime.now(),
    "app_version": "v0.1.0-frontend-preview",
}
for key, value in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ----------------------------------------------------------------------------
# 4. SIDEBAR - LOGO, NAVIGATION, GLOBAL CONTROLS
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
    """
    <div class="gat-logo-box" style="text-align: center; padding: 10px;">
        <div class="gat-logo-icon">🛩️</div>
        <div class="gat-logo-text">
            <h2 style="color: #FFFFFF; margin-bottom: 0;">GreenAeroTester</h2>
            <p style="color: #00D2FF; font-size: 0.9rem; margin-top: 5px;">ENERGY-AWARE FLIGHT TEST FRAMEWORK</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
    

    st.caption("NAVIGATION")
st.page_link("app.py", label="Application Shell")
st.page_link("pages/1_Home.py", label="Home", icon="📊")
st.page_link("pages/2_Dataset.py", label="Dataset", icon="🗂️")
st.page_link("pages/3_Energy.py", label="Energy", icon="⚡")
st.page_link("pages/4_Assurance.py", label="Assurance", icon="🛡️")
st.page_link("pages/5_Prioritization.py", label="Prioritization", icon="🎯")
st.page_link("pages/6_Baseline.py", label="Baseline Comparison", icon="📈")
st.page_link("pages/7_Export.py", label="Export Center", icon="📤")

st.divider()
st.caption("SYSTEM SNAPSHOT")
st.markdown(
        f"""
        <span class="gat-badge {'badge-online' if st.session_state.backend_connected else 'badge-offline'}">
            BACKEND: {'ONLINE' if st.session_state.backend_connected else 'OFFLINE (DUMMY DATA)'}
        </span>
        """,
        unsafe_allow_html=True,
    )
st.caption(f"Build: {st.session_state.app_version}")
st.caption(f"Last refresh: {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")

# ----------------------------------------------------------------------------
# 5. MAIN SHELL CONTENT (no analytics - just orientation for the user)
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="gat-header">
        <div>
            <h1>🛩️ GreenAeroTester</h1>
            <p>Energy-aware aviation simulation testing, assurance scoring & carbon-conscious test prioritization</p>
        </div>
        <span class="gat-badge badge-pending">FRONTEND PREVIEW · DUMMY DATA</span>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        """<div class="gat-card"><div class="label">Backend Pipeline</div>
        <div class="value" style="font-size:1.1rem;">Not Connected</div>
        <div class="delta-flat">Awaiting Intern 1 integration</div></div>""",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        """<div class="gat-card"><div class="label">Hardware Power Meter</div>
        <div class="value" style="font-size:1.1rem;">Pending</div>
        <div class="delta-flat">ESP32 stream not yet linked</div></div>""",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        """<div class="gat-card"><div class="label">Dashboard</div>
        <div class="value" style="font-size:1.1rem;">Ready</div>
        <div class="delta-up">All 7 pages available</div></div>""",
        unsafe_allow_html=True,
    )

st.write("")
st.markdown('<div class="gat-section-title">Get Started</div>', unsafe_allow_html=True)
st.write(
    "Use the sidebar to explore the dashboard. Every page currently runs on "
    "realistic dummy data generated locally so the full experience can be "
    "reviewed before the backend, hardware, and dataset pipelines are wired in."
)
st.page_link("pages/1_Home.py", label="➡️  Go to Home Dashboard", icon="📊")

# ----------------------------------------------------------------------------
# 6. FOOTER
# ----------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="gat-footer">
        GreenAeroTester &middot; University Internship Project &middot; {datetime.now().year}
        &middot; Frontend build {st.session_state.app_version}
    </div>
    """,
    unsafe_allow_html=True,
)
