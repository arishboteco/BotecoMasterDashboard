"""Formatting tests for sheet report helpers."""

import matplotlib.pyplot as plt

import sheet_reports


class TestRupeeFormatting:
    def test_decimal_currency_rounds_to_whole_rupees(self):
        assert sheet_reports._r(72885.08) == "₹72,885"

    def test_small_decimal_currency_rounds_to_whole_rupees(self):
        assert sheet_reports._r(1433.66) == "₹1,434"


class TestForecastFormatting:
    def test_currency_formatter_handles_forecast_values(self):
        assert sheet_reports._r(300000.4) == "₹300,000"


class TestCategorySuperCategoryDisplay:
    def test_category_section_displays_super_categories_only(self):
        fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
        try:
            report_data = {
                "date": "2026-04-08",
                "categories": [
                    {"category": "Tira Gosto", "qty": 2, "amount": 800.0},
                    {"category": "Hot Beverages", "qty": 1, "amount": 200.0},
                ],
            }
            mtd_category = {"Tira Gosto": 1800.0, "Hot Beverages": 600.0}

            row_h = 48 / (120 * 6)  # ROW_PX / (DPI * fig_h)
            sheet_reports._section_category(
                ax,
                report_data,
                location_name="All locations",
                row_h=row_h,
                mtd_category=mtd_category,
                day_lbl="Wed, 8 Apr 2026",
            )

            text_values = {t.get_text() for t in ax.texts}
            assert "Food" in text_values
            assert "Coffee" in text_values
            assert "Tira Gosto" not in text_values
            assert "Hot Beverages" not in text_values
        finally:
            plt.close(fig)

    def test_category_section_accepts_total_key_values(self):
        fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
        try:
            report_data = {
                "date": "2026-04-08",
                "categories": [
                    {"category": "Tira Gosto", "qty": 2, "total": 800.0},
                ],
            }

            row_h = 48 / (120 * 6)  # ROW_PX / (DPI * fig_h)
            sheet_reports._section_category(
                ax,
                report_data,
                location_name="All locations",
                row_h=row_h,
                mtd_category={"Tira Gosto": 1800.0},
                day_lbl="Wed, 8 Apr 2026",
            )

            text_values = {t.get_text() for t in ax.texts}
            assert "₹800" in text_values
            assert "₹1,800" in text_values
        finally:
            plt.close(fig)
