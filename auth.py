from typing import List

import streamlit as st
import database
from datetime import datetime


def init_auth_state():
    """Initialize authentication state variables."""
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


def show_login_form():
    """Show login form."""
    st.markdown(
        """
        <style>
        :root {
            --brand: #C2703E;
            --brand-dark: #A45A2E;
            --login-surface: #FFF8F0;
            --login-border: #E0D5C8;
            --text: #3D2B1F;
        }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 2.5rem;
            background: var(--login-surface);
            border-radius: 14px;
            border: 1px solid var(--login-border);
            box-shadow: 0 4px 16px rgba(60, 40, 20, 0.10);
        }
        .stButton > button {
            width: 100%;
            background-color: var(--brand);
            color: #FFF8F0;
            border: none;
            padding: 0.75rem;
            border-radius: 10px;
            font-weight: bold;
            font-family: 'DM Sans', sans-serif;
        }
        .stButton > button:hover {
            background-color: var(--brand-dark);
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
                    st.session_state.authenticated = True
                    st.session_state.username = user["username"]
                    st.session_state.user_role = user["role"]
                    st.session_state.location_id = user.get("location_id") or 1
                    st.session_state.location_name = (
                        user.get("location_name") or "Boteco"
                    )
                    if user.get("role") == "admin":
                        st.session_state.view_scope = "all"
                    else:
                        st.session_state.view_scope = str(st.session_state.location_id)
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
    """Log out user."""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.location_id = None
    st.session_state.location_name = None
    st.session_state.view_scope = None
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
