"""Regression coverage for combined trading days and the second report forecast."""

import pytest

import pos_parser
import sheet_reports


@pytest.mark.parametrize(
    "rows, expected_sales, expected_days",
    [
        ([("01", 100), ("01", 200)], 300, 1),
        ([("01", 100), ("02", 200), ("02", 50), ("03", 0)], 350, 2),
        ([("01", 100), ("07", 900)], 100, 1),
        ([("01", 0), ("02", 0)], 0, 0),
        ([], 0, 0),
    ],
)
def test_combined_average_counts_dates(monkeypatch, rows, expected_sales, expected_days):
    monkeypatch.setattr(
        "database.get_summaries_for_month_multi",
        lambda *args: [{"date": f"2026-09-{day}", "net_total": value} for day, value in rows],
    )
    pos_parser.calculate_mtd_metrics_multi.clear()
    result = pos_parser.calculate_mtd_metrics_multi(
        [1, 2], 8000000, 2026, 9, as_of_date="2026-09-06"
    )
    assert result["mtd_net_sales"] == expected_sales
    assert result["days_counted"] == expected_days
    assert result["mtd_avg_daily"] == pytest.approx(
        expected_sales / expected_days if expected_days else 0
    )
    pos_parser.calculate_mtd_metrics_multi.clear()


@pytest.mark.parametrize(
    "date, sales, average, target, expected",
    [
        ("2026-09-06", 1442583, 1442583 / 6, 8000000, 7212915),
        ("2026-09-06", 497185, 497185 / 6, 4000000, 2485925),
        ("2026-09-06", 945398, 945398 / 6, 4000000, 4726990),
        ("2026-09-30", 1442583, 240430.5, 8000000, 1442583),
        ("2026-09-06", 0, 0, 8000000, 0),
        ("2026-09-06", 100, 100, 0, 2500),
        ("2026-02-27", 100, 50, 1000, 150),
    ],
)
def test_run_rate_forecast(date, sales, average, target, expected):
    report = {
        "date": date,
        "mtd_net_sales": sales,
        "mtd_avg_daily": average,
        "mtd_target": target,
    }
    result = sheet_reports.compute_forecast_metrics(report)
    assert result["forecast_2_sales"] == pytest.approx(expected)
    if target:
        assert result["forecast_2_target_pct"] == pytest.approx(expected / target * 100)
    else:
        assert result["forecast_2_target_pct"] is None
    changed_average = sheet_reports.compute_forecast_metrics(
        {**report, "mtd_avg_daily": average + 123},
        daily_sales_history=[
            {"date": "2026-01-01", "net_total": 100},
            {"date": "2026-01-02", "net_total": 200},
            {"date": "2026-01-03", "net_total": 300},
        ],
    )
    original_average = sheet_reports.compute_forecast_metrics(
        report,
        daily_sales_history=[
            {"date": "2026-01-01", "net_total": 100},
            {"date": "2026-01-02", "net_total": 200},
            {"date": "2026-01-03", "net_total": 300},
        ],
    )
    assert (
        changed_average["forecast_month_end_sales"] == original_average["forecast_month_end_sales"]
    )


@pytest.mark.parametrize("multi", [False, True])
def test_forecast_2_rendering(multi, monkeypatch):
    report = {
        "date": "2026-09-06",
        "mtd_net_sales": 1442583,
        "mtd_avg_daily": 1442583 / 6,
        "mtd_target": 8000000,
    }
    outlets = [
        (
            "Bagmane",
            {**report, "mtd_net_sales": 497185, "mtd_avg_daily": 497185 / 6, "mtd_target": 4000000},
        ),
        (
            "Indiqube",
            {**report, "mtd_net_sales": 945398, "mtd_avg_daily": 945398 / 6, "mtd_target": 4000000},
        ),
    ]
    elements = sheet_reports._build_sales_summary(
        report, "All locations", per_outlet=outlets if multi else None
    )
    table = next(item for item in elements if isinstance(item, sheet_reports.Table))
    labels = [row[0] for row in table._cellvalues]
    index = labels.index("Forecast 2 — Run Rate")
    assert labels[index - 1] == "Forecast % of Target"
    assert labels[index + 1] == "Forecast 2 % of Target"
    assert table._cellvalues[index][-1] == "₹7,212,915"
    assert table._cellvalues[index + 1][-1] == "90%"
    if multi:
        colors = [style.color.hexval().upper() for style in table._cellStyles[index + 1][1:]]
        assert colors[0] == sheet_reports._hex(sheet_reports.C_RED).hexval().upper()
        assert colors[1] == sheet_reports._hex(sheet_reports.C_GREEN).hexval().upper()
    assert any("Forecast 2 =" in getattr(item, "text", "") for item in elements)

    def inspect_pdf(buf, dpi):
        with sheet_reports.fitz.open(stream=buf.getvalue(), filetype="pdf") as pdf:
            assert len(pdf) == 1
            assert "Forecast 2 =" in pdf[0].get_text()
        return buf

    monkeypatch.setattr(sheet_reports, "_pdf_bytes_to_png", inspect_pdf)
    sheet_reports._render_elements_to_png(elements, sheet_reports.SECTION_WIDTHS[2 if multi else 1])
