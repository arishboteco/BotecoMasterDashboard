"""Formatting tests for sheet report helpers."""

from PIL import Image

import sheet_reports


def _has_dark_footer_band(buf) -> bool:
    buf.seek(0)
    image = Image.open(buf).convert("RGB")
    sample_xs = (image.width // 4, image.width // 2, (image.width * 3) // 4)
    dark_rows = 0
    for y in range(image.height // 2, max(image.height - 8, image.height // 2)):
        dark_samples = 0
        for x in sample_xs:
            r, g, b = image.getpixel((x, y))
            if r < 60 and g < 90 and b < 130:
                dark_samples += 1
        if dark_samples >= 2:
            dark_rows += 1
    return dark_rows >= 8


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
            if isinstance(el, sheet_reports.Table):
                for row_data in el._cellvalues:
                    for cell in row_data:
                        if cell is not None:
                            element_texts.append(str(cell))

        assert "Food (" in str(element_texts), (
            f"Expected 'Food (xx%)' in output, got: {element_texts}"
        )
        assert "Coffee (" in str(element_texts), (
            f"Expected 'Coffee (xx%)' in output, got: {element_texts}"
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


class TestCategoryServiceTotalRows:
    def test_category_png_shows_total_footer_row(self):
        sections = sheet_reports.generate_sheet_style_report_sections(
            {
                "date": "2026-04-08",
                "categories": [
                    {"category": "Food", "amount": 800.0},
                    {"category": "Liquor", "amount": 450.0},
                ],
            },
            mtd_category={"Food": 1800.0, "Liquor": 900.0},
        )

        assert _has_dark_footer_band(sections["category"])

    def test_service_png_shows_total_footer_row(self):
        sections = sheet_reports.generate_sheet_style_report_sections(
            {
                "date": "2026-04-08",
                "services": [
                    {"service_type": "Lunch", "amount": 700.0},
                    {"service_type": "Dinner", "amount": 950.0},
                ],
            },
            mtd_service={"Lunch": 1400.0, "Dinner": 2100.0},
        )

        assert _has_dark_footer_band(sections["service"])
