"""BotecoMasterDashboard — Main Streamlit application entry point."""

from __future__ import annotations

import streamlit as st
from datetime import datetime

import config
import database
import logger as boteco_logger
import ui_theme
import auth
from tabs import TabContext
from tabs.upload_tab import render as render_upload
from tabs.report_tab import render as render_report
from tabs.analytics_tab import render as render_analytics
from tabs.settings_tab import render as render_settings

boteco_logger.setup_logging()
ui_theme.apply_plotly_theme()
database.bootstrap()

# Page configuration
st.set_page_config(
    page_title="Boteco Dashboard",
    page_icon="🥂",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS (warm editorial theme — tokens align with .streamlit/config.toml)
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300..700;1,9..40,300..700&display=swap');

    :root {
        --brand: #C2703E;
        --brand-dark: #A45A2E;
        --brand-soft: #F5EAE0;
        --surface: #FAF6F1;
        --surface-elevated: #FFF8F0;
        --text: #3D2B1F;
        --text-muted: #8C7B6B;
        --border-subtle: #E0D5C8;
        --success-bg: #EDF2E8;
        --success-text: #3D5A2E;
        --success-border: #D4DFC9;
        --error-bg: #F5E8E6;
        --error-text: #7A2E22;
        --error-border: #E8CFCB;
        --font-display: 'DM Serif Display', serif;
        --font-body: 'DM Sans', sans-serif;
    }

    /* ── Typography ─────────────────────────────────────────── */
    html, body, [class*="st-"], .stMarkdown, p, li, span, label,
    [data-testid="stText"], input, textarea, select {
        font-family: var(--font-body) !important;
    }
    h1, h2, h3, .main-header,
    [data-testid="stHeadingWithActionElements"] {
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        letter-spacing: -0.01em;
    }
    button[data-baseweb="tab"] {
        font-family: var(--font-display) !important;
        font-size: 1.05rem !important;
        letter-spacing: 0.01em;
    }

    /* ── Components ─────────────────────────────────────────── */
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: var(--brand) !important;
    }
    .stCaption, [data-testid="stCaption"] {
        color: var(--text-muted);
    }

    /* ── KPI metric values — high-contrast dark text ─────────── */
    div[data-testid="stMetricValue"] {
        color: var(--text);
        font-weight: 700;
    }

    /* ── Metric cards inside bordered containers ──────────────── */
    .metric-card {
        background: var(--surface);
        padding: 1rem;
        border-radius: 14px;
        border-left: 4px solid var(--brand);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border-color: var(--border-subtle) !important;
        border-radius: 14px !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        background: var(--surface-elevated);
        border-radius: 10px;
        box-shadow: 0 1px 4px rgba(60,40,20,0.06);
        border: 1px solid var(--border-subtle);
    }

    /* ── Alert / status boxes ─────────────────────────────────── */
    .success-box {
        background: var(--success-bg);
        color: var(--success-text);
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid var(--success-border);
    }
    .error-box {
        background: var(--error-bg);
        color: var(--error-text);
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid var(--error-border);
    }

    /* ── Upload zone ──────────────────────────────────────────── */
    .upload-zone {
        border: 2px dashed var(--brand);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        text-align: left;
        background: var(--brand-soft);
        margin-bottom: 0.75rem;
    }
    .empty-upload-hint {
        color: var(--text-muted);
        font-size: 0.95rem;
        padding: 0.75rem 1rem;
        background: var(--surface);
        border-radius: 10px;
        border: 1px dashed var(--border-subtle);
        margin-top: 0.5rem;
    }

    /* ── Sidebar ──────────────────────────────────────────────── */
    [data-testid="stSidebar"] hr {
        margin: 0.75rem 0;
    }

    /* ── Expander labels — prevent arrow/text overlap ─────────── */
    [data-testid="stExpander"] summary {
        gap: 0.5rem;
        align-items: center;
    }
    [data-testid="stExpander"] summary p {
        margin: 0;
        overflow: visible;
    }

    /* ── Consistent dataframe table headers ───────────────────── */
    [data-testid="stDataFrame"] th {
        font-weight: 600 !important;
        color: var(--text) !important;
        background-color: var(--surface) !important;
        border-bottom: 2px solid var(--border-subtle) !important;
    }

    /* ── Buttons ────────────────────────────────────────────── */
    .stButton > button {
        font-family: var(--font-body) !important;
        border-radius: 10px !important;
    }
    .stButton > button[kind="primary"] {
        background-color: var(--brand) !important;
        color: #FFF8F0 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--brand-dark) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize authentication
auth.init_auth_state()

# Check if setup is needed
conn = database.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as count FROM users")
user_count = cursor.fetchone()["count"]
conn.close()

if user_count == 0:
    auth.show_setup_form()
else:
    if not auth.check_authentication():
        auth.show_login_form()
    else:
        # Render sidebar
        auth.render_auth_sidebar()
        st.sidebar.divider()
        st.sidebar.markdown("##### POS import")

        report_loc_ids = auth.get_report_location_ids()
        report_display_name = auth.get_report_display_name()
        all_locs = database.get_all_locations()
        if len(all_locs) > 1 and auth.is_admin():
            imp_labels = {
                str(loc["id"]): loc["name"]
                for loc in sorted(all_locs, key=lambda x: x["name"])
            }
            imp_keys = list(imp_labels.keys())
            default_imp = str(st.session_state.location_id)
            if default_imp not in imp_keys:
                default_imp = imp_keys[0]
            import_loc_id = int(
                st.sidebar.selectbox(
                    "POS import for",
                    options=imp_keys,
                    index=imp_keys.index(default_imp),
                    format_func=lambda k: imp_labels[k],
                    key="sidebar_import_location",
                )
            )
        elif len(all_locs) > 1:
            import_loc_id = int(st.session_state.location_id)
            imp_name = st.session_state.location_name or "your location"
            for loc in all_locs:
                if loc["id"] == import_loc_id:
                    imp_name = loc["name"]
                    break
            st.sidebar.caption(f"POS imports save to **{imp_name}**.")
        else:
            import_loc_id = (
                all_locs[0]["id"] if all_locs else st.session_state.location_id
            )

        import_location_settings = database.get_location_settings(import_loc_id)
        location_id = st.session_state.location_id

        # Build shared context
        ctx = TabContext(
            location_id=location_id,
            import_loc_id=import_loc_id,
            report_loc_ids=report_loc_ids,
            report_display_name=report_display_name,
            all_locs=all_locs,
            location_settings=database.get_location_settings(location_id),
            import_location_settings=import_location_settings,
        )

        # Tabs
        tab1, tab2, tab3, tab4 = st.tabs(["Upload", "Report", "Analytics", "Settings"])

        with tab1:
            render_upload(ctx)
        with tab2:
            render_report(ctx)
        with tab3:
            render_analytics(ctx)
        with tab4:
            render_settings(ctx)
