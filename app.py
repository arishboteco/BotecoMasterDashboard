"""BotecoMasterDashboard — Main Streamlit application entry point."""

from __future__ import annotations

import os
import streamlit as st
import streamlit.components.v1 as _components
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

        default_pw = "admin"
        hashed = bcrypt.hashpw(default_pw.encode("utf-8"), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hashed.decode("utf-8"), "admin"),
        )
        conn.commit()

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

# Detect active Streamlit theme (light/dark) from context or ?theme= param.
# Runs before the auth check so the login page also gets a correct data-theme.
_theme = "light"
_context = getattr(st, "context", None)
_context_theme = getattr(_context, "theme", None)
_context_theme_type = getattr(_context_theme, "type", None)
if _context_theme_type in {"light", "dark"}:
    _theme = _context_theme_type
else:
    _query_theme = st.query_params.get("theme")
    if _query_theme in {"light", "dark"}:
        _theme = _query_theme

# Store for clipboard_ui and other components that need it.
st.session_state["theme"] = _theme

# Activate CSS token dark-mode branch by setting data-theme on <html>.
# Uses a sandboxed component iframe; window.parent is the Streamlit app frame.
# The script is defensive: (1) try window.parent first, fall back to window.top
# for deeply-nested iframe hosts, (2) short-circuit when the attribute is
# already correct so we don't churn the cascade, (3) swallow cross-origin
# access errors silently instead of dropping the rest of the rerun.
_components.html(
    "<script>"
    "(function(){"
    f'var t="{_theme}";'
    "function apply(doc){"
    'if(doc.getAttribute("data-theme")!==t){'
    'doc.setAttribute("data-theme",t);'
    "}"
    "}"
    "try{apply(window.parent.document.documentElement);return;}catch(e){}"
    "try{apply(window.top.document.documentElement);}catch(e){}"
    "})();"
    "</script>",
    height=0,
)

import plotly.io as _pio

_pio.templates.default = ui_theme.plotly_template_for_theme(
    "dark" if _theme == "dark" else "light"
)

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
        f'</div>'
        f'<div class="location-row">'
        f'<span class="location-pin">📍</span>{location_name}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    report_loc_ids = auth.get_report_location_ids()
    report_display_name = auth.get_report_display_name()
    all_locs = database.get_all_locations()

    # ── Admin outlet quick-switcher ──────────────────────────────
    if auth.is_admin() and all_locs and len(all_locs) > 1:
        st.sidebar.markdown("##### Outlet")
        _outlet_options = ["all"] + [
            str(_loc["id"]) for _loc in sorted(all_locs, key=lambda x: x["name"])
        ]

        def _outlet_label(k: str) -> str:
            if k == "all":
                return "All outlets"
            for _loc in all_locs:
                if str(_loc["id"]) == k:
                    return str(_loc["name"])
            return k

        _current = st.session_state.get("view_scope") or "all"
        if _current not in _outlet_options:
            _current = "all"
        _idx = _outlet_options.index(_current)

        def _on_outlet_change():
            # Streamlit fires on_script_will_rerun callbacks before the widget
            # is remounted; if session_state was cleared (login/logout, etc.)
            # the key may be missing. Bail out silently in that case.
            _new = st.session_state.get("sidebar_outlet_switcher")
            if _new is None:
                return
            st.session_state.view_scope = _new
            if _new != "all":
                try:
                    _nid = int(_new)
                    st.session_state.location_id = _nid
                    for _loc in all_locs:
                        if _loc["id"] == _nid:
                            st.session_state.location_name = _loc["name"]
                            break
                except (TypeError, ValueError):
                    pass

        st.sidebar.selectbox(
            "Outlet",
            options=_outlet_options,
            index=_idx,
            format_func=_outlet_label,
            key="sidebar_outlet_switcher",
            on_change=_on_outlet_change,
            label_visibility="collapsed",
        )
        # Refresh derived values after potential change
        report_loc_ids = auth.get_report_location_ids()
        report_display_name = auth.get_report_display_name()

    location_id = st.session_state.location_id

    st.sidebar.divider()
    if st.sidebar.button("Logout", key="sidebar_logout_btn", width="stretch"):
        auth.logout()

    st.sidebar.markdown(
        '<div class="sidebar-footer">'
        '<span class="sidebar-footer-text">Boteco Dashboard · v1.0</span>'
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
