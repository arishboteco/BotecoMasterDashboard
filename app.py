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
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&display=swap');

    /* Force system fonts for Streamlit expander icons */
    section[data-testid="stExpander"] * {
        font-family: inherit !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] button {
        font-family: inherit !important;
    }
    summary {
        font-family: inherit !important;
    }

    :root {
        --brand: #E8734A;
        --brand-dark: #D4612E;
        --brand-light: #F0936E;
        --brand-soft: #FEF0EB;
        --surface: #FFFFFF;
        --surface-elevated: #F8F9FB;
        --surface-raised: #FFFFFF;
        --sidebar-bg: #F1F3F7;
        --sidebar-border: #E2E8F0;
        --text: #1E293B;
        --text-secondary: #475569;
        --text-muted: #94A3B8;
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;
        --success-bg: #F0FDF4;
        --success-text: #15803D;
        --success-border: #BBF7D0;
        --error-bg: #FEF2F2;
        --error-text: #B91C1C;
        --error-border: #FECACA;
        --info-bg: #EFF6FF;
        --info-text: #4338CA;
        --info-border: #C7D2FE;
        --font-display: 'Sora', sans-serif;
        --font-body: 'DM Sans', sans-serif;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -2px rgba(0,0,0,0.05);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);
        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;
        --btn-height-sm: 32px;
        --btn-height-md: 40px;
        --btn-height-lg: 48px;
        --btn-padding-x: 1rem;
        --btn-padding-y: 0.5rem;
        --icon-size: 18px;
        --accent-coral: #E8734A;
        --accent-teal: #0D9488;
        --accent-amber: #D97706;
        --accent-indigo: #6366F1;
        --accent-slate: #334155;
    }

    /* ── Base typography ────────────────────────────────────── */
    .stMarkdown p, .stMarkdown li, .stMarkdown span, .stMarkdown label,
    [data-testid="stText"] p, [data-testid="stText"] li, [data-testid="stText"] span,
    .stTextInput input, .stTextArea textarea, .stSelectbox select,
    .stNumberInput input {
        font-family: var(--font-body) !important;
    }
    h1, h2, h3, h4 {
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        margin-bottom: 0.5em !important;
    }
    h1 { font-size: 1.85rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
    h2 { font-size: 1.4rem !important; font-weight: 600 !important; letter-spacing: -0.01em !important; }
    h3 {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        padding-left: 0.75rem !important;
        border-left: 3px solid var(--brand) !important;
    }
    h4 { font-size: 1.05rem !important; font-weight: 600 !important; }
    button[data-baseweb="tab"] {
        font-family: var(--font-body) !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em;
        padding: 0.75rem 1.25rem !important;
        color: var(--text-muted) !important;
        transition: color 0.2s ease, background-color 0.2s ease !important;
    }
    button[data-baseweb="tab"]:hover {
        color: var(--brand) !important;
        background-color: var(--brand-soft) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--brand) !important;
        font-weight: 600 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: var(--brand) !important;
    }
    [data-testid="stTabs"] [role="tablist"] {
        border-bottom: 2px solid var(--border-subtle);
        gap: 0;
    }
    .stCaption, [data-testid="stCaption"], caption {
        color: var(--text-muted) !important;
        font-size: 0.85rem !important;
        font-family: var(--font-body) !important;
    }

    /* ── Branded header ─────────────────────────────────────── */
    .boteco-header {
        display: flex;
        align-items: baseline;
        gap: 0.5rem;
        padding-bottom: 0.75rem;
        margin-bottom: 0.25rem;
        border-bottom: 2px solid var(--border-subtle);
    }
    .boteco-header-name {
        font-family: var(--font-display);
        font-weight: 700;
        font-size: 1.5rem;
        color: var(--brand);
        letter-spacing: -0.02em;
    }
    .boteco-header-dot {
        color: var(--brand);
        font-size: 1.5rem;
        line-height: 1;
    }
    .boteco-header-sub {
        font-family: var(--font-body);
        font-weight: 500;
        font-size: 0.9rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    /* ── Button system ──────────────────────────────────────── */
    .stButton > button {
        font-family: var(--font-body) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        min-height: var(--btn-height-md) !important;
        line-height: 1.4 !important;
        padding: var(--btn-padding-y) var(--btn-padding-x) !important;
    }
    .stButton > button:active {
        transform: scale(0.98) !important;
        transition: transform 0.05s ease !important;
    }
    .stButton > button[kind="primary"] {
        background-color: var(--brand) !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: var(--shadow-sm) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--brand-dark) !important;
        box-shadow: var(--shadow-md) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: var(--surface) !important;
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
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        font-weight: 700 !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
    }
    div[data-testid="stMetricLabel"] {
        font-family: var(--font-body) !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        font-size: 0.75rem !important;
        letter-spacing: 0.03em;
    }
    div[data-testid="stMetricDelta"] {
        font-family: var(--font-body) !important;
        font-weight: 600 !important;
    }

    /* ── Metric cards & containers ──────────────────────────── */
    .metric-card {
        background: var(--surface);
        padding: 1rem;
        border-radius: var(--radius-md);
        border-left: 4px solid var(--brand);
        box-shadow: var(--shadow-sm);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border-color: var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-sm) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: var(--shadow-md) !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        background: var(--surface);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-subtle);
        border-left: 4px solid var(--accent-coral);
        padding: 0.85rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    /* Differentiated metric accent colors by position */
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stMetric"] {
        border-left-color: var(--accent-coral);
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"] {
        border-left-color: var(--accent-teal);
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stMetric"] {
        border-left-color: var(--accent-amber);
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stMetric"] {
        border-left-color: var(--accent-indigo);
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] > div:nth-child(5) [data-testid="stMetric"] {
        border-left-color: var(--accent-slate);
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
        background: var(--surface);
        margin-bottom: 0.75rem;
        transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
    }
    .upload-zone:hover {
        border-color: var(--brand-dark);
        background: var(--brand-soft);
        box-shadow: 0 0 0 4px rgba(232,115,74,0.1);
        transform: translateY(-1px);
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
        font-family: var(--font-body) !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        color: #FFFFFF !important;
        background-color: #334155 !important;
        border-bottom: none !important;
    }
    [data-testid="stDataFrame"] {
        border-radius: var(--radius-md) !important;
        overflow: hidden !important;
        border: 1px solid var(--border-subtle) !important;
    }
    [data-testid="stDataFrame"] td {
        font-family: var(--font-body) !important;
        font-size: 0.875rem !important;
    }
    [data-testid="stDataFrame"] tr:nth-child(even) {
        background-color: var(--surface-elevated) !important;
    }
    [data-testid="stDataFrame"] tr:hover {
        background-color: var(--brand-soft) !important;
    }

    /* ── Expander labels ────────────────────────────────────── */
    [data-testid="stExpander"] {
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        gap: 0.65rem;
        align-items: center;
        padding: 0.5rem 0.75rem;
        border-radius: var(--radius-sm);
        transition: background-color 0.2s ease;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: var(--brand-soft);
    }
    [data-testid="stExpander"] summary p {
        margin: 0;
        overflow: visible;
        line-height: 1.5;
        font-family: var(--font-body) !important;
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
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }
    [data-testid="stSidebar"] hr {
        margin: 1rem 0;
        border-color: var(--border-subtle);
    }
    [data-testid="stSidebar"]::before {
        content: '';
        display: block;
        height: 3px;
        background: linear-gradient(90deg, var(--brand), var(--accent-amber));
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1;
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
        font-family: var(--font-display);
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--text);
        text-align: center;
        min-width: 200px;
        padding: 0.5rem 1.25rem;
        background: var(--surface);
        border-radius: var(--radius-md);
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
        font-family: var(--font-body);
        font-weight: 600;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s ease;
        white-space: nowrap;
        line-height: 1.3;
        min-height: var(--btn-height-md);
    }
    .whatsapp-btn-primary {
        background: var(--brand);
        color: #FFFFFF;
        border: none;
        box-shadow: var(--shadow-sm);
    }
    .whatsapp-btn-primary:hover {
        background: var(--brand-dark);
        box-shadow: var(--shadow-md);
    }
    .whatsapp-btn-secondary {
        background: var(--surface);
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
        background: var(--surface);
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
        transition: all 0.2s ease;
        border: none;
        background: transparent;
        color: var(--text-secondary);
        font-size: 0;
    }
    .action-btn-row .action-btn:hover {
        background: var(--brand-soft);
        color: var(--brand);
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
        min-height: 140px;
        border: 2px dashed var(--brand) !important;
        border-radius: var(--radius-lg) !important;
        background: var(--surface) !important;
        transition: all 0.2s ease;
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--brand-dark) !important;
        background: var(--brand-soft) !important;
        box-shadow: 0 0 0 4px rgba(232,115,74,0.1) !important;
        transform: translateY(-1px);
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"] label {
        color: var(--text-secondary) !important;
        font-size: 0.95rem !important;
        font-family: var(--font-body) !important;
    }

    /* ── Section dividers ───────────────────────────────────── */
    .section-divider {
        border: none;
        height: 1px;
        background: linear-gradient(to right, transparent, var(--border-subtle), transparent);
        margin: 2rem 0;
    }

    /* ── Layout & spacing ──────────────────────────────────── */
    .main .block-container {
        max-width: 1200px;
        padding: 1.5rem 2rem 2rem !important;
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

    /* ── Focus rings ───────────────────────────────────────── */
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox [data-baseweb="select"]:focus-within {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(232,115,74,0.15) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Mount cookie component on every render (must precede conditional branches)
auth._get_cookie_manager()

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

        # Branded header
        st.markdown(
            '<div class="boteco-header">'
            '<span class="boteco-header-name">Boteco</span>'
            '<span class="boteco-header-dot">&middot;</span>'
            '<span class="boteco-header-sub">Dashboard</span>'
            '</div>',
            unsafe_allow_html=True,
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
