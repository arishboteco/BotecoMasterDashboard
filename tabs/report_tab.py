"""Report tab — Daily sales report, KPIs, and PNG report generation."""

from __future__ import annotations

import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st


import clipboard_ui
import config
import database
import scope
import sheet_reports as reports
import utils
from tabs import TabContext


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
        st.write("")
        if st.button("← Prev", key="report_prev_day", use_container_width=True):
            st.session_state["report_date"] -= timedelta(days=1)
            st.rerun()
    with nav_col2:
        st.markdown(
            f'<div class="date-display" style="text-align:center;">{date_display}</div>',
            unsafe_allow_html=True,
        )
        # Hidden date picker for calendar access
        picked = st.date_input(
            "Select Date",
            value=selected_date,
            key=f"report_date_picker_{selected_date.isoformat()}",
            label_visibility="collapsed",
        )
        if picked != selected_date:
            st.session_state["report_date"] = picked
            st.rerun()
    with nav_col3:
        st.write("")
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

        with st.container(border=True):
            if multi_outlet:
                ncols = len(outlets_bundle) + 1
                st.caption("Each outlet vs **Combined** (same date).")
                st.markdown("##### Net sales")
                cr = st.columns(ncols)
                for i, (_, oname, s) in enumerate(outlets_bundle):
                    with cr[i]:
                        st.metric(
                            _col_head(oname),
                            utils.format_currency(s.get("net_total", 0)),
                        )
                with cr[-1]:
                    st.metric(
                        "Combined",
                        utils.format_currency(summary.get("net_total", 0)),
                        delta=f"vs {utils.format_currency(summary.get('target', 0))} target",
                        delta_color="off",
                    )
                st.markdown("##### Covers")
                cr = st.columns(ncols)
                for i, (_, _on, s) in enumerate(outlets_bundle):
                    with cr[i]:
                        st.metric(
                            _col_head(_on),
                            f"{int(s.get('covers') or 0):,}",
                            delta=f"Turns {float(s.get('turns') or 0):.0f}",
                            delta_color="off",
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
                    st.metric(
                        "Combined",
                        f"{int(summary.get('covers') or 0):,}",
                        delta=foot or f"Turns: {float(summary.get('turns') or 0):.0f}",
                        delta_color="off",
                    )
                st.markdown("##### APC")
                cr = st.columns(ncols)
                for i, (_, _on, s) in enumerate(outlets_bundle):
                    with cr[i]:
                        st.metric(
                            _col_head(_on),
                            utils.format_currency(s.get("apc", 0)),
                        )
                with cr[-1]:
                    st.metric(
                        "Combined",
                        utils.format_currency(summary.get("apc", 0)),
                        help="Average per cover: net sales ÷ covers.",
                    )
                st.markdown("##### Target achievement (day)")
                cr = st.columns(ncols)
                for i, (_, _on, s) in enumerate(outlets_bundle):
                    p = float(s.get("pct_target") or 0)
                    with cr[i]:
                        st.metric(
                            _col_head(_on),
                            utils.format_percent(p),
                        )
                with cr[-1]:
                    pct = float(summary.get("pct_target") or 0)
                    pct_delta = pct - 100
                    st.metric(
                        "Combined",
                        utils.format_percent(pct),
                        delta=f"{pct_delta:+.0f}% vs target",
                        delta_color="normal",
                        help="Net sales for the day vs daily sales target.",
                    )
            else:
                _, _single_name, s_one = outlets_bundle[0]
                _oc = int(s_one.get("order_count") or 0)
                _aov = float(s_one.get("net_total") or 0) / _oc if _oc > 0 else 0.0
                col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
                with col_kpi1:
                    st.metric(
                        "Net Sales",
                        utils.format_currency(s_one.get("net_total", 0)),
                        delta=f"vs {utils.format_currency(s_one.get('target', 0))} target",
                        delta_color="off",
                    )
                with col_kpi2:
                    lc = s_one.get("lunch_covers")
                    dc = s_one.get("dinner_covers")
                    foot = (
                        f"Lunch {lc:,} · Dinner {dc:,}"
                        if lc is not None and dc is not None
                        else None
                    )
                    st.metric(
                        "Covers",
                        f"{int(s_one.get('covers') or 0):,}",
                        delta=foot or f"Turns: {float(s_one.get('turns') or 0):.0f}",
                        delta_color="off",
                    )
                with col_kpi3:
                    st.metric(
                        "APC",
                        utils.format_currency(s_one.get("apc", 0)),
                        help="Average per cover: net sales ÷ covers.",
                    )
                with col_kpi4:
                    st.metric(
                        "Orders / AOV",
                        f"{_oc:,}",
                        delta=utils.format_currency(_aov) + " avg" if _oc > 0 else None,
                        help="Unique orders (invoices) and Average Order Value.",
                    )
                with col_kpi5:
                    pct = float(s_one.get("pct_target") or 0)
                    pct_delta = pct - 100
                    st.metric(
                        "Target Achievement",
                        utils.format_percent(pct),
                        delta=f"{pct_delta:+.0f}% vs target",
                        delta_color="normal",
                        help="Net sales for the day vs daily sales target.",
                    )

        st.markdown("---")

        col_det1, col_det2 = st.columns(2)

        _pay_fields = [
            ("Gross Total", "gross_total"),
            ("Net Total", "net_total"),
            ("Cash", "cash_sales"),
            ("GPay", "gpay_sales"),
            ("Zomato", "zomato_sales"),
            ("Card", "card_sales"),
            ("Other", "other_sales"),
            ("Discount", "discount"),
            ("Complimentary", "complimentary"),
            ("Service Charge", "service_charge"),
            ("CGST", "cgst"),
            ("SGST", "sgst"),
        ]

        with col_det1:
            st.markdown("### 💰 Sales & Tax Breakdown")
            if multi_outlet:
                sd = {
                    "Line item": [x[0] for x in _pay_fields],
                }
                for _, oname, s in outlets_bundle:
                    sd[_col_head(oname, 12)] = [
                        utils.format_currency(float(s.get(f) or 0))
                        for _l, f in _pay_fields
                    ]
                sd["Combined"] = [
                    utils.format_currency(float(summary.get(f) or 0))
                    for _l, f in _pay_fields
                ]
                sales_df = pd.DataFrame(sd)
                st.dataframe(
                    sales_df,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                _, _sn, s_one = outlets_bundle[0]
                sales_data = {
                    "Line item": [x[0] for x in _pay_fields],
                    "Amount (₹)": [
                        utils.format_currency(float(s_one.get(f) or 0))
                        for _l, f in _pay_fields
                    ],
                }
                sales_df = pd.DataFrame(sales_data)
                st.dataframe(
                    sales_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Line item": st.column_config.TextColumn("Line item"),
                        "Amount (₹)": st.column_config.TextColumn("Amount (₹)"),
                    },
                )

        with col_det2:
            st.markdown("### 📊 MTD Summary")
            _mtd_rows = [
                ("Net Sales", "mtd_net_sales", "cur"),
                ("Total Covers", "mtd_total_covers", "int"),
                ("Avg Daily", "mtd_avg_daily", "cur"),
                ("Target", "mtd_target", "cur"),
                ("Achievement", "mtd_pct_target", "pct"),
            ]
            if multi_outlet:
                md = {"Metric": [x[0] for x in _mtd_rows]}
                for _, oname, s in outlets_bundle:
                    col_vals = []
                    for _lab, key, kind in _mtd_rows:
                        v = s.get(key, 0)
                        if kind == "int":
                            col_vals.append(f"{int(v or 0):,}")
                        elif kind == "pct":
                            col_vals.append(utils.format_percent(float(v or 0)))
                        else:
                            col_vals.append(utils.format_currency(float(v or 0)))
                    md[_col_head(oname, 12)] = col_vals
                md["Combined"] = []
                for _lab, key, kind in _mtd_rows:
                    v = summary.get(key, 0)
                    if kind == "int":
                        md["Combined"].append(f"{int(v or 0):,}")
                    elif kind == "pct":
                        md["Combined"].append(utils.format_percent(float(v or 0)))
                    else:
                        md["Combined"].append(utils.format_currency(float(v or 0)))
                st.dataframe(
                    pd.DataFrame(md),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                _, _sn, s_one = outlets_bundle[0]
                mtd_data = {
                    "Metric": [x[0] for x in _mtd_rows],
                    "Value": [],
                }
                for _lab, key, kind in _mtd_rows:
                    v = s_one.get(key, 0)
                    if kind == "int":
                        mtd_data["Value"].append(f"{int(v or 0):,}")
                    elif kind == "pct":
                        mtd_data["Value"].append(utils.format_percent(float(v or 0)))
                    else:
                        mtd_data["Value"].append(utils.format_currency(float(v or 0)))
                st.dataframe(
                    pd.DataFrame(mtd_data),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Metric": st.column_config.TextColumn("Metric"),
                        "Value": st.column_config.TextColumn("Value"),
                    },
                )

        st.markdown("---")

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
            st.download_button(
                "Download all sections (ZIP)",
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
                    "📱 WhatsApp (5 PNGs)",
                    f"share_5_pngs_{date_str}",
                    height=44,
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
                    cb1, cb2, cb3 = st.columns(3)
                    with cb1:
                        clipboard_ui.render_copy_image_button(
                            sec_bytes,
                            "Copy",
                            f"clip_sec_{key}_{date_str}",
                            height=44,
                            primary=False,
                        )
                    with cb2:
                        _wa_text = f"Boteco Bangalore EOD Report – {date_str} ({title})"
                        clipboard_ui.render_share_images_button(
                            [(f"boteco_{key}_{date_str}.png", sec_bytes)],
                            f"📱 WhatsApp ({title})",
                            f"share_sec_{key}_{date_str}",
                            height=44,
                            primary=False,
                            fallback_url=f"https://wa.me/?text={quote_plus(_wa_text)}",
                        )
                    with cb3:
                        st.download_button(
                            "PNG",
                            sec_bytes,
                            file_name=f"boteco_{key}_{date_str}.png",
                            mime="image/png",
                            key=f"dl_sec_{key}_{date_str}",
                            type="secondary",
                        )

        # ── Monthly Footfall Summary ─────────────────────────────
        st.markdown("---")
        st.markdown("### Monthly Footfall Summary")
        st.caption("Last 12 months of covers data.")

        _today = datetime.now().date()
        _start = _today.replace(day=1)
        # Go back 11 months to get 12 months total
        for _ in range(11):
            _m = _start.month - 1
            if _m == 0:
                _m = 12
                _start = _start.replace(year=_start.year - 1, month=_m)
            else:
                _start = _start.replace(month=_m)

        _start_str = _start.strftime("%Y-%m-%d")
        _as_of = _today - timedelta(days=1)
        _end_str = _as_of.strftime("%Y-%m-%d")

        _monthly_rows = database.get_monthly_footfall_multi(
            ctx.report_loc_ids, _start_str, _end_str
        )

        if _monthly_rows:
            _df_m = pd.DataFrame(_monthly_rows)
            _df_m["month_label"] = _df_m["month"].apply(
                lambda x: datetime.strptime(f"{x}-01", "%Y-%m-%d").strftime("%b-%Y")
            )
            _df_m["footfall"] = _df_m["covers"].astype(int)
            _df_m["total_days"] = _df_m["total_days"].astype(int)
            _df_m["daily_avg"] = (
                (_df_m["footfall"] / _df_m["total_days"].replace(0, pd.NA))
                .round(0)
                .fillna(0)
                .astype(int)
            )

            # Month-over-month % change
            _df_m["pct_footfall"] = (
                _df_m["footfall"]
                .pct_change()
                .replace([float("inf"), float("-inf")], pd.NA)
            )
            _df_m["pct_avg"] = (
                _df_m["daily_avg"]
                .pct_change()
                .replace([float("inf"), float("-inf")], pd.NA)
            )

            # Format for display
            _display = pd.DataFrame(
                {
                    "Month": _df_m["month_label"],
                    "Footfall": _df_m["footfall"].apply(lambda x: f"{x:,}"),
                    "% Change": _df_m["pct_footfall"].apply(
                        lambda x: utils.format_percent(x * 100) if pd.notna(x) else ""
                    ),
                    "Total Days": _df_m["total_days"].astype(int),
                    "Daily Avg.": _df_m["daily_avg"].apply(lambda x: f"{x:,}"),
                    "Avg % Change": _df_m["pct_avg"].apply(
                        lambda x: utils.format_percent(x * 100) if pd.notna(x) else ""
                    ),
                }
            )

            st.dataframe(
                _display,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No monthly footfall data available.")
    else:
        st.info(
            f"No saved data for **{selected_date.strftime('%d %b %Y')}**. "
            "Go to the **Upload** tab and import POS files for that date."
        )
