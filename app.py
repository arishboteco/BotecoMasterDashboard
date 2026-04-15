"""BotecoMasterDashboard — Main Streamlit application entry point."""

from __future__ import annotations

import os
import streamlit as st
from datetime import datetime

import config
import database
import boteco_logger
import styles
import ui_theme
import auth
from tabs import TabContext
from tabs.upload_tab import render as render_upload
from tabs.report_tab import render as render_report
from tabs.analytics_tab import render as render_analytics
from tabs.settings_tab import render as render_settings

boteco_logger.setup_logging()
ui_theme.apply_plotly_theme()

# Warn if Supabase mode is requested but credentials are missing
if os.environ.get("USE_SUPABASE") and not config.SUPABASE_KEY:
    st.error(
        "⚠️ USE_SUPABASE is set but SUPABASE_KEY is empty. "
        "Set the SUPABASE_URL, SUPABASE_KEY, and SUPABASE_SERVICE_KEY environment variables."
    )
    st.stop()

if "bootstrapped" not in st.session_state:
    database.bootstrap()
    database.backfill_weekday_weighted_targets()
    st.session_state["bootstrapped"] = True

# Bootstrap admin user if none exists
with database.db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users")
    user_count = cursor.fetchone()["count"]

    if user_count == 0:
        import bcrypt
        import secrets

        generated_pw = secrets.token_urlsafe(16)
        hashed = bcrypt.hashpw(generated_pw.encode("utf-8"), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hashed.decode("utf-8"), "admin"),
        )
        conn.commit()

        # Set session state for admin (will get location from Settings)
        st.session_state.authenticated = True
        st.session_state.username = "admin"
        st.session_state.user_role = "admin"
        st.session_state.location_id = 1
        st.session_state.location_name = None
        st.session_state.view_scope = "all"
        st.session_state["_first_run_password"] = generated_pw

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
    except Exception:
        pass
    st.json({"status": "ok" if db_ok else "degraded", "database": db_type})
    st.stop()

# Apply centralized CSS
st.markdown(styles.get_css(), unsafe_allow_html=True)

# Initialize authentication
auth.init_auth_state()

# Show first-run admin password exactly once
if "_first_run_password" in st.session_state:
    st.warning(
        f"🔐 **First-run admin password:** `{st.session_state['_first_run_password']}`\n\n"
        "Change this immediately in **Settings > Change Password**. "
        "This message will not appear again."
    )
    del st.session_state["_first_run_password"]

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
        f'<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">'
        f'<span class="sidebar-user-initials">{initials}</span>'
        f'<div><div style="font-weight:600;color:#fff;font-size:0.9rem;line-height:1.2;">{username}</div>'
        f'<div style="font-size:0.72rem;color:rgba(255,255,255,0.6);text-transform:uppercase;letter-spacing:0.06em;">{role}</div></div>'
        f'</div>'
        f'<div style="font-size:0.78rem;color:rgba(255,255,255,0.75);display:flex;align-items:center;gap:0.35rem;">'
        f'<span style="opacity:0.6;">📍</span>{location_name}</div>'
        f'</div>',
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
        '<div style="position:absolute;bottom:1rem;left:0;right:0;text-align:center;">'
        '<span style="font-size:0.68rem;color:rgba(255,255,255,0.3);letter-spacing:0.04em;">Boteco Dashboard · v1.0</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Build shared context
    import_loc_id = int(st.session_state.location_id)
    import_location_settings = database.get_location_settings(import_loc_id)

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
    tab1, tab2, tab3, tab4 = st.tabs(["⬆ Upload", "📊 Report", "📈 Analytics", "⚙ Settings"])

    with tab1:
        render_upload(ctx)
    with tab2:
        render_report(ctx)
    with tab3:
        render_analytics(ctx)
    with tab4:
        render_settings(ctx)
