"""Formatting tests for sheet report helpers."""

import sheet_reports


class TestRupeeFormatting:
    def test_decimal_currency_rounds_to_whole_rupees(self):
        assert sheet_reports._r(72885.08) == "\u20b972,885"

    def test_small_decimal_currency_rounds_to_whole_rupees(self):
        assert sheet_reports._r(1433.66) == "\u20b91,434"


class TestForecastFormatting:
    def test_currency_formatter_handles_forecast_values(self):
        assert sheet_reports._r(300000.4) == "\u20b9300,000"


class TestCategorySuperCategoryDisplay:
    def test_category_section_displays_super_categories_only(self):
        report_data = {
            "date": "2026-04-08",
            "categories": [
                {"category": "Tira Gosto", "qty": 2, "amount": 800.0},
                {"category": "Hot Beverages", "qty": 1, "amount": 200.0},
            ],
        }
        mtd_category = {"Tira Gosto": 1800.0, "Hot Beverages": 600.0}

        elements = sheet_reports._build_category(
            report_data,
            location_name="All locations",
            mtd_category=mtd_category,
            day_lbl="Wed, 8 Apr 2026",
        )

        # Verify the section builds without errors and contains a Table
        has_table = any(isinstance(el, sheet_reports.Table) for el in elements)
        assert has_table, "Expected a Table element in the section output"

        # Extract text from Table cells to verify super category collapse
        element_texts = []
        for el in elements:
            if isinstance(el, sheet_reports._BannerFlowable):
                element_texts.append(el.title)
            if isinstance(el, sheet_reports.Table):
                for row_data in el._cellvalues:
                    for cell in row_data:
                        if cell is not None:
                            element_texts.append(str(cell))

        assert "Food" in element_texts, (
            f"Expected 'Food' in output, got: {element_texts}"
        )
        assert "Coffee" in element_texts, (
            f"Expected 'Coffee' in output, got: {element_texts}"
        )

    def test_category_section_accepts_total_key_values(self):
        report_data = {
            "date": "2026-04-08",
            "categories": [
                {"category": "Tira Gosto", "qty": 2, "total": 800.0},
            ],
        }

        elements = sheet_reports._build_category(
            report_data,
            location_name="All locations",
            mtd_category={"Tira Gosto": 1800.0},
            day_lbl="Wed, 8 Apr 2026",
        )

        # Extract cell text to verify currency formatting
        element_texts = []
        for el in elements:
            if isinstance(el, sheet_reports.Table):
                for row_data in el._cellvalues:
                    for cell in row_data:
                        if cell is not None:
                            element_texts.append(str(cell))

        assert "\u20b9800" in element_texts, (
            f"Expected '₹800' in output, got: {element_texts}"
        )
        assert "\u20b91,800" in element_texts, (
            f"Expected '₹1,800' in output, got: {element_texts}"
        )
