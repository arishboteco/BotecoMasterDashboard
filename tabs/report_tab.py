"""Report tab — Daily sales report, KPIs, and PNG report generation."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from typing import List, Tuple
from urllib.parse import quote_plus

import streamlit as st

import clipboard_ui
import database
import sheet_reports as reports
import utils
from components import (
    classed_container,
    date_nav,
    info_banner,
    page_shell,
)
from components.navigation import init_date_state, shift_date, sync_date_from_picker
from components.feedback import empty_state
from services import report_service
from tabs import TabContext


def clear_report_cache() -> None:
    """Clear cached per-date report data.

    Called when new data is imported or when a user requests a refresh.
    """
    report_service.clear_report_cache()


def _footfall_metric_ranges(selected_date: date) -> Tuple[str, str, str]:
    """Return monthly start, weekly start, and end dates for footfall metrics."""
    end = selected_date.strftime("%Y-%m-%d")
    start_mo_dt = utils.subtract_months(selected_date, 9)
    start_mo_str = start_mo_dt.strftime("%Y-%m-%d")
    days_since_monday = selected_date.weekday()
    current_week_monday = selected_date - timedelta(days=days_since_monday)
    start_wk = (current_week_monday - timedelta(weeks=3)).strftime("%Y-%m-%d")
    return start_mo_str, start_wk, end


def render(ctx: TabContext) -> None:
    """Render the Daily Report tab UI."""
    shell = page_shell()
    # Date selector with Prev/Next navigation
    if "report_date" not in st.session_state:
        most_recent_date = database.get_most_recent_date_with_data(ctx.report_loc_ids)
        if most_recent_date:
            st.session_state["report_date"] = datetime.strptime(most_recent_date, "%Y-%m-%d").date()
        else:
            st.session_state["report_date"] = datetime.now().date()

    with shell.filters:
        with classed_container(
            "tab-report-mobile-filters",
            "mobile-layout-stack",
            "mobile-layout-filters",
            "report-filter-shell",
        ):
            _is_multi_outlet = len(ctx.report_loc_ids) > 1
            if _is_multi_outlet and ctx.all_locs:
                _report_loc_id_set = set(ctx.report_loc_ids)
                _outlet_options = ["All outlets"] + [
                    loc["name"]
                    for loc in ctx.all_locs
                    if loc["id"] in _report_loc_id_set
                ]
                _picker_key = init_date_state("report_date")
                _prev_col, _date_col, _next_col, _outlet_col = st.columns(
                    [0.3, 1.2, 0.3, 4], vertical_alignment="center"
                )
                with _prev_col:
                    st.button(
                        "←",
                        key="report_date_prev",
                        width=44,
                        on_click=shift_date,
                        args=("report_date", _picker_key, -1),
                    )
                with _date_col:
                    st.date_input(
                        "Report date",
                        key=_picker_key,
                        format="DD-MM-YYYY",
                        label_visibility="collapsed",
                        on_change=sync_date_from_picker,
                        args=("report_date", _picker_key),
                    )
                with _next_col:
                    st.button(
                        "→",
                        key="report_date_next",
                        width=44,
                        on_click=shift_date,
                        args=("report_date", _picker_key, 1),
                    )
                with _outlet_col:
                    st.segmented_control(
                        "Select outlet",
                        options=_outlet_options,
                        default=_outlet_options[0],
                        key="png_outlet_selector",
                        label_visibility="collapsed",
                    )
                selected_date = st.session_state["report_date"]
            else:
                selected_date = date_nav(session_key="report_date", label="Report date")

    date_str = selected_date.strftime("%Y-%m-%d")
    outlets_bundle, summary = report_service.load_report_bundle_cached(ctx.report_loc_ids, date_str)

    with shell.content:
        if summary:
            y_m = [int(x) for x in date_str.split("-")[:2]]
            multi_outlet = len(outlets_bundle) > 1
            # Individual PNG sections
            per_outlet_sheet = [(n, d) for _i, n, d in outlets_bundle] if multi_outlet else None
            per_outlet_cat = None
            per_outlet_svc = None
            if len(ctx.report_loc_ids) > 1:
                mtd_cat, mtd_svc = report_service.build_mtd_maps_cached(
                    ctx.report_loc_ids, y_m[0], y_m[1], date_str
                )
                _start_mo_str, _start_wk, _end = _footfall_metric_ranges(selected_date)

                per_outlet_footfall_metrics = [
                    (
                        name,
                        database.get_monthly_footfall_multi([lid], _start_mo_str, _end),
                        database.get_weekly_footfall_multi([lid], _start_wk, _end),
                    )
                    for lid, name, _ in outlets_bundle
                ]
                foot_rows = report_service.get_foot_rows_cached(ctx.report_loc_ids, y_m[0], y_m[1])
                per_outlet_footfall = None
                per_outlet_cat = None
                per_outlet_svc = None
            else:
                mtd_cat, mtd_svc = report_service.build_mtd_maps_cached(
                    [ctx.report_loc_ids[0]], y_m[0], y_m[1], date_str
                )
                foot_rows = report_service.get_foot_rows_cached(
                    [ctx.report_loc_ids[0]], y_m[0], y_m[1]
                )
                per_outlet_footfall = None
                per_outlet_footfall_metrics = None
                per_outlet_cat = None
                per_outlet_svc = None

            section_bufs = reports.generate_sheet_style_report_sections(
                summary,
                ctx.report_display_name,
                mtd_category=mtd_cat,
                mtd_service=mtd_svc,
                month_footfall_rows=foot_rows,
                per_outlet_summaries=per_outlet_sheet,
                per_outlet_category=per_outlet_cat,
                per_outlet_service=per_outlet_svc,
                per_outlet_footfall=per_outlet_footfall,
                per_outlet_footfall_metrics=per_outlet_footfall_metrics,
                daily_sales_history=foot_rows,
            )

            def _footfall_sections() -> List[Tuple[str, str]]:
                items: List[Tuple[str, str]] = []
                for key in section_bufs.keys():
                    if key == "footfall_metrics":
                        items.append((key, "Footfall Metrics"))
                        continue
                    if key == "footfall":
                        items.append((key, "Footfall (month)"))
                        continue
                    if key.startswith("footfall_metrics__"):
                        parts = key.split("__")
                        if len(parts) >= 3:
                            slug = parts[1].replace("_", " ")
                            items.append((key, f"Footfall Metrics ({slug.title()})"))
                        else:
                            items.append((key, "Footfall Metrics"))
                        continue
                    if key.startswith("footfall__"):
                        parts = key.split("__")
                        if len(parts) >= 3:
                            slug = parts[1].replace("_", " ")
                            items.append((key, f"Footfall ({slug.title()})"))
                        else:
                            items.append((key, "Footfall"))
                return items

            if multi_outlet and outlets_bundle:
                _selected_outlet = st.session_state.get("png_outlet_selector") or "All outlets"

                if _selected_outlet != "All outlets":
                    _selected_lid = None
                    for lid, name, _ in outlets_bundle:
                        if name == _selected_outlet:
                            _selected_lid = lid
                            break

                    _outlet_data = None
                    for lid, _name, data in outlets_bundle:
                        if lid == _selected_lid:
                            _outlet_data = data
                            break

                    _single_outlet_sheet = [(_selected_outlet, _outlet_data)]
                    _single_outlet_cat = None
                    _single_outlet_svc = None
                    _single_outlet_footfall_metrics = None

                    if len(ctx.report_loc_ids) > 1:
                        _single_outlet_cat = [
                            (
                                name,
                                report_service.build_mtd_maps_cached(
                                    [lid], y_m[0], y_m[1], date_str
                                )[0],
                            )
                            for lid, name, _ in outlets_bundle
                            if lid == _selected_lid
                        ]
                        _single_outlet_svc = [
                            (
                                name,
                                report_service.build_mtd_maps_cached(
                                    [lid], y_m[0], y_m[1], date_str
                                )[1],
                            )
                            for lid, name, _ in outlets_bundle
                            if lid == _selected_lid
                        ]
                        _start_mo_str, _start_wk, _end = _footfall_metric_ranges(selected_date)
                        _single_outlet_footfall_metrics = [
                            (
                                _selected_outlet,
                                database.get_monthly_footfall_multi(
                                    [_selected_lid], _start_mo_str, _end
                                ),
                                database.get_weekly_footfall_multi(
                                    [_selected_lid], _start_wk, _end
                                ),
                            )
                        ]
                        foot_rows = database.get_summaries_for_month(_selected_lid, y_m[0], y_m[1])
                    else:
                        foot_rows = report_service.get_foot_rows_cached(
                            [_selected_lid], y_m[0], y_m[1]
                        )

                    _single_outlet_mtd_cat = None
                    _single_outlet_mtd_svc = None

                    if len(ctx.report_loc_ids) > 1:
                        _single_outlet_mtd_cat, _single_outlet_mtd_svc = (
                            report_service.build_mtd_maps_cached(
                                [_selected_lid], y_m[0], y_m[1], date_str
                            )
                        )

                    _single_section_bufs = reports.generate_sheet_style_report_sections(
                        _outlet_data,
                        _selected_outlet,
                        mtd_category=_single_outlet_mtd_cat or mtd_cat,
                        mtd_service=_single_outlet_mtd_svc or mtd_svc,
                        month_footfall_rows=foot_rows,
                        per_outlet_summaries=_single_outlet_sheet,
                        per_outlet_category=_single_outlet_cat,
                        per_outlet_service=_single_outlet_svc,
                        per_outlet_footfall=None,
                        per_outlet_footfall_metrics=_single_outlet_footfall_metrics,
                        daily_sales_history=foot_rows,
                    )

                    def _single_footfall_sections() -> List[Tuple[str, str]]:
                        items: List[Tuple[str, str]] = []
                        for key in _single_section_bufs.keys():
                            if key == "footfall_metrics":
                                items.append((key, "Footfall Metrics"))
                                continue
                            if key == "footfall":
                                items.append((key, "Footfall (month)"))
                                continue
                            if key.startswith("footfall_metrics__"):
                                parts = key.split("__")
                                if len(parts) >= 3:
                                    slug = parts[1].replace("_", " ")
                                    items.append((key, f"Footfall Metrics ({slug.title()})"))
                                else:
                                    items.append((key, "Footfall Metrics"))
                                continue
                            if key.startswith("footfall__"):
                                parts = key.split("__")
                                if len(parts) >= 3:
                                    slug = parts[1].replace("_", " ")
                                    items.append((key, f"Footfall ({slug.title()})"))
                                else:
                                    items.append((key, "Footfall"))
                        return items

                    with classed_container(
                        "tab-report-mobile-secondary",
                        "mobile-layout-secondary",
                    ):
                        with st.expander("PNG Report", expanded=True):
                            info_banner(
                                "Primary share bundle",
                                tone="info",
                                icon="ios_share",
                            )
                            _sec_meta = [
                                ("sales_summary", "Sales summary"),
                                ("category", "Category sales"),
                                ("service", "Service sales"),
                            ]
                            _sec_meta.extend(_single_footfall_sections())

                            _first_five = _sec_meta[:5]
                            if _first_five:
                                _share_files = [
                                    (
                                        f"boteco_{key}_{date_str}.png",
                                        _single_section_bufs[key].getvalue(),
                                    )
                                    for key, _ in _first_five
                                ]
                                with classed_container(
                                    "tab-report-mobile-primary-action",
                                    "mobile-layout-primary-action",
                                ):
                                    clipboard_ui.render_share_images_button(
                                        _share_files,
                                        "WhatsApp",
                                        f"share_5_pngs_{date_str}",
                                        height=48,
                                        primary=True,
                                    )

                            rows = max(1, (len(_sec_meta) + 1) // 2)
                            _cells = [st.columns(2) for _ in range(rows)]
                            for idx, (key, title) in enumerate(_sec_meta):
                                sec_bytes = _single_section_bufs[key].getvalue()
                                row_idx, col_idx = divmod(idx, 2)
                                with _cells[row_idx][col_idx]:
                                    st.image(BytesIO(sec_bytes), width="stretch")
                                    _wa_text = (
                                        f"Boteco {_selected_outlet} EOD Report \u2013 "
                                        f"{date_str} ({title})"
                                    )
                                    clipboard_ui.render_image_action_row(
                                        sec_bytes,
                                        f"boteco_{key}_{date_str}.png",
                                        f"action_row_{key}_{date_str}",
                                        share_text=_wa_text,
                                        fallback_url=f"https://wa.me/?text={quote_plus(_wa_text)}",
                                    )
                    return

            with classed_container("tab-report-mobile-secondary", "mobile-layout-secondary"):
                with st.expander("Individual PNG sections", expanded=True):
                    _sec_meta = [
                        ("sales_summary", "Sales summary"),
                        ("category", "Category sales"),
                        ("service", "Service sales"),
                    ]
                    _sec_meta.extend(_footfall_sections())

                    # Combined share button for first 5 PNG sections
                    _first_five = _sec_meta[:5]
                    if _first_five:
                        _share_files = [
                            (f"boteco_{key}_{date_str}.png", section_bufs[key].getvalue())
                            for key, _ in _first_five
                        ]
                        with classed_container(
                            "tab-report-mobile-primary-action",
                            "mobile-layout-primary-action",
                        ):
                            clipboard_ui.render_share_images_button(
                                _share_files,
                                "WhatsApp",
                                f"share_5_pngs_{date_str}",
                                height=48,
                                primary=True,
                            )

                    rows = max(1, (len(_sec_meta) + 1) // 2)
                    _cells = [st.columns(2) for _ in range(rows)]
                    for idx, (key, title) in enumerate(_sec_meta):
                        sec_bytes = section_bufs[key].getvalue()
                        row_idx, col_idx = divmod(idx, 2)
                        with _cells[row_idx][col_idx]:
                            st.image(BytesIO(sec_bytes), width="stretch")
                            _wa_text = f"Boteco Bangalore EOD Report \u2013 {date_str} ({title})"
                            clipboard_ui.render_image_action_row(
                                sec_bytes,
                                f"boteco_{key}_{date_str}.png",
                                f"action_row_{key}_{date_str}",
                                share_text=_wa_text,
                                fallback_url=f"https://wa.me/?text={quote_plus(_wa_text)}",
                            )
        else:
            empty_state(
                message="No data for this date",
                hint=(
                    f"No saved data for <strong>{selected_date.strftime('%d %b %Y')}</strong>. "
                    "Go to the <strong>Upload</strong> tab and import POS files for that date."
                ),
                icon="insights",
            )
