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


def show_login_form():
    """Show login form."""
    st.markdown(
        """
        <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 2rem;
            background: #f8f9fa;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stButton > button {
            width: 100%;
            background-color: #e94560;
            color: white;
            border: none;
            padding: 0.75rem;
            border-radius: 5px;
            font-weight: bold;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("🥂 Boteco Dashboard")
    st.markdown("### Restaurant Sales Management")

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
                        user.get("location_name") or "Boteco Bangalore"
                    )
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            else:
                st.warning("Please enter both username and password")


def show_setup_form():
    """Show initial setup form for first-time users."""
    st.title("🥂 Boteco Dashboard - Setup")
    st.markdown("### Create Admin Account")

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
        st.text_input("Location Name", key="setup_location", value="Boteco Bangalore")
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

            # Update location settings
            conn = database.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE locations 
                SET name = ?, target_monthly_sales = ?, target_daily_sales = ?
                WHERE name = 'Boteco Bangalore'
            """,
                (
                    st.session_state.setup_location,
                    st.session_state.setup_target,
                    st.session_state.setup_target / 30,
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
    st.rerun()


def require_auth():
    """Decorator-like function to require authentication."""
    if not check_authentication():
        show_login_form()
        st.stop()


def render_auth_sidebar():
    """Render authentication info in sidebar."""
    with st.sidebar:
        st.markdown("### 👤 User Info")
        st.write(f"**Logged in as:** {st.session_state.username}")
        st.write(f"**Role:** {st.session_state.user_role}")
        st.write(f"**Location:** {st.session_state.location_name}")
        st.markdown("---")
        if st.button("🚪 Logout"):
            logout()


def is_admin():
    """Check if current user is admin."""
    return st.session_state.get("user_role") == "admin"


def is_manager():
    """Check if current user is manager or admin."""
    role = st.session_state.get("user_role")
    return role in ["admin", "manager"]
