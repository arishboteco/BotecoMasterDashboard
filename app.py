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
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS (clean white theme with blue accent — tokens align with .streamlit/config.toml)
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300..700;1,9..40,300..700&display=swap');

    :root {
        --brand: #2563EB;
        --brand-dark: #1D4ED8;
        --brand-light: #3B82F6;
        --brand-soft: #DBEAFE;
        --surface: #FFFFFF;
        --surface-elevated: #F8FAFC;
        --surface-raised: #FFFFFF;
        --text: #0F172A;
        --text-secondary: #475569;
        --text-muted: #94A3B8;
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;
        --success-bg: #F0FDF4;
        --success-text: #166534;
        --success-border: #BBF7D0;
        --error-bg: #FEF2F2;
        --error-text: #7F1D1D;
        --error-border: #FECACA;
        --info-bg: #EFF6FF;
        --info-text: #1E40AF;
        --info-border: #BFDBFE;
        --font-display: 'DM Serif Display', serif;
        --font-body: 'DM Sans', sans-serif;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
        --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;
        --btn-height-sm: 32px;
        --btn-height-md: 40px;
        --btn-height-lg: 48px;
        --btn-padding-x: 1rem;
        --btn-padding-y: 0.5rem;
        --icon-size: 18px;
    }

    /* ── Base typography ────────────────────────────────────── */
    html, body, [class*="st-"], .stMarkdown, p, li, span, label,
    [data-testid="stText"], input, textarea, select {
        font-family: var(--font-body) !important;
    }
    h1, h2, h3, h4, h5, h6,
    .main-header,
    [data-testid="stHeadingWithActionElements"] {
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        letter-spacing: -0.01em;
        margin-bottom: 0.5em !important;
    }
    h1 { font-size: 2rem !important; }
    h2 { font-size: 1.5rem !important; }
    h3 { font-size: 1.25rem !important; }
    h4 { font-size: 1.1rem !important; }
    button[data-baseweb="tab"] {
        font-family: var(--font-display) !important;
        font-size: 1.05rem !important;
        letter-spacing: 0.01em;
    }
    .stCaption, [data-testid="stCaption"], caption {
        color: var(--text-muted) !important;
        font-size: 0.85rem !important;
    }

    /* ── Header ─────────────────────────────────────────────── */
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: var(--brand) !important;
        position: relative;
        padding-bottom: 0.5rem;
    }
    .main-header::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 60px;
        height: 3px;
        background: var(--brand);
        border-radius: 2px;
    }

    /* ── Button system ──────────────────────────────────────── */
    .stButton > button {
        font-family: var(--font-body) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 500 !important;
        transition: all 0.15s ease-in-out !important;
        min-height: var(--btn-height-md) !important;
        line-height: 1.4 !important;
        padding: var(--btn-padding-y) var(--btn-padding-x) !important;
    }
    .stButton > button[kind="primary"] {
        background-color: var(--brand) !important;
        color: var(--surface-elevated) !important;
        border: none !important;
        box-shadow: var(--shadow-sm) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--brand-dark) !important;
        box-shadow: var(--shadow-md) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: var(--surface-elevated) !important;
        color: var(--text) !important;
        border: 1px solid var(--border-subtle) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: var(--brand-soft) !important;
        border-color: var(--brand) !important;
        color: var(--brand-dark) !important;
    }
    .stButton > button.destructive {
        background-color: transparent !important;
        color: var(--error-text) !important;
        border: 1.5px solid var(--error-border) !important;
    }
    .stButton > button.destructive:hover {
        background-color: var(--error-bg) !important;
        border-color: var(--error-text) !important;
    }
    .stButton > button.destructive:disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
    }

    /* ── KPI metric values ──────────────────────────────────── */
    div[data-testid="stMetricValue"] {
        color: var(--text) !important;
        font-weight: 700 !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
    }
    div[data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
    }
    div[data-testid="stMetricDelta"] {
        font-weight: 600 !important;
    }

    /* ── Metric cards & containers ──────────────────────────── */
    .metric-card {
        background: var(--surface-elevated);
        padding: 1rem;
        border-radius: var(--radius-md);
        border-left: 4px solid var(--brand);
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.15s ease;
    }
    .metric-card:hover {
        box-shadow: var(--shadow-md);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border-color: var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        background: var(--surface-elevated);
        border-radius: var(--radius-sm);
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-subtle);
        padding: 0.75rem;
        transition: box-shadow 0.15s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"]:hover {
        box-shadow: var(--shadow-md);
    }

    /* ── Alert / status boxes ───────────────────────────────── */
    .success-box {
        background: var(--success-bg);
        color: var(--success-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--success-border);
    }
    .error-box {
        background: var(--error-bg);
        color: var(--error-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--error-border);
    }
    .info-box {
        background: var(--info-bg);
        color: var(--info-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--info-border);
    }

    /* ── Upload zone ────────────────────────────────────────── */
    .upload-zone {
        border: 2px dashed var(--brand);
        border-radius: var(--radius-lg);
        padding: 1rem 1.25rem;
        text-align: left;
        background: var(--brand-soft);
        margin-bottom: 0.75rem;
        transition: border-color 0.15s ease, background-color 0.15s ease;
    }
    .upload-zone:hover {
        border-color: var(--brand-dark);
        background: #EFF6FF;
    }
    .empty-upload-hint {
        color: var(--text-muted);
        font-size: 0.95rem;
        padding: 0.75rem 1rem;
        background: var(--surface);
        border-radius: var(--radius-sm);
        border: 1px dashed var(--border-subtle);
        margin-top: 0.5rem;
    }

    /* ── Data tables ────────────────────────────────────────── */
    [data-testid="stDataFrame"] th {
        font-weight: 600 !important;
        color: var(--text) !important;
        background-color: var(--surface) !important;
        border-bottom: 2px solid var(--border-subtle) !important;
    }
    [data-testid="stDataFrame"] {
        border-radius: var(--radius-sm) !important;
        overflow: hidden !important;
        border: 1px solid var(--border-subtle) !important;
    }
    [data-testid="stDataFrame"] tr:nth-child(even) {
        background-color: var(--brand-soft) !important;
    }
    [data-testid="stDataFrame"] tr:hover {
        background-color: var(--surface) !important;
    }

    /* ── Expander labels ────────────────────────────────────── */
    [data-testid="stExpander"] summary {
        gap: 0.65rem;
        align-items: center;
        padding-left: 0.25rem;
        border-radius: var(--radius-sm);
        transition: background-color 0.15s ease;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: var(--brand-soft);
    }
    [data-testid="stExpander"] summary p {
        margin: 0;
        overflow: visible;
        line-height: 1.5;
    }
    [data-testid="stExpander"] svg {
        flex-shrink: 0;
        margin-right: 0.25rem;
        transition: transform 0.2s ease;
    }
    [data-testid="stExpander"][open] summary svg {
        transform: rotate(90deg);
    }

    /* ── Sidebar ────────────────────────────────────────────── */
    [data-testid="stSidebar"] hr {
        margin: 0.75rem 0;
        border-color: var(--border-subtle);
    }
    [data-testid="stSidebar"] {
        background-color: var(--surface) !important;
    }

    /* ── Date navigation ────────────────────────────────────── */
    .date-nav-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1rem;
        padding: 0.75rem 0;
    }
    .date-nav-btn {
        min-width: 90px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.4rem;
    }
    .date-display {
        font-family: var(--font-display), serif;
        font-size: 1.25rem;
        color: var(--text);
        text-align: center;
        min-width: 200px;
        padding: 0.5rem 1rem;
        background: var(--surface-elevated);
        border-radius: var(--radius-sm);
        border: 1px solid var(--border-subtle);
        box-shadow: var(--shadow-sm);
    }

    /* ── WhatsApp share buttons ─────────────────────────────── */
    .whatsapp-btn-container {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        min-height: var(--btn-height-md);
    }
    .whatsapp-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: var(--btn-padding-y) var(--btn-padding-x);
        border-radius: var(--radius-sm);
        font-weight: 600;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.15s ease;
        white-space: nowrap;
        line-height: 1.3;
        min-height: var(--btn-height-md);
    }
    .whatsapp-btn-primary {
        background: var(--brand);
        color: var(--surface-elevated);
        border: none;
        box-shadow: var(--shadow-sm);
    }
    .whatsapp-btn-primary:hover {
        background: var(--brand-dark);
        box-shadow: var(--shadow-md);
    }
    .whatsapp-btn-secondary {
        background: var(--surface-elevated);
        color: var(--text);
        border: 1px solid var(--border-subtle);
    }
    .whatsapp-btn-secondary:hover {
        background: var(--brand-soft);
        border-color: var(--brand);
        color: var(--brand-dark);
    }
    .whatsapp-icon {
        width: var(--icon-size);
        height: var(--icon-size);
        flex-shrink: 0;
    }
    .whatsapp-msg {
        font-size: 0.8rem;
        color: var(--success-text);
        margin-left: 0.5rem;
    }

    /* ── Icon-only action buttons ──────────────────────────── */
    .action-btn-row {
        display: inline-flex;
        align-items: center;
        gap: 0;
        background: var(--surface-elevated);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-sm);
        padding: 4px;
    }
    .action-btn-row .action-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        padding: 0;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.15s ease;
        border: none;
        background: transparent;
        color: #475569;
        font-size: 0;
    }
    .action-btn-row .action-btn:hover {
        background: var(--brand-soft);
        color: #2563EB;
    }
    .action-btn-row .action-btn + .action-btn {
        border-left: 1px solid var(--border-subtle);
    }
    .action-btn-row .action-btn svg {
        width: 18px;
        height: 18px;
        display: block;
    }

    /* ── Upload zone styling ───────────────────────────────── */
    .upload-zone-container {
        position: relative;
    }
    .upload-zone-container .stFileUploader > div:first-child {
        padding: 0 !important;
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"] {
        min-height: 120px;
        border: 2px dashed var(--brand) !important;
        border-radius: var(--radius-lg) !important;
        background: var(--brand-soft) !important;
        transition: all 0.15s ease;
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--brand-dark) !important;
        background: #EFF6FF !important;
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"] label {
        color: var(--text-secondary) !important;
        font-size: 0.95rem !important;
    }

    /* ── Section dividers ───────────────────────────────────── */
    .section-divider {
        border: none;
        height: 1px;
        background: linear-gradient(to right, transparent, var(--border-subtle), transparent);
        margin: 1.5rem 0;
    }

    /* ── Smooth transitions ─────────────────────────────────── */
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"],
    [data-testid="stVerticalBlockBorderWrapper"] {
        transition: all 0.15s ease;
    }

    /* ── Scrollbar styling ──────────────────────────────────── */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--surface);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb {
        background: var(--border-medium);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
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
