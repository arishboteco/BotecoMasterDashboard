"""Section-level tests for sheet report footfall output keys."""

from typing import Any, Dict, List

import sheet_reports


def _base_report_data() -> Dict[str, Any]:
    return {
        "date": "2026-04-01",
        "net_total": 7500,
        "gross_total": 9500,
        "cash_sales": 4000,
        "gpay_sales": 1000,
        "zomato_sales": 1500,
        "card_sales": 500,
        "other_sales": 500,
        "covers": 200,
        "lunch_covers": 90,
        "dinner_covers": 110,
        "mtd_total_covers": 5000,
        "mtd_net_sales": 225000,
        "mtd_complimentary": 0,
        "mtd_discount": 0,
        "mtd_target": 300000,
        "mtd_avg_daily": 7500,
        "mtd_pct_target": 75,
        "target": 10000,
        "pct_target": 75,
    }


class TestSheetReportSections:
    def test_single_outlet_keeps_legacy_footfall_key(self) -> None:
        sections = sheet_reports.generate_sheet_style_report_sections(
            _base_report_data(),
            mtd_category={"Food": 2000},
            mtd_service={"Service Charge": 120},
            month_footfall_rows=[
                {
                    "date": "2026-04-01",
                    "covers": 220,
                    "lunch_covers": 90,
                    "dinner_covers": 130,
                }
            ],
        )

        for key in ["sales_summary", "category", "service", "footfall"]:
            assert key in sections
            assert sections[key].getbuffer().nbytes > 0

        assert not any(k.startswith("footfall__") for k in sections)

    def test_multi_outlet_generates_per_outlet_footfall_sections(self) -> None:
        sections = sheet_reports.generate_sheet_style_report_sections(
            _base_report_data(),
            mtd_category={"Food": 2000},
            mtd_service={"Service Charge": 120},
            per_outlet_footfall=[
                (
                    "Outlet One",
                    [
                        {
                            "date": "2026-04-01",
                            "covers": 110,
                            "lunch_covers": 50,
                            "dinner_covers": 60,
                        },
                        {
                            "date": "2026-04-02",
                            "covers": 120,
                            "lunch_covers": 60,
                            "dinner_covers": 60,
                        },
                    ],
                ),
                ("Outlet Two", []),
            ],
        )

        footfall_keys: List[str] = [k for k in sections if k.startswith("footfall__")]
        assert len(footfall_keys) == 2
        assert "footfall" not in sections
        assert "sales_summary" in sections
        assert "category" in sections
        assert "service" in sections
        assert all(sections[k].getbuffer().nbytes > 0 for k in footfall_keys)

    def test_image_stacks_with_per_outlet_footfall(self) -> None:
        image = sheet_reports.generate_sheet_style_report_image(
            _base_report_data(),
            mtd_category={"Food": 2000},
            mtd_service={"Service Charge": 120},
            per_outlet_footfall=[("Outlet One", []), ("Outlet Two", [])],
        )
        assert image.getbuffer().nbytes > 0

    def test_single_outlet_footfall_metrics(self) -> None:
        sections = sheet_reports.generate_sheet_style_report_sections(
            _base_report_data(),
            mtd_category={"Food": 2000},
            mtd_service={"Service Charge": 120},
            footfall_metrics_monthly=[
                {"month": "2026-03", "covers": 2087, "total_days": 31},
                {"month": "2026-02", "covers": 1257, "total_days": 28},
                {"month": "2026-01", "covers": 1800, "total_days": 31},
            ],
            footfall_metrics_weekly=[
                {"week": "2026-W13", "covers": 512, "total_days": 7},
                {"week": "2026-W12", "covers": 419, "total_days": 7},
                {"week": "2026-W11", "covers": 447, "total_days": 7},
            ],
        )

        assert "footfall_metrics" in sections
        assert sections["footfall_metrics"].getbuffer().nbytes > 0
        # Legacy footfall key should not be present when metrics are provided
        assert "footfall" not in sections
        assert "sales_summary" in sections
        assert "category" in sections
        assert "service" in sections

    def test_multi_outlet_footfall_metrics_sections(self) -> None:
        sections = sheet_reports.generate_sheet_style_report_sections(
            _base_report_data(),
            mtd_category={"Food": 2000},
            mtd_service={"Service Charge": 120},
            per_outlet_footfall_metrics=[
                (
                    "Outlet One",
                    [
                        {"month": "2026-03", "covers": 1500, "total_days": 31},
                        {"month": "2026-02", "covers": 800, "total_days": 28},
                    ],
                    [
                        {"week": "2026-W13", "covers": 350, "total_days": 7},
                        {"week": "2026-W12", "covers": 280, "total_days": 7},
                    ],
                ),
                (
                    "Outlet Two",
                    [
                        {"month": "2026-03", "covers": 587, "total_days": 31},
                        {"month": "2026-02", "covers": 457, "total_days": 28},
                    ],
                    [
                        {"week": "2026-W13", "covers": 162, "total_days": 7},
                        {"week": "2026-W12", "covers": 139, "total_days": 7},
                    ],
                ),
            ],
        )

        # Check for per-outlet metrics keys
        metrics_keys: List[str] = [
            k for k in sections if k.startswith("footfall_metrics__")
        ]
        assert len(metrics_keys) == 2
        assert "footfall_metrics" not in sections
        assert "footfall" not in sections
        assert "sales_summary" in sections
        assert "category" in sections
        assert "service" in sections
        assert all(sections[k].getbuffer().nbytes > 0 for k in metrics_keys)

    def test_image_stacks_with_footfall_metrics(self) -> None:
        image = sheet_reports.generate_sheet_style_report_image(
            _base_report_data(),
            mtd_category={"Food": 2000},
            mtd_service={"Service Charge": 120},
            footfall_metrics_monthly=[
                {"month": "2026-03", "covers": 2087, "total_days": 31},
            ],
            footfall_metrics_weekly=[
                {"week": "2026-W13", "covers": 512, "total_days": 7},
            ],
        )
        assert image.getbuffer().nbytes > 0

    def test_whatsapp_text_includes_daily_operations_brief(self) -> None:
        txt = sheet_reports.generate_whatsapp_text(
            _base_report_data(), "Boteco Bangalore"
        )
        assert "DAILY OPERATIONS BRIEF" in txt
        assert "Forecast month-end" in txt
