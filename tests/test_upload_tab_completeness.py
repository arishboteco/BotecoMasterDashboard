"""Tests for upload tab completeness and file details rendering."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

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
