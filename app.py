"""FinSight — entry point using st.navigation for reliable multi-page routing."""
import streamlit as st

st.set_page_config(
    page_title="FinSight — Financial Statement Analyser",
    page_icon="",
    layout="wide",
)

# ── Global styles + nav bar ───────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 0 !important; padding-bottom: 3rem; }
#MainMenu, footer, header { visibility: hidden; }

.topnav {
    background: #0d1117;
    border-bottom: 1px solid #21262d;
    padding: 0 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 56px;
    position: sticky;
    top: 0;
    z-index: 999;
    margin-bottom: 0;
}
.topnav-brand { color: #f0f6fc; font-size: 1.05rem; font-weight: 700; letter-spacing: -0.3px; }
.topnav-links { display: flex; gap: 0.2rem; align-items: center; }
.nav-btn {
    background: none;
    border: none;
    color: #8b949e;
    font-size: 0.87rem;
    font-weight: 500;
    padding: 0.35rem 0.9rem;
    border-radius: 6px;
    cursor: pointer;
    font-family: 'Inter', sans-serif;
    transition: background 0.15s, color 0.15s;
}
.nav-btn:hover { background: #161b22; color: #f0f6fc; }
.nav-btn.active { background: #161b22; color: #f0f6fc; }
.nav-btn.cta { background: #2e5eaa; color: #fff; font-weight: 600; }
.nav-btn.cta:hover { background: #1a4a8a; }

[data-testid="metric-container"] {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 10px; padding: 0.9rem 1rem;
}
[data-testid="metric-container"] label {
    color: #8b949e !important; font-size: 0.72rem !important;
    font-weight: 700 !important; letter-spacing: 0.8px; text-transform: uppercase;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f0f6fc !important; font-size: 1.2rem !important; font-weight: 700 !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }

div[data-testid="stButton"] > button {
    background: #2e5eaa; color: white !important; border: none;
    border-radius: 8px; padding: 0.7rem 2rem; font-size: 0.95rem;
    font-weight: 600; width: 100%; transition: background 0.2s;
}
div[data-testid="stButton"] > button:hover { background: #1a4a8a; }

[data-testid="stDownloadButton"] > button {
    background: #161b22 !important; color: #f0f6fc !important;
    border: 1px solid #30363d !important; border-radius: 8px;
    font-size: 0.88rem; font-weight: 500; width: 100%;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #58a6ff !important; color: #58a6ff !important;
}
[data-testid="stExpander"] {
    background: #161b22; border: 1px solid #30363d !important;
    border-radius: 8px; margin-bottom: 0.5rem;
}
hr { border-color: #21262d !important; }
textarea {
    background: #0d1117 !important; border: 1px solid #30363d !important;
    color: #c9d1d9 !important; border-radius: 8px !important;
}

/* Hide Streamlit's own sidebar nav */
[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Page state ────────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "analyser"

# ── Nav bar with buttons ──────────────────────────────────────────────────────
col_brand, col_nav = st.columns([2, 3])
with col_brand:
    st.markdown("<div class='topnav-brand' style='padding:0.9rem 0 0;'>FinSight</div>", unsafe_allow_html=True)

with col_nav:
    n1, n2, n3, _ = st.columns([1, 1, 1, 2])
    with n1:
        if st.button("Analyser", key="nav_analyser",
                     type="primary" if st.session_state.page == "analyser" else "secondary",
                     use_container_width=True):
            st.session_state.page = "analyser"
            st.rerun()
    with n2:
        if st.button("Features", key="nav_features",
                     type="primary" if st.session_state.page == "features" else "secondary",
                     use_container_width=True):
            st.session_state.page = "features"
            st.rerun()
    with n3:
        if st.button("Pricing", key="nav_pricing",
                     type="primary" if st.session_state.page == "pricing" else "secondary",
                     use_container_width=True):
            st.session_state.page = "pricing"
            st.rerun()

st.divider()

# ── Route to correct page ─────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pages"))

if st.session_state.page == "analyser":
    import analyser
    analyser.show()
elif st.session_state.page == "features":
    import features
    features.show()
elif st.session_state.page == "pricing":
    import pricing
    pricing.show()
