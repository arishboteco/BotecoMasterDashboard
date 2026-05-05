"""Tests for shared navigation components."""

from datetime import date

from components import navigation


def test_sync_session_date_ignores_missing_picker_state(monkeypatch) -> None:
    """Streamlit can invoke callbacks before widget state is available on rerun."""
    existing_date = date(2026, 5, 5)
    monkeypatch.setattr(navigation.st, "session_state", {"report_date": existing_date})

    navigation._sync_session_date_from_picker("report_date", "report_date_picker")

    assert navigation.st.session_state["report_date"] == existing_date
