"""BotecoMasterDashboard — Main Streamlit application entry point."""

from __future__ import annotations

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
database.bootstrap()

# Hardcode admin user if none exists
with database.db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users")
    user_count = cursor.fetchone()["count"]

    if user_count == 0:
        import bcrypt

        hashed = bcrypt.hashpw("admin".encode("utf-8"), bcrypt.gensalt())
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

# Page configuration
st.set_page_config(
    page_title="Boteco Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    st.sidebar.markdown("##### Account")
    username = st.session_state.username or "User"
    initials = username[:2].upper() if username else "U"
    st.sidebar.markdown(
        f'<div style="display:flex;align-items:center;gap:0.4rem;margin-bottom:0.25rem;">'
        f'<span style="width:28px;height:28px;border-radius:50%;background:rgba(255,255,255,0.2);'
        f"display:inline-flex;align-items:center;justify-content:center;font-size:0.8rem;"
        f'font-weight:600;color:#fff;">{initials}</span>'
        f'<span style="font-weight:500;color:#fff;">{username}</span></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"**Role:** {st.session_state.user_role}")
    st.sidebar.caption(f"**Location:** {st.session_state.location_name or 'Default'}")
    st.sidebar.divider()
    st.sidebar.markdown("##### Reports & scope")
    st.sidebar.caption("Daily Report and Analytics use this scope.")

    report_loc_ids = auth.get_report_location_ids()
    report_display_name = auth.get_report_display_name()
    all_locs = database.get_all_locations()
    if len(all_locs) > 1 and auth.is_admin():
        options = ["all"] + [
            str(loc["id"]) for loc in sorted(all_locs, key=lambda x: x["name"])
        ]

        def _scope_label(k: str) -> str:
            if k == "all":
                return "All locations"
            for loc in all_locs:
                if str(loc["id"]) == k:
                    return str(loc["name"])
            return k

        vs = st.session_state.get("view_scope")
        if vs not in options:
            st.session_state.view_scope = "all"
            vs = "all"
        ix = options.index(vs)
        choice = st.sidebar.selectbox(
            "Report scope",
            options=options,
            index=ix,
            format_func=_scope_label,
            key="sidebar_report_scope",
        )
        st.session_state.view_scope = choice
    else:
        st.session_state.view_scope = str(st.session_state.location_id)

    location_id = st.session_state.location_id

    st.sidebar.divider()
    if st.sidebar.button("Logout", key="sidebar_logout_btn", use_container_width=True):
        auth.logout()

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
    tab1, tab2, tab3, tab4 = st.tabs(["Upload", "Report", "Analytics", "Settings"])

    with tab1:
        render_upload(ctx)
    with tab2:
        render_report(ctx)
    with tab3:
        render_analytics(ctx)
    with tab4:
        render_settings(ctx)
