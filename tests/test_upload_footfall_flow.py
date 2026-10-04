"""Regression tests for batched upload footfall entry and save failures."""

from unittest.mock import Mock

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from components import footfall_editor


@pytest.fixture
def footfall_repo(monkeypatch):
    repo = Mock()
    repo.get_for_range.return_value = []
    monkeypatch.setattr(footfall_editor, "get_footfall_override_repository", lambda: repo)
    monkeypatch.setattr(footfall_editor, "_fetch_pos_covers_batch", lambda *_: {})
    monkeypatch.setattr(footfall_editor, "invalidate_footfall_caches", Mock())
    return repo


def _entry_app() -> AppTest:
    return AppTest.from_string(
        """
import streamlit as st
from components import page_shell
from tabs.upload_tab import _render_post_import_footfall

if 'started' not in st.session_state:
    st.session_state.started = True
    st.session_state['_post_import_state'] = {
        'saved_days': 2,
        'dates_by_loc': {
            1: {'name': 'Outlet A', 'dates': ['2026-10-01']},
            2: {'name': 'Outlet B', 'dates': ['2026-10-01']},
        },
    }
if st.session_state.get('_post_import_state'):
    _render_post_import_footfall(page_shell(), None)
else:
    st.success('Finished')
""",
        default_timeout=10,
    ).run()


def _edit_covers(app: AppTest) -> None:
    for loc_id in (1, 2):
        app.session_state[f"upload_footfall_{loc_id}_footfall_editor_{loc_id}_0"] = {
            "edited_rows": {0: {"Lunch": loc_id * 10, "Dinner": 0}},
            "added_rows": [],
            "deleted_rows": [],
        }


def test_one_submit_saves_both_outlets_and_finishes(footfall_repo):
    app = _entry_app()
    assert not app.exception
    _edit_covers(app)
    app.button[0].click().run()
    assert not app.exception
    assert [call.args[0] for call in footfall_repo.upsert.call_args_list] == [1, 2]
    assert footfall_repo.upsert.call_args_list[0].kwargs["lunch_covers"] == 10
    assert footfall_repo.upsert.call_args_list[1].kwargs["dinner_covers"] == 0
    assert "_post_import_state" not in app.session_state
    assert app.session_state["_footfall_summary_flash"] == "Footfall saved for 2 date(s)."


def test_finish_without_saving_discards_drafts(footfall_repo):
    app = _entry_app()
    _edit_covers(app)
    app.button[1].click().run()
    assert not app.exception
    footfall_repo.upsert.assert_not_called()
    footfall_repo.delete.assert_not_called()
    assert "_post_import_state" not in app.session_state


def test_failed_save_keeps_entry_open_for_retry(footfall_repo):
    footfall_repo.upsert.side_effect = RuntimeError("Connection lost")
    app = _entry_app()
    _edit_covers(app)
    app.button[0].click().run()
    assert not app.exception
    assert "_post_import_state" in app.session_state
    assert "retry saving" in app.error[0].value
    assert "_import_summary_flash" not in app.session_state
    footfall_repo.upsert.side_effect = None
    app.button[0].click().run()
    assert not app.exception
    assert "_post_import_state" not in app.session_state


def test_save_preserves_zeroes_blanks_and_unchanged_dates(footfall_repo):
    original = {
        "2026-10-01": {"lunch": pd.NA, "dinner": pd.NA, "has_override": False},
        "2026-10-02": {"lunch": 5, "dinner": 10, "has_override": True},
        "2026-10-03": {"lunch": 8, "dinner": 12, "has_override": True},
        "2026-10-04": {"lunch": pd.NA, "dinner": pd.NA, "has_override": False},
    }
    edited = pd.DataFrame(
        [
            {"Date": "2026-10-01", "Lunch": 0, "Dinner": pd.NA},
            {"Date": "2026-10-02", "Lunch": 5, "Dinner": 10},
            {"Date": "2026-10-03", "Lunch": pd.NA, "Dinner": pd.NA},
            {"Date": "2026-10-04", "Lunch": pd.NA, "Dinner": pd.NA},
        ]
    )
    assert footfall_editor.save_footfall_values(1, edited, original, "manager") == 2
    footfall_repo.upsert.assert_called_once_with(
        1, "2026-10-01", lunch_covers=0, dinner_covers=None, note=None, edited_by="manager"
    )
    footfall_repo.delete.assert_called_once_with(1, "2026-10-03")
    footfall_editor.invalidate_footfall_caches.assert_called_once_with([1])


def test_partial_failure_invalidates_successfully_saved_dates(footfall_repo):
    footfall_repo.upsert.side_effect = [None, RuntimeError("Connection lost")]
    edited = pd.DataFrame(
        [
            {"Date": "2026-10-01", "Lunch": 5, "Dinner": pd.NA},
            {"Date": "2026-10-02", "Lunch": 8, "Dinner": pd.NA},
        ]
    )
    with pytest.raises(RuntimeError):
        footfall_editor.save_footfall_values(1, edited, {}, "manager")
    footfall_editor.invalidate_footfall_caches.assert_called_once_with([1])
