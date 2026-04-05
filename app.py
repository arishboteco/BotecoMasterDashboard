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
        # Sidebar branding
        st.sidebar.image("logo.png", width=180)
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
