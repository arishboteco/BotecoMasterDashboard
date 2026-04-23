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

# Detect and propagate Streamlit's active theme to the CSS token system.
# Streamlit sets --streamlit-variant as a CSS custom property on the body.
# We mirror it as data-theme on <html> so all :root[data-theme="dark"] { … }
# CSS rules in styles/_tokens.py activate automatically.
_theme_script = """
<script id="boteco-theme-sync">
(function() {
    function applyTheme(dark) {
        document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    }

    function detect() {
        // Primary: Streamlit's --streamlit-variant custom property (Streamlit 1.33+)
        var variant = getComputedStyle(document.body).getPropertyValue('--streamlit-variant').trim();
        if (variant === 'dark') { applyTheme(true); return; }
        if (variant === 'light') { applyTheme(false); return; }
        // Fallback: class on .stApp
        var app = document.querySelector('.stApp');
        if (app && (app.getAttribute('data-theme') === 'dark' || app.className.includes('dark'))) {
            applyTheme(true); return;
        }
        // System preference fallback
        applyTheme(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    }

    detect();
    if (window.MutationObserver) {
        new MutationObserver(detect).observe(
            document.body,
            { attributes: true, attributeFilter: ['data-theme', 'class'], subtree: false }
        );
    }
})();
</script>"""
st.markdown(_theme_script, unsafe_allow_html=True)

# Initialize authentication
auth.init_auth_state()


if not auth.check_authentication():
    auth.show_login_form()
else:
    st.sidebar.image("logo.png", width=180)

    st.sidebar.caption("Theme: use ⋮ -> Settings -> Theme")

    # Switch Plotly template to match active Streamlit theme.
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

    import plotly.io as _pio

    _pio.templates.default = ui_theme.plotly_template_for_theme(
        "dark" if _theme == "dark" else "light"
    )

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
            _new = st.session_state.get("sidebar_outlet_switcher", "all")
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
