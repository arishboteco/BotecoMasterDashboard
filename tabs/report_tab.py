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
from tabs import TabContext
from components import date_nav, divider


def render(ctx: TabContext) -> None:
    """Render the Daily Report tab UI."""
    st.header("Daily Sales Report")
    # Date selector with Prev/Next navigation
    if "report_date" not in st.session_state:
        most_recent_date = database.get_most_recent_date_with_data(ctx.report_loc_ids)
        if most_recent_date:
            st.session_state["report_date"] = datetime.strptime(
                most_recent_date, "%Y-%m-%d"
            ).date()
        else:
            st.session_state["report_date"] = datetime.now().date()

    selected_date = date_nav(
        session_key="report_date",
        label="Select a date",
        help_text="Choose a date to view that day's report",
    )

    date_str = selected_date.strftime("%Y-%m-%d")
    outlets_bundle, summary = scope.get_daily_report_bundle(
        ctx.report_loc_ids, date_str
    )

    if summary:
        y_m = [int(x) for x in date_str.split("-")[:2]]
        multi_outlet = len(outlets_bundle) > 1

        # ── Same weekday previous week comparison ──────────────
        _prev_date = selected_date - timedelta(days=7)
        _prev_date_str = _prev_date.strftime("%Y-%m-%d")
        _prev_summary = scope.get_daily_summary_for_scope(
            ctx.report_loc_ids, _prev_date_str
        )
        if _prev_summary:
            _prev_net = float(_prev_summary.get("net_total") or 0)
            _prev_cov = int(_prev_summary.get("covers") or 0)
            _prev_apc = float(_prev_summary.get("apc") or 0)
            _curr_net = float(summary.get("net_total") or 0)
            _curr_cov = int(summary.get("covers") or 0)
            _curr_apc = float(summary.get("apc") or 0)

            def _delta_indicator(curr, prev, is_currency=True):
                if prev is None or prev == 0:
                    return ""
                g = utils.calculate_growth(curr, prev)
                pct = g["percentage"]
                change = g["change"]
                if change > 0:
                    arrow = "\u25b2"
                    color = "#22c55e"
                elif change < 0:
                    arrow = "\u25bc"
                    color = "#ef4444"
                    change = abs(change)
                    pct = abs(pct)
                else:
                    return "\u2014"
                if is_currency:
                    return (
                        f'<span style="color:{color};font-size:0.8rem;">'
                        f"{arrow} {utils.format_rupee_short(change)} ({pct:+.2f}%)</span>"
                    )
                else:
                    return (
                        f'<span style="color:{color};font-size:0.8rem;">'
                        f"{arrow} {int(change):,} ({pct:+.2f}%)</span>"
                    )

            _net_cmp = _delta_indicator(_curr_net, _prev_net, is_currency=True)
            _cov_cmp = _delta_indicator(_curr_cov, _prev_cov, is_currency=False)
            _apc_cmp = _delta_indicator(_curr_apc, _prev_apc, is_currency=True)
            st.markdown(
                f'<div style="display:flex;gap:2rem;padding:0.25rem 0 0.5rem 0;'
                f"color:var(--text-secondary);font-size:0.85rem;"
                f'border-bottom:1px solid #e2e8f0;margin-bottom:0.5rem;">'
                f"<span>vs {_prev_date.strftime('%d %b')}: "
                f"Net {_net_cmp} &nbsp;|&nbsp; "
                f"Covers {_cov_cmp} &nbsp;|&nbsp; "
                f"APC {_apc_cmp}</span></div>",
                unsafe_allow_html=True,
            )

        divider()

        # Individual PNG sections
        per_outlet_sheet = (
            [(n, d) for _i, n, d in outlets_bundle] if multi_outlet else None
        )
        per_outlet_cat = None
        per_outlet_svc = None
        if len(ctx.report_loc_ids) > 1:
            mtd_cat, mtd_svc = database.get_mtd_totals_multi(
                ctx.report_loc_ids, y_m[0], y_m[1]
            )
            _today = datetime.now().date()
            _end = _today.strftime("%Y-%m-%d")
            _start_mo = _today.replace(day=1)
            for _ in range(9):
                _m = _start_mo.month - 1
                if _m == 0:
                    _m = 12
                    _start_mo = _start_mo.replace(year=_start_mo.year - 1, month=_m)
                else:
                    _start_mo = _start_mo.replace(month=_m)
            _start_mo_str = _start_mo.strftime("%Y-%m-%d")
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
            foot_rows = database.get_summaries_for_month_multi(
                ctx.report_loc_ids, y_m[0], y_m[1]
            )
            per_outlet_footfall = None
            per_outlet_cat = None
            per_outlet_svc = None
        else:
            mtd_cat = database.get_category_mtd_totals(
                ctx.report_loc_ids[0], y_m[0], y_m[1]
            )
            mtd_svc = database.get_service_mtd_totals(
                ctx.report_loc_ids[0], y_m[0], y_m[1]
            )
            foot_rows = database.get_summaries_for_month(
                ctx.report_loc_ids[0], y_m[0], y_m[1]
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
            st.caption(
                "Category and service sections use **combined** "
                "MTD for all outlets in scope. Footfall metrics are shown per outlet."
            )

        if multi_outlet and outlets_bundle:
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
                _single_outlet_footfall = None
                _single_outlet_footfall_metrics = None

                if len(ctx.report_loc_ids) > 1:
                    _single_outlet_cat = [
                        (name, database.get_category_mtd_totals(lid, y_m[0], y_m[1]))
                        for lid, name, _ in outlets_bundle
                        if lid == _selected_lid
                    ]
                    _single_outlet_svc = [
                        (name, database.get_service_mtd_totals(lid, y_m[0], y_m[1]))
                        for lid, name, _ in outlets_bundle
                        if lid == _selected_lid
                    ]
                    _today = datetime.now().date()
                    _end = _today.strftime("%Y-%m-%d")
                    _start_mo = _today
                    for _ in range(9):
                        _m = _start_mo.month - 1
                        if _m == 0:
                            _m = 12
                            _start_mo = _start_mo.replace(
                                year=_start_mo.year - 1, month=_m
                            )
                        else:
                            _start_mo = _start_mo.replace(month=_m)
                    _start_mo_str = _start_mo.replace(day=1).strftime("%Y-%m-%d")
                    _days_since_monday = _today.weekday()
                    _current_week_monday = _today - timedelta(days=_days_since_monday)
                    _start_wk = (_current_week_monday - timedelta(weeks=3)).strftime(
                        "%Y-%m-%d"
                    )
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
                    foot_rows = database.get_summaries_for_month(
                        _selected_lid, y_m[0], y_m[1]
                    )
                else:
                    foot_rows = database.get_summaries_for_month(
                        _selected_lid, y_m[0], y_m[1]
                    )

                _single_outlet_mtd_cat = None
                _single_outlet_mtd_svc = None

                if len(ctx.report_loc_ids) > 1:
                    _single_outlet_mtd_cat = database.get_category_mtd_totals(
                        _selected_lid, y_m[0], y_m[1]
                    )
                    _single_outlet_mtd_svc = database.get_service_mtd_totals(
                        _selected_lid, y_m[0], y_m[1]
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
                    per_outlet_footfall=_single_outlet_footfall,
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
                                items.append(
                                    (key, f"Footfall Metrics ({slug.title()})")
                                )
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

                with st.expander("PNG Report", expanded=True):
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
                            st.markdown(
                                f'<div class="section-label">{title}</div>',
                                unsafe_allow_html=True,
                            )
                            st.image(BytesIO(sec_bytes), use_container_width=True)
                            _wa_text = f"Boteco {_selected_outlet} EOD Report \u2013 {date_str} ({title})"
                            clipboard_ui.render_image_action_row(
                                sec_bytes,
                                f"boteco_{key}_{date_str}.png",
                                f"action_row_{key}_{date_str}",
                                share_text=_wa_text,
                                fallback_url=f"https://wa.me/?text={quote_plus(_wa_text)}",
                            )
                return

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
                    st.markdown(
                        f'<div class="section-label">{title}</div>',
                        unsafe_allow_html=True,
                    )
                    st.image(BytesIO(sec_bytes), use_container_width=True)
                    _wa_text = (
                        f"Boteco Bangalore EOD Report \u2013 {date_str} ({title})"
                    )
                    clipboard_ui.render_image_action_row(
                        sec_bytes,
                        f"boteco_{key}_{date_str}.png",
                        f"action_row_{key}_{date_str}",
                        share_text=_wa_text,
                        fallback_url=f"https://wa.me/?text={quote_plus(_wa_text)}",
                    )
    else:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon material-symbols-outlined">insights</div>'
            '<div class="empty-state-title">No data for this date</div>'
            '<div class="empty-state-desc">'
            f"No saved data for **{selected_date.strftime('%d %b %Y')}**. "
            "Go to the **Upload** tab and import POS files for that date."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
