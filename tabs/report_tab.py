"""Report tab — Daily sales report, KPIs, and PNG report generation."""

from __future__ import annotations

import zipfile
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
from components import divider


def render(ctx: TabContext) -> None:
    """Render the Daily Report tab UI."""
    st.header("Daily Sales Report")
    st.caption(f"Viewing: **{ctx.report_display_name}** — pick a date below.")
    st.divider()

    # Date selector with Prev/Next navigation
    if "report_date" not in st.session_state:
        most_recent_date = database.get_most_recent_date_with_data(ctx.report_loc_ids)
        if most_recent_date:
            st.session_state["report_date"] = datetime.strptime(
                most_recent_date, "%Y-%m-%d"
            ).date()
        else:
            st.session_state["report_date"] = datetime.now().date()

    selected_date = st.session_state["report_date"]
    date_display = selected_date.strftime("%a, %d %b %Y")

    nav_col1, nav_col2, nav_col3 = st.columns([1, 4, 1])
    with nav_col1:
        if st.button("← Prev", key="report_prev_day", use_container_width=True):
            st.session_state["report_date"] -= timedelta(days=1)
            st.rerun()
    with nav_col2:
        st.markdown(
            f'<div class="date-display" style="text-align:center;">{date_display}</div>',
            unsafe_allow_html=True,
        )

    # Date picker below navigation for clearer access
    picked = st.date_input(
        "Select a date",
        value=selected_date,
        key="report_date_picker",
        help="Choose a date to view that day's report",
    )
    if picked != selected_date:
        st.session_state["report_date"] = picked
        st.rerun()
    with nav_col3:
        if st.button("Next →", key="report_next_day", use_container_width=True):
            st.session_state["report_date"] += timedelta(days=1)
            st.rerun()

    date_str = selected_date.strftime("%Y-%m-%d")
    outlets_bundle, summary = scope.get_daily_report_bundle(
        ctx.report_loc_ids, date_str
    )

    if summary:
        y_m = [int(x) for x in date_str.split("-")[:2]]
        multi_outlet = len(outlets_bundle) > 1

        def _col_head(nm: str, max_len: int = 20) -> str:
            nm = str(nm).strip()
            for prefix in ("Boteco - ", "Boteco-", "Boteco "):
                if nm.lower().startswith(prefix.lower()):
                    nm = nm[len(prefix) :].strip()
                    break
            return nm if len(nm) <= max_len else nm[: max_len - 1] + "…"

        # ── Compact KPI bar ──────────────────────────────────────
        with st.container(border=True):
            if multi_outlet:
                ncols = len(outlets_bundle) + 1
                st.caption("Each outlet vs **Combined** (same date).")

                def _metric(label, value, delta=None, extra_class=""):
                    delta_html = (
                        f'<span class="kpi-delta">{delta}</span>' if delta else ""
                    )
                    st.markdown(
                        f'<div class="kpi-item {extra_class}">'
                        f'<span class="kpi-label">{label}</span>'
                        f'<span class="kpi-value">{value}</span>'
                        f"{delta_html}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                cr = st.columns(ncols)
                for i, (_, oname, s) in enumerate(outlets_bundle):
                    with cr[i]:
                        _metric(
                            "Net sales",
                            utils.format_currency(s.get("net_total", 0)),
                        )
                with cr[-1]:
                    _metric(
                        "Net sales",
                        utils.format_currency(summary.get("net_total", 0)),
                        f"vs {utils.format_currency(summary.get('target', 0))} target",
                        "kpi-combined",
                    )

                cr = st.columns(ncols)
                for i, (_, _on, s) in enumerate(outlets_bundle):
                    with cr[i]:
                        _metric(
                            "Covers",
                            f"{int(s.get('covers') or 0):,}",
                            f"Turns {float(s.get('turns') or 0):.0f}",
                        )
                with cr[-1]:
                    lc, dc = (
                        summary.get("lunch_covers"),
                        summary.get("dinner_covers"),
                    )
                    foot = (
                        f"Lunch {lc:,} · Dinner {dc:,}"
                        if lc is not None and dc is not None
                        else None
                    )
                    _metric(
                        "Covers",
                        f"{int(summary.get('covers') or 0):,}",
                        foot or f"Turns: {float(summary.get('turns') or 0):.0f}",
                        "kpi-combined",
                    )

                cr = st.columns(ncols)
                for i, (_, _on, s) in enumerate(outlets_bundle):
                    with cr[i]:
                        _metric(
                            "APC",
                            utils.format_currency(s.get("apc", 0)),
                        )
                with cr[-1]:
                    _metric(
                        "APC",
                        utils.format_currency(summary.get("apc", 0)),
                        extra_class="kpi-combined",
                    )

                cr = st.columns(ncols)
                for i, (_, _on, s) in enumerate(outlets_bundle):
                    p = float(s.get("pct_target") or 0)
                    with cr[i]:
                        _metric(
                            "Target %",
                            utils.format_percent(p),
                        )
                with cr[-1]:
                    pct = float(summary.get("pct_target") or 0)
                    pct_delta = pct - 100
                    _metric(
                        "Target %",
                        utils.format_percent(pct),
                        f"{pct_delta:+.0f}% vs target",
                        "kpi-combined",
                    )
            else:
                _, _single_name, s_one = outlets_bundle[0]
                _oc = int(s_one.get("order_count") or 0)
                _aov = float(s_one.get("net_total") or 0) / _oc if _oc > 0 else 0.0

                def _metric(label, value, delta=None, extra_class=""):
                    delta_html = (
                        f'<span class="kpi-delta">{delta}</span>' if delta else ""
                    )
                    st.markdown(
                        f'<div class="kpi-item {extra_class}">'
                        f'<span class="kpi-label">{label}</span>'
                        f'<span class="kpi-value">{value}</span>'
                        f"{delta_html}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                kpis = st.columns(5)
                with kpis[0]:
                    _metric(
                        "Net Sales",
                        utils.format_currency(s_one.get("net_total", 0)),
                        f"vs {utils.format_currency(s_one.get('target', 0))} target",
                    )
                with kpis[1]:
                    _metric(
                        "Covers",
                        f"{int(s_one.get('covers') or 0):,}",
                        (
                            f"Lunch {s_one.get('lunch_covers'):,} · Dinner {s_one.get('dinner_covers'):,}"
                            if s_one.get("lunch_covers") is not None
                            and s_one.get("dinner_covers") is not None
                            else f"Turns: {float(s_one.get('turns') or 0):.0f}"
                        ),
                    )
                with kpis[2]:
                    _metric(
                        "APC",
                        utils.format_currency(s_one.get("apc", 0)),
                    )
                with kpis[3]:
                    _metric(
                        "Orders / AOV",
                        f"{_oc:,}",
                        utils.format_currency(_aov) + " avg" if _oc > 0 else None,
                    )
                with kpis[4]:
                    _metric(
                        "Target %",
                        utils.format_percent(float(s_one.get("pct_target") or 0)),
                        f"{float(s_one.get('pct_target') or 0) - 100:+.0f}% vs target",
                    )

        divider()

        divider()

        # Individual PNG sections
        per_outlet_sheet = (
            [(n, d) for _i, n, d in outlets_bundle] if multi_outlet else None
        )
        y_m = [int(x) for x in date_str.split("-")[:2]]
        per_outlet_cat = None
        per_outlet_svc = None
        if len(ctx.report_loc_ids) > 1:
            mtd_cat = database.get_category_mtd_totals_multi(
                ctx.report_loc_ids, y_m[0], y_m[1]
            )
            mtd_svc = database.get_service_mtd_totals_multi(
                ctx.report_loc_ids, y_m[0], y_m[1]
            )
            # Get per-outlet footfall metrics (monthly + weekly aggregated data)
            # Calculate date range: last 9 months for monthly, last 5 weeks for weekly
            _today = datetime.now().date()
            _end = _today.strftime("%Y-%m-%d")
            # 9 months back
            _start_mo = _today
            for _ in range(9):
                _m = _start_mo.month - 1
                if _m == 0:
                    _m = 12
                    _start_mo = _start_mo.replace(year=_start_mo.year - 1, month=_m)
                else:
                    _start_mo = _start_mo.replace(month=_m)
            _start_mo_str = _start_mo.replace(day=1).strftime("%Y-%m-%d")
            # 5 weeks back
            _start_wk = (_today - timedelta(weeks=5)).strftime("%Y-%m-%d")

            per_outlet_footfall_metrics = [
                (
                    name,
                    database.get_monthly_footfall_multi([lid], _start_mo_str, _end),
                    database.get_weekly_footfall_multi([lid], _start_wk, _end),
                )
                for lid, name, _ in outlets_bundle
            ]
            foot_rows = []
            per_outlet_footfall = None
            # Per-outlet MTD category & service for PNG sections
            per_outlet_cat = [
                (name, database.get_category_mtd_totals(lid, y_m[0], y_m[1]))
                for lid, name, _ in outlets_bundle
            ]
            per_outlet_svc = [
                (name, database.get_service_mtd_totals(lid, y_m[0], y_m[1]))
                for lid, name, _ in outlets_bundle
            ]
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

        with st.expander("Individual PNG sections", expanded=True):
            st.markdown("#### Individual sections")
            _sec_meta = [
                ("sales_summary", "Sales summary"),
                ("category", "Category sales"),
                ("service", "Service sales"),
            ]
            _sec_meta.extend(_footfall_sections())
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for key, title in _sec_meta:
                    b = section_bufs[key].getvalue()
                    zf.writestr(
                        f"boteco_{key}_{date_str}.png",
                        b,
                    )
            zip_buf.seek(0)
            dl_col, wa_col = st.columns([1, 1])
            with dl_col:
                st.download_button(
                    "Download ZIP",
                    zip_buf.getvalue(),
                    file_name=f"boteco_sections_{date_str}.zip",
                    mime="application/zip",
                    key=f"dl_zip_sections_{date_str}",
                    type="secondary",
                )

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
                    st.caption(title)
                    st.image(BytesIO(sec_bytes), use_container_width=True)
                    _wa_text = f"Boteco Bangalore EOD Report – {date_str} ({title})"
                    clipboard_ui.render_image_action_row(
                        sec_bytes,
                        f"boteco_{key}_{date_str}.png",
                        f"action_row_{key}_{date_str}",
                        share_text=_wa_text,
                        fallback_url=f"https://wa.me/?text={quote_plus(_wa_text)}",
                    )
    else:
        st.info(
            f"No saved data for **{selected_date.strftime('%d %b %Y')}**. "
            "Go to the **Upload** tab and import POS files for that date."
        )
