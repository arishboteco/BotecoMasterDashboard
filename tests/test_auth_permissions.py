"""Tests for extracted permission and report-scope helpers."""

from __future__ import annotations

import auth
import auth_permissions


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
