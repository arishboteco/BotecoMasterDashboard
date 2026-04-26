from datetime import datetime, timedelta
from typing import List, Optional

import streamlit as st
from streamlit_cookies_controller import CookieController

import auth_permissions
import boteco_logger
import config
import database
import styles

_COOKIE_NAME = "boteco_session"
_COOKIE_EXPIRY_DAYS = 30
logger = boteco_logger.get_logger(__name__)


def _get_cookie_manager() -> Optional[CookieController]:
    """Return the CookieController for the current render.

    A fresh instance is created once per render inside init_auth_state() and
    stored in st.session_state so that subsequent calls within the same render
    reuse it (avoiding duplicate-component-key errors).
    """
    if "_cm" not in st.session_state or st.session_state._cm is None:
        try:
            st.session_state._cm = CookieController(key="boteco_cookie_manager")
        except TypeError as ex:
            logger.warning(
                "CookieController init failed in auth.py user=%s error=%s",
                st.session_state.get("username") or "anonymous",
                ex,
            )
            return None
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
    try:
        st.session_state._cm = CookieController(key="boteco_cookie_manager")
    except TypeError as ex:
        logger.warning(
            "CookieController render init failed in auth.py user=%s error=%s",
            st.session_state.get("username") or "anonymous",
            ex,
        )
        st.session_state._cm = None

    if st.session_state.authenticated:
        return  # already logged in this server-side session

    # Attempt cookie-based session restoration.
    # Cookie data arrives from JS asynchronously. The component needs at least
    # one full render cycle to synchronize. Track retries in session state
    # so we don't restart the counter on every rerun.
    cookie_retries = st.session_state.get("_cookie_retries", 0)
    if cookie_retries < 2:
        try:
            token = st.session_state._cm.get(_COOKIE_NAME)
        except (TypeError, AttributeError):
            token = None
        if token:
            user = database.validate_session_token(token)
            if user:
                _apply_user_to_session(user, token)
                st.session_state.pop("_cookie_retries", None)
            else:
                if st.session_state._cm is not None:
                    try:
                        st.session_state._cm.remove(_COOKIE_NAME)
                    except (TypeError, AttributeError) as ex:
                        logger.warning(
                            "Cookie removal failed in auth.py user=%s token_present=%s error=%s",
                            st.session_state.get("username") or "anonymous",
                            bool(token),
                            ex,
                        )
                st.session_state.pop("_cookie_retries", None)
                st.rerun()
        else:
            st.session_state["_cookie_retries"] = cookie_retries + 1
            st.rerun()


def show_login_form():
    """Show login form."""
    st.markdown(styles.get_login_css(), unsafe_allow_html=True)

    # Centered login card with logo and branding
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.image("logo.png", width=160)
        st.markdown(
            '<div class="login-title">Boteco Dashboard</div>'
            '<div class="login-subtitle">Restaurant Sales Management</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="login-form-wrap">', unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            st.markdown(
                '<div id="login-caps-hint" class="login-caps-hint">⚠ Caps Lock is ON</div>',
                unsafe_allow_html=True,
            )
            remember = st.checkbox("Remember me for 30 days", value=True)
            submit = st.form_submit_button("Sign In", width="stretch")

        # Caps-lock hint: listen to keydown/keyup on password input
        st.markdown(
            """
            <script>
            (function() {
                const hint = window.parent.document.getElementById('login-caps-hint');
                const pw = window.parent.document.querySelector('input[type="password"]');
                if (!hint || !pw) return;
                const update = (e) => {
                    const on = e.getModifierState && e.getModifierState('CapsLock');
                    hint.classList.toggle('active', !!on);
                };
                pw.addEventListener('keydown', update);
                pw.addEventListener('keyup', update);
                pw.addEventListener('focus', (e) => update(e));
                pw.addEventListener('blur', () => hint.classList.remove('active'));
            })();
            </script>
            """,
            unsafe_allow_html=True,
        )

        if submit:
            if username and password:
                locked, mins_left = database.is_login_locked(username)
                if locked:
                    st.error(f"Too many failed attempts. Try again in about {mins_left} minute(s).")
                    return

                user = database.verify_user(username, password)
                if user:
                    database.clear_failed_login(username)
                    # "Remember me" unchecked → session cookie (no expires);
                    # checked → persistent cookie for _COOKIE_EXPIRY_DAYS
                    session_days = _COOKIE_EXPIRY_DAYS if remember else 1
                    token = database.create_user_session(user["id"], days=session_days)
                    cm = _get_cookie_manager()
                    if cm is not None:
                        try:
                            cookie_kwargs = {}
                            if remember:
                                cookie_kwargs["expires"] = datetime.now() + timedelta(
                                    days=session_days
                                )
                            cm.set(_COOKIE_NAME, token, **cookie_kwargs)
                        except TypeError as ex:
                            logger.warning(
                                "Cookie set failed in auth.py user=%s remember=%s error=%s",
                                username,
                                remember,
                                ex,
                            )
                            st.warning(
                                "Signed in, but 'Remember me' could not be applied in this browser."
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

        st.markdown("</div>", unsafe_allow_html=True)  # login-form-wrap
        st.markdown("</div>", unsafe_allow_html=True)  # login-card


def show_setup_form():
    """Show initial setup form for first-time users."""
    st.title("Boteco Dashboard - Setup")
    st.markdown("### Create Admin Account")
    st.caption("One-time setup — create the first admin and default location.")

    with st.form("setup_form"):
        st.text_input("Username", key="setup_username", placeholder="Enter admin username")
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
            location_name = st.session_state.setup_location

            if not username or not password:
                st.error("Username and password are required")
                return

            if password != confirm:
                st.error("Passwords do not match")
                return

            if len(password) < config.MIN_PASSWORD_LENGTH:
                st.error(f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters")
                return

            if not str(location_name).strip():
                st.error("Location name is required")
                return

            locations = database.get_all_locations()
            try:
                if locations:
                    database.update_location_settings(
                        int(locations[0]["id"]),
                        {
                            "name": location_name,
                            "target_monthly_sales": st.session_state.setup_target,
                        },
                    )
                database.create_admin_user(username, password)
            except ValueError as exc:
                st.error(str(exc))
                return

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
    cm = _get_cookie_manager()
    if cm is not None:
        try:
            cm.remove(_COOKIE_NAME)
        except (TypeError, AttributeError) as ex:
            logger.warning(
                "Cookie cleanup failed during logout in auth.py user=%s error=%s",
                st.session_state.get("username") or "anonymous",
                ex,
            )

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


def is_admin() -> bool:
    """Backward-compatible wrapper for admin role checks."""
    return auth_permissions.is_admin()


def is_manager() -> bool:
    """Backward-compatible wrapper for manager role checks."""
    return auth_permissions.is_manager()


def get_report_location_ids() -> List[int]:
    """Backward-compatible wrapper for report location scope resolution."""
    return auth_permissions.get_report_location_ids()


def get_report_display_name() -> str:
    """Backward-compatible wrapper for report scope display naming."""
    return auth_permissions.get_report_display_name()
