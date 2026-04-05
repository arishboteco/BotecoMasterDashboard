from typing import List
from datetime import datetime, timedelta

import streamlit as st
import database
import config
import styles
from streamlit_cookies_controller import CookieController

_COOKIE_NAME = "boteco_session"
_COOKIE_EXPIRY_DAYS = 30


def _get_cookie_manager() -> CookieController:
    """Return the CookieController for the current render.

    A fresh instance is created once per render inside init_auth_state() and
    stored in st.session_state so that subsequent calls within the same render
    reuse it (avoiding duplicate-component-key errors).
    """
    if "_cm" not in st.session_state:
        # Fallback: shouldn't normally be needed if init_auth_state() runs first
        st.session_state._cm = CookieController(key="boteco_cookie_manager")
    return st.session_state._cm


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
    """Initialize authentication state, restoring from cookie when possible.

    Called once per render from app.py.  Creates a fresh CookieController at
    the top of every render so its __cookies dict is always current (avoids
    the stale-cached-instance bug).
    """
    # Set defaults
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

    # Always create a fresh CookieController at the START of each render so
    # that its internal __cookies dict reflects the latest component state.
    # Storing it in session_state lets other functions reuse it within this
    # render without creating a duplicate component call.
    st.session_state._cm = CookieController(key="boteco_cookie_manager")

    if st.session_state.authenticated:
        return  # already logged in this server-side session

    # Attempt cookie-based session restoration.
    # Returns None on the very first render (JS not yet run); the component
    # automatically triggers a rerun once it has sent the cookie data.
    token = st.session_state._cm.get(_COOKIE_NAME)
    if token:
        user = database.validate_session_token(token)
        if user:
            _apply_user_to_session(user, token)
        else:
            st.session_state._cm.remove(_COOKIE_NAME)  # stale / expired


def show_login_form():
    """Show login form."""
    st.markdown(styles.get_login_css(), unsafe_allow_html=True)

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
                locked, mins_left = database.is_login_locked(username)
                if locked:
                    st.error(
                        f"Too many failed attempts. Try again in about {mins_left} minute(s)."
                    )
                    return

                user = database.verify_user(username, password)
                if user:
                    database.clear_failed_login(username)
                    token = database.create_user_session(
                        user["id"], days=_COOKIE_EXPIRY_DAYS
                    )
                    _get_cookie_manager().set(
                        _COOKIE_NAME,
                        token,
                        expires=datetime.now() + timedelta(days=_COOKIE_EXPIRY_DAYS),
                    )
                    _apply_user_to_session(user, token)
                    st.rerun()
                else:
                    locked, mins_left = database.record_failed_login(username)
                    if locked:
                        st.error(
                            f"Too many failed attempts. Try again in about {mins_left} minute(s)."
                        )
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

            if len(password) < config.MIN_PASSWORD_LENGTH:
                st.error(
                    f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters"
                )
                return

            # Create user and location
            database.create_admin_user(username, password)

            locations = database.get_all_locations()
            if locations:
                database.update_location_settings(
                    int(locations[0]["id"]),
                    {
                        "name": st.session_state.setup_location,
                        "target_monthly_sales": st.session_state.setup_target,
                    },
                )

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
