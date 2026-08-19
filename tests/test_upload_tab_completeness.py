"""Tests for upload tab completeness and file details rendering."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from services.data_quality import CategoryMismatch, LocationDataQuality
from tabs import upload_tab
from uploads.models import FileResult


class _NoopContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_outlet_completeness_includes_comp_report(monkeypatch):
    lines: list[str] = []
    monkeypatch.setattr(upload_tab.st, "expander", lambda *_a, **_k: _NoopContext())
    monkeypatch.setattr(upload_tab.st, "markdown", lambda text, **_k: lines.append(str(text)))

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
            }
        },
    )

    upload_tab._render_outlet_completeness(result, {1: "Boteco - Indiqube"})

    assert any("Comp Report" in line for line in lines)


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


class TestRenderDataQuality:
    def test_shows_warnings_for_flagged_outlets(self, monkeypatch):
        warnings: list[str] = []
        monkeypatch.setattr(upload_tab.st, "expander", lambda *_a, **_k: _NoopContext())
        monkeypatch.setattr(upload_tab.st, "warning", lambda text, **_k: warnings.append(text))

        flagged = LocationDataQuality(
            location_id=2,
            location_name="Boteco - Bagmane",
            missing_days=["2026-08-05"],
            category_missing_days=["2026-08-10", "2026-08-11"],
            category_mismatches=[
                CategoryMismatch(date="2026-08-12", net_total=50000, category_total=40000)
            ],
        )
        monkeypatch.setattr(
            "services.data_quality.audit_recent_data_quality",
            lambda location_ids, loc_name_map: [flagged],
        )

        ctx = SimpleNamespace(
            report_loc_ids=[2],
            all_locs=[{"id": 2, "name": "Boteco - Bagmane"}],
        )

        upload_tab._render_data_quality(ctx)

        assert len(warnings) == 3
        assert any("no data uploaded at all" in w for w in warnings)
        assert any("no category breakdown" in w for w in warnings)
        assert any("don't\nmatch net sales" in w or "don't match net sales" in w for w in warnings)

    def test_shows_all_clear_caption_when_no_issues(self, monkeypatch):
        warnings: list[str] = []
        captions: list[str] = []
        monkeypatch.setattr(upload_tab.st, "expander", lambda *_a, **_k: _NoopContext())
        monkeypatch.setattr(upload_tab.st, "warning", lambda text, **_k: warnings.append(text))
        monkeypatch.setattr(upload_tab.st, "caption", lambda text, **_k: captions.append(text))

        clean = LocationDataQuality(location_id=1, location_name="Boteco - Indiqube")
        monkeypatch.setattr(
            "services.data_quality.audit_recent_data_quality",
            lambda location_ids, loc_name_map: [clean],
        )

        ctx = SimpleNamespace(
            report_loc_ids=[1],
            all_locs=[{"id": 1, "name": "Boteco - Indiqube"}],
        )

        upload_tab._render_data_quality(ctx)

        assert warnings == []
        assert any("No missing uploads" in c for c in captions)
