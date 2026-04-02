from typing import List
from datetime import datetime, timedelta

import streamlit as st
import database
from streamlit_cookies_controller import CookieController

_COOKIE_NAME = "boteco_session"
_COOKIE_EXPIRY_DAYS = 30


def _get_cookie_manager():
    """Return a CookieController instance, stored in session_state to avoid duplicate keys."""
    if "_cookie_manager" not in st.session_state:
        st.session_state._cookie_manager = CookieController(key="boteco_cookie_manager")
    return st.session_state._cookie_manager


def _apply_user_to_session(user: dict, token: str) -> None:
    """Populate session state from a verified user dict and token."""
    st.session_state.authenticated = True
    st.session_state.username = user["username"]
    st.session_state.user_role = user["role"]
    st.session_state.location_id = user.get("location_id") or 1
    st.session_state.location_name = user.get("location_name") or "Boteco"
    st.session_state.session_token = token
    if user.get("role") == "admin":
        st.session_state.view_scope = "all"
    else:
        st.session_state.view_scope = str(st.session_state.location_id)


def init_auth_state():
    """Initialize authentication state, restoring from cookie if available."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = None
    if "location_id" not in st.session_state:
        st.session_state.location_id = None
    if "location_name" not in st.session_state:
        st.session_state.location_name = None
    if "view_scope" not in st.session_state:
        st.session_state.view_scope = None
    if "session_token" not in st.session_state:
        st.session_state.session_token = None

    if st.session_state.authenticated:
        return  # already restored this server session

    cookie_mgr = _get_cookie_manager()
    token = cookie_mgr.get(_COOKIE_NAME)  # None on first render (JS not yet run)
    if token:
        user = database.validate_session_token(token)
        if user:
            _apply_user_to_session(user, token)
        else:
            cookie_mgr.remove(_COOKIE_NAME)  # stale/expired cookie


def show_login_form():
    """Show login form."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&display=swap');
        :root {
            --brand: #E8734A;
            --brand-dark: #D4612E;
            --login-surface: #FFFFFF;
            --login-border: #E2E8F0;
            --text: #1E293B;
        }
        .stApp {
            background: #FFFFFF !important;
        }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 2.5rem;
            background: var(--login-surface);
            border-radius: 14px;
            border: 1px solid var(--login-border);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
        }
        .stButton > button {
            width: 100%;
            background-color: var(--brand);
            color: #FFFFFF;
            border: none;
            padding: 0.75rem;
            border-radius: 10px;
            font-weight: 600;
            font-family: 'DM Sans', sans-serif;
            transition: all 0.2s ease;
        }
        .stButton > button:hover {
            background-color: var(--brand-dark);
            box-shadow: 0 4px 6px rgba(232, 115, 74, 0.2);
        }
        .stTextInput input:focus {
            border-color: var(--brand) !important;
            box-shadow: 0 0 0 3px rgba(232, 115, 74, 0.15) !important;
        }
        h1 {
            font-family: 'Sora', sans-serif !important;
            color: var(--brand) !important;
        }
        h3 {
            font-family: 'DM Sans', sans-serif !important;
            color: #475569 !important;
            font-weight: 500 !important;
            border-left: none !important;
            padding-left: 0 !important;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("Boteco Dashboard")
    st.markdown("### Restaurant Sales Management")
    st.caption("Internal use — your session is protected by login.")

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input(
            "Password", type="password", placeholder="Enter password"
        )
        submit = st.form_submit_button("Login")

        if submit:
            if username and password:
                user = database.verify_user(username, password)
                if user:
                    token = database.create_user_session(
                        user["id"], days=_COOKIE_EXPIRY_DAYS
                    )
                    cookie_mgr = _get_cookie_manager()
                    cookie_mgr.set(
                        _COOKIE_NAME,
                        token,
                        expires=_COOKIE_EXPIRY_DAYS * 24 * 3600,
                    )
                    _apply_user_to_session(user, token)
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            else:
                st.warning("Please enter both username and password")


def show_setup_form():
    """Show initial setup form for first-time users."""
    st.title("Boteco Dashboard - Setup")
    st.markdown("### Create Admin Account")
    st.caption("One-time setup — create the first admin and default location.")

    with st.form("setup_form"):
        st.text_input(
            "Username", key="setup_username", placeholder="Enter admin username"
        )
        st.text_input(
            "Password",
            key="setup_password",
            type="password",
            placeholder="Enter password",
        )
        st.text_input(
            "Confirm Password",
            key="setup_confirm",
            type="password",
            placeholder="Confirm password",
        )

        st.markdown("---")
        st.markdown("### Location Settings")
        st.text_input("Location Name", key="setup_location", value="Boteco - Indiqube")
        st.number_input(
            "Monthly Target (₹)",
            key="setup_target",
            min_value=0,
            value=5000000,
            step=100000,
            format="%d",
        )

        submit = st.form_submit_button("Create Account & Setup")

        if submit:
            username = st.session_state.setup_username
            password = st.session_state.setup_password
            confirm = st.session_state.setup_confirm

            if not username or not password:
                st.error("Username and password are required")
                return

            if password != confirm:
                st.error("Passwords do not match")
                return

            if len(password) < 6:
                st.error("Password must be at least 6 characters")
                return

            # Create user and location
            database.create_admin_user(username, password)

            conn = database.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM locations ORDER BY id LIMIT 1")
            loc_row = cursor.fetchone()
            if loc_row:
                cursor.execute(
                    """
                    UPDATE locations
                    SET name = ?, target_monthly_sales = ?, target_daily_sales = ?
                    WHERE id = ?
                    """,
                    (
                        st.session_state.setup_location,
                        st.session_state.setup_target,
                        st.session_state.setup_target / 30,
                        loc_row["id"],
                    ),
                )
            conn.commit()
            conn.close()

            st.success("Account created successfully! Please login.")
            st.rerun()


def check_authentication():
    """Check if user is authenticated."""
    return st.session_state.get("authenticated", False)


def logout():
    """Log out user: delete server-side session, clear cookie, reset state."""
    token = st.session_state.get("session_token")
    if token:
        database.delete_session_token(token)
    _get_cookie_manager().remove(_COOKIE_NAME)

    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.location_id = None
    st.session_state.location_name = None
    st.session_state.view_scope = None
    st.session_state.session_token = None
    st.rerun()


def require_auth():
    """Decorator-like function to require authentication."""
    if not check_authentication():
        show_login_form()
        st.stop()


def render_auth_sidebar():
    """Render authentication info in sidebar."""
    with st.sidebar:
        st.markdown("##### Account")
        st.write(f"**Logged in as:** {st.session_state.username}")
        st.write(f"**Role:** {st.session_state.user_role}")
        st.write(f"**Assigned location:** {st.session_state.location_name}")
        st.divider()
        st.markdown("##### Reports & scope")
        st.caption("Daily Report and Analytics use this scope.")
        locs = database.get_all_locations()
        if is_admin() and len(locs) > 1:
            options = ["all"] + [
                str(l["id"]) for l in sorted(locs, key=lambda x: x["name"])
            ]

            def _scope_label(k: str) -> str:
                if k == "all":
                    return "All locations"
                for loc in locs:
                    if str(loc["id"]) == k:
                        return str(loc["name"])
                return k

            vs = st.session_state.get("view_scope")
            if vs not in options:
                st.session_state.view_scope = "all"
                vs = "all"
            ix = options.index(vs)
            choice = st.selectbox(
                "Report scope",
                options=options,
                index=ix,
                format_func=_scope_label,
                key="sidebar_report_scope",
            )
            st.session_state.view_scope = choice
        else:
            st.session_state.view_scope = str(st.session_state.location_id)
        st.divider()
        if st.button("Logout"):
            logout()


def is_admin():
    """Check if current user is admin."""
    return st.session_state.get("user_role") == "admin"


def is_manager():
    """Check if current user is manager or admin."""
    role = st.session_state.get("user_role")
    return role in ["admin", "manager"]


def get_report_location_ids() -> List[int]:
    """Locations included in Daily Report / Analytics for the current scope."""
    locs = database.get_all_locations()
    vs = st.session_state.get("view_scope")
    if is_admin() and vs == "all":
        return [l["id"] for l in sorted(locs, key=lambda x: x["name"])]
    if vs and str(vs) != "all":
        try:
            return [int(vs)]
        except (TypeError, ValueError):
            pass
    lid = st.session_state.get("location_id")
    return [int(lid)] if lid is not None else [1]


def get_report_display_name() -> str:
    locs = database.get_all_locations()
    ids = get_report_location_ids()
    if len(ids) > 1:
        return "All locations"
    for loc in locs:
        if loc["id"] == ids[0]:
            return str(loc["name"])
    return st.session_state.get("location_name") or "Boteco"
