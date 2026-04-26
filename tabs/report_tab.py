"""Report tab — Daily sales report, KPIs, and PNG report generation."""

from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from typing import List, Tuple
from urllib.parse import quote_plus

import streamlit as st

import clipboard_ui
import database
import scope
import sheet_reports as reports
import utils
from components import (
    classed_container,
    date_nav,
    divider,
    filter_strip,
    info_banner,
    page_header,
    page_shell,
    section_title,
)
from components.feedback import empty_state
from services import report_service
from tabs import TabContext


def clear_report_cache() -> None:
    """Clear cached per-date report data.

    Called when new data is imported or when a user requests a refresh.
    """
    report_service.clear_report_cache()


def render(ctx: TabContext) -> None:
    """Render the Daily Report tab UI."""
    shell = page_shell()
    with shell.hero:
        page_header(
            title="Daily Sales Report",
            subtitle=(
                "Track day-level sales health, compare with same weekday last week, and "
                "share report-ready PNG sections."
            ),
            context=ctx.report_display_name,
        )
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
        ):
            section_title("Filters", "Choose a day and outlet scope.", icon="filter_alt")
            selected_date = date_nav(
                session_key="report_date",
                label="Report date",
            )

    date_str = selected_date.strftime("%Y-%m-%d")
    outlets_bundle, summary = report_service.load_report_bundle_cached(ctx.report_loc_ids, date_str)

    with shell.content:
        if summary:
            y_m = [int(x) for x in date_str.split("-")[:2]]
            multi_outlet = len(outlets_bundle) > 1
            _prev_date = selected_date - timedelta(days=7)
            _prev_date_str = _prev_date.strftime("%Y-%m-%d")
            _prev_summary = scope.get_daily_summary_for_scope(ctx.report_loc_ids, _prev_date_str)

            _curr_net = float(summary.get("net_total") or 0)
            _curr_cov = int(summary.get("covers") or 0)
            _curr_apc = float(summary.get("apc") or 0)
            _prev_net = float(_prev_summary.get("net_total") or 0) if _prev_summary else 0.0
            _prev_cov = int(_prev_summary.get("covers") or 0) if _prev_summary else 0
            _prev_apc = float(_prev_summary.get("apc") or 0) if _prev_summary else 0.0

            def _delta_chip(curr: float, prev: float, is_currency: bool = True) -> str:
                if prev == 0:
                    return '<span class="kpi-delta">No baseline</span>'
                growth = utils.calculate_growth(curr, prev)
                pct = growth["percentage"]
                change = growth["change"]
                if change > 0:
                    arrow = "\u25b2"
                    delta_class = "delta-chip--positive"
                elif change < 0:
                    arrow = "\u25bc"
                    delta_class = "delta-chip--negative"
                    change = abs(change)
                    pct = abs(pct)
                else:
                    return '<span class="kpi-delta">No change</span>'
                value = utils.format_rupee_short(change) if is_currency else f"{int(change):,}"
                return (
                    f'<span class="delta-chip {delta_class}">{arrow} {value} ({pct:+.2f}%)</span>'
                )

            with classed_container("tab-report-mobile-kpis", "mobile-layout-stack"):
                st.markdown(
                    (
                        '<div class="kpi-primary-card kpi-snapshot-card">'
                        '<div class="kpi-snapshot-head">'
                        "<h4>Daily KPI Snapshot</h4>"
                        f'<span class="kpi-snapshot-subhead">vs {_prev_date.strftime("%d %b %Y")}</span>'
                        "</div>"
                        '<div class="kpi-snapshot-grid">'
                        '<div class="kpi-item kpi-combined">'
                        '<span class="kpi-label">Net Sales</span>'
                        f'<span class="kpi-value">{utils.format_rupee_short(_curr_net)}</span>'
                        f"{_delta_chip(_curr_net, _prev_net, is_currency=True)}"
                        "</div>"
                        '<div class="kpi-item">'
                        '<span class="kpi-label">Covers</span>'
                        f'<span class="kpi-value">{_curr_cov:,}</span>'
                        f"{_delta_chip(float(_curr_cov), float(_prev_cov), is_currency=False)}"
                        "</div>"
                        '<div class="kpi-item">'
                        '<span class="kpi-label">APC</span>'
                        f'<span class="kpi-value">{utils.format_rupee_short(_curr_apc)}</span>'
                        f"{_delta_chip(_curr_apc, _prev_apc, is_currency=True)}"
                        "</div>"
                        "</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )

            # ── Same weekday previous week comparison ──────────────
            _context_items = [
                f'<span class="context-band-item"><strong>Date:</strong> {selected_date.strftime("%d %b %Y")}</span>',
                f'<span class="context-band-item"><strong>Scope:</strong> {ctx.report_display_name}</span>',
            ]
            if _prev_summary:
                _net_cmp = _delta_chip(_curr_net, _prev_net, is_currency=True)
                _cov_cmp = _delta_chip(float(_curr_cov), float(_prev_cov), is_currency=False)
                _apc_cmp = _delta_chip(_curr_apc, _prev_apc, is_currency=True)
                _context_items.append(
                    f'<span class="report-comparison-bar"><strong>vs {_prev_date.strftime("%d %b")}:</strong> '
                    f"Net {_net_cmp} | Covers {_cov_cmp} | APC {_apc_cmp}</span>"
                )

            st.markdown(
                f'<div class="context-band context-band--muted">{"".join(_context_items)}</div>',
                unsafe_allow_html=True,
            )
            divider()

            # Individual PNG sections
            per_outlet_sheet = [(n, d) for _i, n, d in outlets_bundle] if multi_outlet else None
            per_outlet_cat = None
            per_outlet_svc = None
            if len(ctx.report_loc_ids) > 1:
                mtd_cat, mtd_svc = report_service.build_mtd_maps_cached(
                    ctx.report_loc_ids, y_m[0], y_m[1], date_str
                )
                _today = datetime.now().date()
                _end = _today.strftime("%Y-%m-%d")
                _start_mo_dt = utils.subtract_months(_today, 9)
                _start_mo_str = _start_mo_dt.strftime("%Y-%m-%d")
                _days_since_monday = _today.weekday()
                _current_week_monday = _today - timedelta(days=_days_since_monday)
                _start_wk = (_current_week_monday - timedelta(weeks=3)).strftime("%Y-%m-%d")

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

            if multi_outlet:
                st.markdown(
                    '<div class="context-band context-band--muted">'
                    '<span class="context-band-item microtext">'
                    "<strong>Note:</strong> Category and service sections use combined MTD for all outlets in scope."
                    "</span>"
                    '<span class="context-band-item microtext">'
                    "<strong>Footfall:</strong> Metrics are shown per outlet."
                    "</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )

            if multi_outlet and outlets_bundle:
                filter_strip(
                    "Report scope",
                    "Choose a single outlet or all outlets for PNG export.",
                    icon="tune",
                )
                _outlet_options = ["All outlets"] + [name for _i, name, _ in outlets_bundle]
                _selected_outlet = st.radio(
                    "Select outlet for PNG report",
                    options=_outlet_options,
                    horizontal=True,
                    key="png_outlet_selector",
                    label_visibility="collapsed",
                )

                if _selected_outlet != "All outlets":
                    _selected_lid = None
                    for lid, name, _ in outlets_bundle:
                        if name == _selected_outlet:
                            _selected_lid = lid
                            break

                    _outlet_data = None
                    for lid, name, data in outlets_bundle:
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
                        _today = datetime.now().date()
                        _end = _today.strftime("%Y-%m-%d")
                        _start_mo_dt = utils.subtract_months(_today, 9)
                        _start_mo_str = _start_mo_dt.strftime("%Y-%m-%d")
                        _days_since_monday = _today.weekday()
                        _current_week_monday = _today - timedelta(days=_days_since_monday)
                        _start_wk = (_current_week_monday - timedelta(weeks=3)).strftime("%Y-%m-%d")
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
                                    section_title(title, icon="image")
                                    st.image(BytesIO(sec_bytes), width="stretch")
                                    _wa_text = f"Boteco {_selected_outlet} EOD Report \u2013 {date_str} ({title})"
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
                            section_title(title, icon="image")
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
