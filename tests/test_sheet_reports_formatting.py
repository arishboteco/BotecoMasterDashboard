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


def _first_table(elements):
    return next(element for element in elements if isinstance(element, sheet_reports.Table))


def _background_hex_for_label(table, label: str) -> str | None:
    row_index = next(idx for idx, row in enumerate(table._cellvalues) if row and row[0] == label)
    for command in reversed(getattr(table, "_bkgrndcmds", [])):
        name, start, end, color = command[:4]
        if name == "BACKGROUND" and start[1] <= row_index <= end[1]:
            return color.hexval().replace("0x", "#").upper()
    return None


def _sales_summary_kpi_banner_text(table) -> str:
    nested = table._cellvalues[1][0]
    return nested._cellvalues[0][1].text


def _cell_text_hex(table, row_label: str, col_index: int) -> str:
    row_index = next(idx for idx, row in enumerate(table._cellvalues) if row and row[0] == row_label)
    color = table._cellStyles[row_index][col_index].color
    return color.hexval().replace("0x", "#").upper()


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

        assert "\u20b9800" in element_texts, f"Expected '₹800' in output, got: {element_texts}"
        assert "\u20b91,800" in element_texts, f"Expected '₹1,800' in output, got: {element_texts}"


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


class TestSalesSummaryRowBackgrounds:
    def test_sales_summary_uses_section_backgrounds_without_zebra_banding(self):
        report_data = {
            "date": "2026-04-27",
            "covers": 48,
            "turns": 0.69,
            "gross_total": 49775,
            "net_total": 44010,
            "gpay_sales": 49775,
            "discount": 650,
            "complimentary": 0,
            "cgst": 1153,
            "sgst": 1153,
            "service_charge": 0,
            "mtd_total_covers": 2079,
            "apc": 917,
            "mtd_net_sales": 3311873,
            "mtd_discount": 1732,
            "mtd_complimentary": 0,
            "mtd_avg_daily": 122662,
            "mtd_target": 8000000,
            "mtd_pct_target": 46,
        }

        table = _first_table(
            sheet_reports._build_sales_summary(report_data, location_name="All locations")
        )

        assert _background_hex_for_label(table, "Covers") == sheet_reports.C_ROW_OPS
        assert _background_hex_for_label(table, "Turns") == sheet_reports.C_ROW_OPS
        assert _background_hex_for_label(table, "GPay") is None
        assert _background_hex_for_label(table, "SGST @ 2.5%") is None
        assert _background_hex_for_label(table, "Discount") == sheet_reports.C_ROW_DEDUCTION
        assert _background_hex_for_label(table, "Complimentary") == sheet_reports.C_ROW_EXCEPTION
        assert (
            _background_hex_for_label(table, "Sales Target") == sheet_reports.C_ROW_TARGET_NEUTRAL
        )
        assert _background_hex_for_label(table, "Actual % of Target") == sheet_reports.C_ROW_TARGET_BAD
        assert (
            _background_hex_for_label(table, "Forecast Month-End") == sheet_reports.C_ROW_FORECAST
        )
        assert (
            _background_hex_for_label(table, "Required Daily Run Rate")
            == sheet_reports.C_ROW_REQUIRED_RUN_RATE
        )


class TestSalesSummaryHeaderKpiText:
    def test_kpi_banner_displays_net_and_target_amounts(self):
        report_data = {
            "date": "2026-05-03",
            "net_total": 281670.8,
            "target": 366309.03,
            "pct_target": 76.89,
            "gross_total": 300000,
            "covers": 100,
            "apc": 2816.7,
            "mtd_total_covers": 1000,
            "mtd_net_sales": 1000000,
            "mtd_discount": 0,
            "mtd_complimentary": 0,
            "mtd_avg_daily": 33333,
            "mtd_target": 1500000,
            "mtd_pct_target": 66.6,
        }

        table = _first_table(
            sheet_reports._build_sales_summary(report_data, location_name="All locations")
        )
        banner_text = _sales_summary_kpi_banner_text(table)

        assert "net vs" in banner_text


class TestSalesSummaryMultiOutletForecastColors:
    def test_forecast_target_colors_are_applied_per_outlet(self):
        report_data = {
            "date": "2026-05-06",
            "pct_target": 65,
            "target": 196785,
            "gross_total": 147142,
            "discount": 4152,
            "apc": 1212,
            "apc_baseline_7d": 1250,
            "mtd_target": 8000000,
            "mtd_net_sales": 1100628,
            "mtd_discount": 4678,
        }
        per_outlet = [
            (
                "Bagmane",
                {
                    "date": "2026-05-06",
                    "mtd_target": 4000000,
                    "mtd_net_sales": 286608,
                },
            ),
            (
                "Indiqube",
                {
                    "date": "2026-05-06",
                    "mtd_target": 4000000,
                    "mtd_net_sales": 814020,
                },
            ),
        ]

        table = _first_table(
            sheet_reports._build_sales_summary(
                report_data,
                location_name="All locations",
                per_outlet=per_outlet,
            )
        )

        assert _cell_text_hex(table, "Forecast % of Target", 1) == sheet_reports.C_RED
        assert _cell_text_hex(table, "Forecast % of Target", 2) == sheet_reports.C_GREEN
        assert _cell_text_hex(table, "Forecast % of Target", 3) == sheet_reports.C_RED
