"""Tests for upload tab completeness and file details rendering."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from services import upload_service
from tabs import upload_tab
from uploads.models import FileResult


class _NoopContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_import_plan_table_includes_comp_report(monkeypatch):
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(upload_tab.st, "expander", lambda *_a, **_k: _NoopContext())
    monkeypatch.setattr(upload_tab.st, "dataframe", lambda df, **_k: captured.append(df.copy()))
    monkeypatch.setattr(upload_tab.st, "success", lambda *_a, **_k: None)
    monkeypatch.setattr(upload_tab.st, "warning", lambda *_a, **_k: None)

    result = SimpleNamespace(
        files=[
            FileResult(
                filename="comp.xlsx",
                kind="order_comp_summary",
                kind_label="Complimentary Orders Summary",
                importable=True,
            )
        ],
        location_results={1: []},
        category_by_loc={1: []},
        new_flow_meta={
            "comp.xlsx": {
                "detected_location_id": 1,
                "file_type": "order_comp_summary",
            }
        },
    )

    plan = upload_service.build_import_plan(result, [], {1: "Boteco - Indiqube"})
    upload_tab._render_import_plan(plan)

    assert captured
    reports = captured[0]["Reports"].tolist()
    assert any("✅ Comp" in r for r in reports)


def test_file_details_includes_comp_rows(monkeypatch):
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(upload_tab.st, "expander", lambda *_a, **_k: _NoopContext())
    monkeypatch.setattr(
        upload_tab.st,
        "dataframe",
        lambda df, **_k: captured.append(df.copy()),
    )

    files = [
        FileResult(
            filename="growth.xlsx",
            kind="growth_report_day_wise",
            kind_label="Growth Report Day Wise",
            importable=True,
        ),
        FileResult(
            filename="comp.xlsx",
            kind="order_comp_summary",
            kind_label="Complimentary Orders Summary",
            importable=True,
        ),
    ]
    result = SimpleNamespace(
        files=files,
        new_flow_meta={
            "growth.xlsx": {
                "detected_location_name": "Boteco",
                "period_start": "2026-02-01",
                "period_end": "2026-05-03",
                "row_count": 77,
            },
            "comp.xlsx": {
                "detected_location_name": "Boteco",
                "period_start": "2026-02-01",
                "period_end": "2026-05-03",
                "row_count": 12,
            },
        },
    )

    upload_tab._render_file_details(result)

    assert captured
    file_names = set(captured[0]["File"].tolist())
    assert "comp.xlsx" in file_names


def _sample_audit_report(*, with_issue: bool):
    from services import data_quality

    loc_id = 2
    findings = (
        [
            data_quality.CheckFinding(
                location_id=loc_id,
                location_name="Boteco - Bagmane",
                date="2026-08-10",
                detail="No category breakdown (Item Report not uploaded)",
                magnitude=1.0,
            )
        ]
        if with_issue
        else []
    )
    check = data_quality.IntegrityCheck(
        key="category_present",
        label="Category breakdown",
        proves="Every trading day has an Item Report category breakdown",
        severity="error",
        days_examined=30,
        findings=findings,
        days_examined_by_loc={loc_id: 30},
    )
    location = data_quality.LocationDataQuality(
        location_id=loc_id,
        location_name="Boteco - Bagmane",
        checks=[check],
    )
    return data_quality.AuditReport(
        window_start="2026-07-01",
        window_end="2026-08-19",
        locations=[location],
        checks=[check],
        months=[
            data_quality.MonthHealth(
                month="2026-08",
                location_id=loc_id,
                location_name="Boteco - Bagmane",
                days=19,
                days_clean=18 if with_issue else 19,
                issue_count=1 if with_issue else 0,
            )
        ],
        days_audited=30,
        days_clean=29 if with_issue else 30,
    )


class TestRenderDataQuality:
    def test_shows_all_clear_when_no_findings(self, monkeypatch):
        report = _sample_audit_report(with_issue=False)
        monkeypatch.setattr(upload_tab, "_cached_full_history_audit", lambda *a, **k: report)

        captions: list[str] = []
        dataframes: list[pd.DataFrame] = []
        monkeypatch.setattr(upload_tab.st, "caption", lambda text, **_k: captions.append(text))
        monkeypatch.setattr(upload_tab.st, "expander", lambda *_a, **_k: _NoopContext())
        monkeypatch.setattr(
            upload_tab.st, "dataframe", lambda df, **_k: dataframes.append(df.copy())
        )

        ctx = SimpleNamespace(
            report_loc_ids=[2],
            all_locs=[{"id": 2, "name": "Boteco - Bagmane"}],
        )

        upload_tab._render_data_quality(ctx)

        assert any("No integrity issues found" in c for c in captions)
        assert dataframes
        checklist = dataframes[0]
        assert "✅ Pass" in checklist["Result"].tolist()

    def test_shows_findings_expander_for_failing_check(self, monkeypatch):
        report = _sample_audit_report(with_issue=True)
        monkeypatch.setattr(upload_tab, "_cached_full_history_audit", lambda *a, **k: report)

        expander_titles: list[str] = []
        monkeypatch.setattr(
            upload_tab.st,
            "expander",
            lambda title="", **_k: expander_titles.append(title) or _NoopContext(),
        )
        monkeypatch.setattr(upload_tab.st, "dataframe", lambda df, **_k: None)
        monkeypatch.setattr(upload_tab.st, "caption", lambda *_a, **_k: None)

        ctx = SimpleNamespace(
            report_loc_ids=[2],
            all_locs=[{"id": 2, "name": "Boteco - Bagmane"}],
        )

        upload_tab._render_data_quality(ctx)

        assert any("Category breakdown" in t for t in expander_titles)

    def test_empty_report_does_not_crash(self, monkeypatch):
        from services import data_quality

        empty_report = data_quality.AuditReport(window_start="", window_end="")
        monkeypatch.setattr(
            upload_tab, "_cached_full_history_audit", lambda *a, **k: empty_report
        )

        ctx = SimpleNamespace(
            report_loc_ids=[1],
            all_locs=[{"id": 1, "name": "Boteco - Indiqube"}],
        )

        upload_tab._render_data_quality(ctx)
