"""BotecoMasterDashboard — Main Streamlit application entry point."""

from __future__ import annotations

import streamlit as st

import auth
import boteco_logger
import config
import database
import styles
import ui_theme
from tabs import TabContext
from tabs.analytics_tab import render as render_analytics
from tabs.footfall_tab import render as render_footfall
from tabs.report_tab import render as render_report
from tabs.settings_tab import render as render_settings
from tabs.upload_tab import render as render_upload

boteco_logger.setup_logging()
logger = boteco_logger.get_logger(__name__)
ui_theme.apply_plotly_theme()

# Supabase is the single source of truth in deployment.
# Fail fast at startup instead of silently falling back to SQLite.
if not config.SUPABASE_URL or not config.SUPABASE_KEY:
    st.error(
        "⚠️ Supabase is required but credentials are missing. "
        "Set SUPABASE_URL, SUPABASE_KEY, and SUPABASE_SERVICE_KEY."
    )
    st.stop()

if not database.use_supabase():
    st.error(
        "⚠️ Supabase is required but connection could not be initialized. "
        "Check credentials/network and restart."
    )
    st.stop()

if "bootstrapped" not in st.session_state:
    database.bootstrap()
    database.backfill_weekday_weighted_targets()
    # Bootstrap admin user if missing — only on first render of the session,
    # otherwise this re-hits the DB on every rerun.
    database.create_admin_user("admin", "admin")
    st.session_state["bootstrapped"] = True

# Page configuration
st.set_page_config(
    page_title="Boteco Dashboard",
    page_icon="logo.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Health check endpoint — returns JSON status for monitoring
if st.query_params.get("health") == "check":
    db_ok = False
    db_type = "unknown"
    try:
        if database.use_supabase():
            db_type = "supabase"
            client = database.get_supabase_client()
            client.table("locations").select("id").limit(1).execute()
            db_ok = True
        else:
            db_type = "sqlite"
            with database.db_connection() as _conn:
                _conn.cursor().execute("SELECT 1")
            db_ok = True
    except (ConnectionError, OSError, RuntimeError, ValueError) as ex:
        logger.warning(
            "Health check failed for db_type=%s path=app.py error=%s",
            db_type,
            ex,
        )
    st.json({"status": "ok" if db_ok else "degraded", "database": db_type})
    st.stop()

# Apply centralized CSS
st.markdown(styles.get_css(), unsafe_allow_html=True)

# Initialize authentication
auth.init_auth_state()


if not auth.check_authentication():
    auth.show_login_form()
else:
    st.sidebar.image("logo.png", width=180)

    st.sidebar.divider()

    # Account section with user badge
    username = st.session_state.username or "User"
    initials = username[:2].upper() if username else "U"
    role = st.session_state.user_role or "user"
    location_name = st.session_state.location_name or "Default"
    st.sidebar.markdown(
        f'<div class="sidebar-account-section">'
        f'<div class="sidebar-account-row">'
        f'<span class="sidebar-user-initials">{initials}</span>'
        f'<div><div class="user-name">{username}</div>'
        f'<div class="role-label">{role}</div></div>'
        f"</div>"
        f'<div class="location-row">'
        f'<span class="location-pin">📍</span>{location_name}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    report_loc_ids = auth.get_report_location_ids()
    report_display_name = auth.get_report_display_name()
    all_locs = database.get_all_locations()

    location_id = st.session_state.location_id

    st.sidebar.divider()
    if st.sidebar.button("Logout", key="sidebar_logout_btn", width="stretch"):
        auth.logout()

    st.sidebar.markdown(
        '<div class="sidebar-footer">'
        '<span class="sidebar-footer-text">Boteco Dashboard · v1.0</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    # Build shared context
    import_loc_id = int(st.session_state.location_id)
    location_settings = database.get_location_settings(location_id)
    if import_loc_id == location_id:
        import_location_settings = location_settings
    else:
        import_location_settings = database.get_location_settings(import_loc_id)

    ctx = TabContext(
        location_id=location_id,
        import_loc_id=import_loc_id,
        report_loc_ids=report_loc_ids,
        report_display_name=report_display_name,
        all_locs=all_locs,
        location_settings=location_settings,
        import_location_settings=import_location_settings,
    )

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Upload", "Report", "Analytics", "Footfall", "Settings"]
    )

    with tab1:
        render_upload(ctx)
    with tab2:
        render_report(ctx)
    with tab3:
        render_analytics(ctx)
    with tab4:
        render_footfall(ctx)
    with tab5:
        render_settings(ctx)
