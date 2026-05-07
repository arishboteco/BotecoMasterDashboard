"""Tests for extracted permission and report-scope helpers."""

from __future__ import annotations

import auth
import auth_permissions


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_is_admin_and_is_manager_role_checks(monkeypatch):
    """Role helpers should match existing auth behavior."""
    monkeypatch.setattr(auth_permissions.st, "session_state", {"user_role": "admin"})

    assert auth_permissions.is_admin() is True
    assert auth_permissions.is_manager() is True

    monkeypatch.setattr(auth_permissions.st, "session_state", {"user_role": "manager"})

    assert auth_permissions.is_admin() is False
    assert auth_permissions.is_manager() is True


def test_get_report_location_ids_for_admin_all_scope_sorted(monkeypatch):
    """Admin users with all scope should return all IDs sorted by location name."""
    monkeypatch.setattr(
        auth_permissions.database,
        "get_all_locations",
        lambda: [
            {"id": 2, "name": "Zeta"},
            {"id": 1, "name": "Alpha"},
        ],
    )
    monkeypatch.setattr(
        auth_permissions.st,
        "session_state",
        {"user_role": "admin", "view_scope": "all", "location_id": 99},
    )

    assert auth_permissions.get_report_location_ids() == [1, 2]


def test_get_report_location_ids_uses_view_scope_when_specific(monkeypatch):
    """Specific view scopes should override current location ID."""
    monkeypatch.setattr(auth_permissions.database, "get_all_locations", lambda: [])
    monkeypatch.setattr(
        auth_permissions.st,
        "session_state",
        {"user_role": "manager", "view_scope": "5", "location_id": 2},
    )

    assert auth_permissions.get_report_location_ids() == [5]


def test_get_report_display_name_falls_back_to_session_name(monkeypatch):
    """Display name should fall back to location_name when ID not found."""
    monkeypatch.setattr(auth_permissions.database, "get_all_locations", lambda: [])
    monkeypatch.setattr(
        auth_permissions.st,
        "session_state",
        {
            "user_role": "manager",
            "view_scope": None,
            "location_id": 8,
            "location_name": "Fallback Outlet",
        },
    )

    assert auth_permissions.get_report_display_name() == "Fallback Outlet"


def test_auth_wrappers_delegate_to_auth_permissions(monkeypatch):
    """Legacy auth.py helper functions should remain as compatibility wrappers."""
    monkeypatch.setattr(auth_permissions, "is_admin", lambda: True)
    monkeypatch.setattr(auth_permissions, "is_manager", lambda: False)
    monkeypatch.setattr(auth_permissions, "get_report_location_ids", lambda: [3, 4])
    monkeypatch.setattr(auth_permissions, "get_report_display_name", lambda: "All locations")

    assert auth.is_admin() is True
    assert auth.is_manager() is False
    assert auth.get_report_location_ids() == [3, 4]
    assert auth.get_report_display_name() == "All locations"


def test_get_report_location_ids_for_unassigned_manager_all_scope(monkeypatch):
    """Unassigned managers with all scope should see all outlet IDs sorted by name."""
    monkeypatch.setattr(
        auth_permissions.database,
        "get_all_locations",
        lambda: [
            {"id": 2, "name": "Zeta"},
            {"id": 1, "name": "Alpha"},
        ],
    )
    monkeypatch.setattr(
        auth_permissions.st,
        "session_state",
        {"user_role": "manager", "view_scope": "all", "location_id": None},
    )

    assert auth_permissions.get_report_location_ids() == [1, 2]


def test_apply_user_to_session_unassigned_manager_gets_all_scope(monkeypatch):
    """Unassigned managers should get all-scope and no default outlet fallback."""
    monkeypatch.setattr(auth.st, "session_state", _SessionState())

    auth._apply_user_to_session(
        {"username": "mgr", "role": "manager", "location_id": None},
        "token-1",
    )

    assert auth.st.session_state.location_id is None
    assert auth.st.session_state.view_scope == "all"
