"""Authentication and shared page replacement regression tests."""
import pytest
from streamlit.testing.v1 import AppTest

HARNESS = r"""
import time
from types import SimpleNamespace
from pathlib import Path
import streamlit as st
import streamlit_cookies_controller.cookie_controller as cookies
import auth
import styles

st.set_page_config(layout="wide")

def cookie_component(**kwargs):
    if kwargs["method"] == "set":
        if st.session_state.get("fail_cookie"):
            raise TypeError("browser component failed")
        st.session_state["saved_cookie"] = kwargs
    return None
cookies._cookie_controller = cookie_component

auth.database.verify_user = lambda u, p: (
    {"id": 1, "username": u, "role": "admin"} if p == "test-password" else None
)
auth.database.create_user_session = lambda *a, **kw: "test-token"
database = SimpleNamespace(
    get_all_locations=lambda: [], get_location_settings=lambda location: {},
)
auth.get_report_location_ids = lambda: []
auth.get_report_display_name = lambda: "All outlets"
auth.get_primary_location_id = lambda: 1
TabContext = lambda **kwargs: kwargs

def render(name):
    def run(ctx):
        if st.session_state.get("slow_preview"):
            time.sleep(2)
        st.title(name)
        st.write("Section content")
    return run
APP_NAV_ITEMS = {name: render(name) for name in
                 ["Upload", "Report", "Analytics", "Footfall", "Settings"]}
def sidebar_app_nav(items, default):
    return st.sidebar.radio("Section", items, index=items.index(default))
st.markdown(styles.get_css(), unsafe_allow_html=True)
source = Path("app.py").read_text(encoding="utf-8")
exec(compile(source[source.index("# Initialize authentication"):], "app.py", "exec"))
"""


@pytest.fixture(autouse=True)
def restore_harness_patches(monkeypatch):
    import streamlit_cookies_controller.cookie_controller as cookies

    import auth

    for target, names in [
        (auth, ["get_report_location_ids", "get_report_display_name", "get_primary_location_id"]),
        (auth.database, ["verify_user", "create_user_session"]),
        (cookies, ["_cookie_controller"]),
    ]:
        for name in names:
            monkeypatch.setattr(target, name, getattr(target, name))


def login(app):
    app.text_input[0].set_value("tester")
    app.text_input[1].set_value("test-password")
    app.button[0].click().run()
    assert not app.exception
    return app


def test_login_clears_form_and_all_sections_replace_previous_content():
    app = AppTest.from_string(HARNESS, default_timeout=15).run()
    assert not app.exception
    login(app)
    assert not app.text_input
    assert not app.warning
    assert app.title[0].value == "Analytics"
    saved = app.session_state["saved_cookie"]
    assert saved["value"] == "test-token"
    assert "expires" in saved["options"]
    for section in ["Upload", "Report", "Footfall", "Settings", "Analytics"]:
        app.radio[0].set_value(section).run()
        assert not app.exception
        assert [title.value for title in app.title] == [section]
        assert not app.text_input


def test_cookie_failure_keeps_login_success_and_shows_dashboard_notice():
    app = AppTest.from_string(HARNESS, default_timeout=15)
    app.session_state["fail_cookie"] = True
    app.run()
    login(app)
    assert app.title[0].value == "Analytics"
    assert not app.text_input
    assert "Remember me could not be saved" in app.warning[0].value


def test_invalid_password_keeps_login_form():
    app = AppTest.from_string(HARNESS, default_timeout=15).run()
    app.text_input[0].set_value("tester")
    app.text_input[1].set_value("wrong")
    app.button[0].click().run()
    assert not app.exception
    assert len(app.text_input) == 2
    assert app.error[0].value == "Invalid username or password"
    assert not app.title


@pytest.mark.parametrize("snapshot", [None, {"existing": "preserved"}])
def test_cookie_snapshot_recovery_preserves_existing_cookies(snapshot):
    app = AppTest.from_string(HARNESS, default_timeout=15)
    app.session_state["boteco_cookie_manager"] = snapshot
    app.run()
    login(app)
    assert app.session_state["saved_cookie"]["value"] == "test-token"
    if snapshot:
        assert app.session_state["boteco_cookie_manager"]["existing"] == "preserved"
