import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Optional, Tuple, NamedTuple, Any
import config

# Modern report palette (aligned with dashboard coral; calm neutrals)
CLR_BG_PAGE = "#f1f5f9"
CLR_HEADER = "#0f172a"
CLR_HEADER_TEXT = "#ffffff"
CLR_BAND = "#e2e8f0"
CLR_ROW = "#ffffff"
CLR_ZERO = "#f8fafc"
CLR_ZERO_TEXT = "#64748b"
CLR_ACCENT_SOFT = "#fff1f2"
CLR_FOOTER_DARK = "#1e293b"
CLR_FOOTER_TEXT = "#f8fafc"
CLR_BORDER = "#e2e8f0"
CLR_TEXT = "#0f172a"
CLR_TEXT_MUTED = "#475569"

FONT_SANS = "DejaVu Sans"

# Composite layout: clearer gaps between the four blocks
_COMPOSITE_HSPACE = 0.52
_COMPOSITE_PAD_INCHES = 0.32
CELL_LW = 0.35


def _rupee(n: float) -> str:
    if n is None:
        n = 0.0
    n = float(n)
    if abs(n - round(n)) < 0.01:
        return f"₹{int(round(n)):,}"
    return f"₹{n:,.2f}"


def _pct(n: float) -> str:
    return f"{n:.2f}%"


def _sheet_date_label(iso_date: str) -> str:
    try:
        dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
    except ValueError:
        return iso_date
    return f"{dt.strftime('%a')}, {dt.day} {dt.strftime('%b %Y')}"


def _style_table(tbl, fontsize: float = 8.25) -> None:
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    for cell in tbl.get_celld().values():
        cell.set_text_props(fontfamily=FONT_SANS)
    tbl.scale(1, 1.88)


def generate_whatsapp_text(
    report_data: Dict,
    location_name: str = "Boteco Bangalore",
    per_outlet: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
) -> str:
    """Generate WhatsApp formatted text report."""

    date_str = report_data.get("date", datetime.now().strftime("%d-%b-%Y"))

    # Calculate payment breakdown percentages
    net_total = report_data.get("net_total", 0)
    cash_pct = (
        (report_data.get("cash_sales", 0) / net_total * 100) if net_total > 0 else 0
    )
    card_pct = (
        (report_data.get("card_sales", 0) / net_total * 100) if net_total > 0 else 0
    )
    gpay_pct = (
        (report_data.get("gpay_sales", 0) / net_total * 100) if net_total > 0 else 0
    )
    zomato_pct = (
        (report_data.get("zomato_sales", 0) / net_total * 100) if net_total > 0 else 0
    )

    # Status emoji
    pct_target = report_data.get("pct_target", 0)
    if pct_target >= 100:
        status_emoji = "✅"
        status_text = "Target Achieved!"
    elif pct_target >= 90:
        status_emoji = "⚠️"
        status_text = "Almost There"
    else:
        status_emoji = "🔴"
        status_text = "Below Target"

    # Category breakdown
    categories = report_data.get("categories", [])
    category_text = ""
    if categories:
        for cat in categories:
            cat_total = sum(c.get("amount", 0) for c in categories)
            cat_pct = (cat.get("amount", 0) / cat_total * 100) if cat_total > 0 else 0
            amount_str = config.CURRENCY_FORMAT.format(cat.get("amount", 0))
            category_text += (
                f"• {cat.get('category', 'N/A')}: {cat_pct:.0f}% ({amount_str})\n"
            )
    else:
        category_text = "• Data not available\n"

    # Build report
    report = f"""
━━━━━━━━━━━━━━━━━━━━━━
🥂 {location_name.upper()}
📅 End of Day Report
📆 {date_str}
━━━━━━━━━━━━━━━━━━━━━━

💰 SALES SUMMARY
• Gross Total: {config.CURRENCY_FORMAT.format(report_data.get("gross_total", 0))}
• Net Total: {config.CURRENCY_FORMAT.format(net_total)}
• Covers: {report_data.get("covers", 0)} | Turns: {report_data.get("turns", 0):.1f}
• APC: {config.CURRENCY_FORMAT.format(report_data.get("apc", 0))}

💳 PAYMENT BREAKDOWN
• Cash: {config.CURRENCY_FORMAT.format(report_data.get("cash_sales", 0))} ({cash_pct:.0f}%)
• GPay: {config.CURRENCY_FORMAT.format(report_data.get("gpay_sales", 0))} ({gpay_pct:.0f}%)
• Zomato: {config.CURRENCY_FORMAT.format(report_data.get("zomato_sales", 0))} ({zomato_pct:.0f}%)
• Card: {config.CURRENCY_FORMAT.format(report_data.get("card_sales", 0))} ({card_pct:.0f}%)

📊 VS TARGET
• Target: {config.CURRENCY_FORMAT.format(report_data.get("target", 0))}
• Achievement: {pct_target:.1f}%
{status_emoji} Status: {status_text}

🍽️ CATEGORY MIX
{category_text}👥 MTD SUMMARY
• Total Covers: {report_data.get("mtd_total_covers", 0):,}
• Net Sales: {config.CURRENCY_FORMAT.format(report_data.get("mtd_net_sales", 0))}
• Avg Daily: {config.CURRENCY_FORMAT.format(report_data.get("mtd_avg_daily", 0))}
• % of Target: {report_data.get("mtd_pct_target", 0):.1f}%
"""

    if per_outlet and len(per_outlet) >= 2:
        po_lines = "\n".join(
            f"• {nm}: Net {config.CURRENCY_FORMAT.format(d.get('net_total', 0))} | "
            f"Covers {int(d.get('covers') or 0):,}"
            for nm, d in per_outlet
        )
        report += f"""
🏪 PER OUTLET
{po_lines}
"""

    report += "━━━━━━━━━━━━━━━━━━━━━━"

    return report.strip()


def _cell_kind_bg(kind: str) -> str:
    if kind == "hdr":
        return CLR_HEADER
    if kind == "teal":
        return CLR_BAND
    if kind == "tan":
        return CLR_ACCENT_SOFT
    if kind == "pink":
        return CLR_ZERO
    if kind == "dk":
        return CLR_FOOTER_DARK
    return CLR_ROW


def _fg_for_bg(bg: str) -> str:
    if bg == CLR_HEADER:
        return CLR_HEADER_TEXT
    if bg == CLR_FOOTER_DARK:
        return CLR_FOOTER_TEXT
    if bg == CLR_ZERO:
        return CLR_ZERO_TEXT
    return CLR_TEXT


def _apply_cell_frame(cell) -> None:
    cell.set_edgecolor(CLR_BORDER)
    cell.set_linewidth(CELL_LW)


class SheetStyleTables(NamedTuple):
    sales_text: List[List[str]]
    sales_kinds: List[Tuple[str, ...]]
    cat_text: List[List[str]]
    cat_rows_kinds: List[Tuple[str, str, str]]
    svc_text: List[List[str]]
    svc_rows_kinds: List[Tuple[str, str, str]]
    ft_text: List[List[str]]
    ft_kinds: List[Tuple[str, str, str, str]]


def _build_sheet_style_tables(
    report_data: Dict,
    location_name: str,
    mtd_category: Dict[str, float],
    mtd_service: Dict[str, float],
    month_footfall_rows: List[Dict],
) -> SheetStyleTables:
    mtd_category = dict(mtd_category or {})
    mtd_service = dict(mtd_service or {})
    month_footfall_rows = list(month_footfall_rows or [])

    iso = str(report_data.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    r = report_data

    def zpay(label: str, val: float) -> Tuple[str, str, str, str]:
        v = float(val or 0)
        kind_r = "pink" if v == 0 else "white"
        kind_l = "pink" if v == 0 else "white"
        return (label, _rupee(v), kind_l, kind_r)

    sales_text: List[List[str]] = []
    sales_kinds: List[Tuple[str, str]] = []

    sales_text.append([day_lbl, "Sales Summary"])
    sales_kinds.append(("hdr", "hdr"))
    sales_text.append(["Payment Mode", location_name[:20]])
    sales_kinds.append(("hdr", "hdr"))
    _cov = int(r.get("covers") or 0)
    _turn = float(r.get("turns") or 0)
    sales_text.append(["Covers / turns", f"{_cov:,} · {_turn:.1f}"])
    sales_kinds.append(("teal", "teal"))

    for label, val in [
        ("Cash Sales", r.get("cash_sales", 0)),
        ("Gpay", r.get("gpay_sales", 0)),
        ("Zomato Gold", r.get("zomato_sales", 0)),
        ("Bill On Hold", 0),
        ("Credit Card Sales", r.get("card_sales", 0)),
        ("AMEX Sales", 0),
        ("Coupon Sale", 0),
        ("Online Bank Transfer", 0),
        ("Other / Wallet", r.get("other_sales", 0)),
    ]:
        fv = float(val or 0)
        if fv == 0:
            continue
        row = zpay(label, fv)
        sales_text.append([row[0], row[1]])
        sales_kinds.append((row[2], row[3]))

    sales_text.append(["EOD Gross Total", _rupee(r.get("gross_total", 0))])
    sales_kinds.append(("tan", "tan"))
    sales_text.append(["CGST@2.5%", _rupee(r.get("cgst", 0))])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(["SGST@2.5%", _rupee(r.get("sgst", 0))])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(["Service Charge@10%", _rupee(r.get("service_charge", 0))])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(["Discount", _rupee(r.get("discount", 0))])
    d0 = float(r.get("discount") or 0)
    sales_kinds.append(("pink", "pink") if d0 == 0 else ("white", "white"))
    sales_text.append(["EOD Net Total", _rupee(r.get("net_total", 0))])
    sales_kinds.append(("tan", "tan"))

    mtd_cov = int(r.get("mtd_total_covers") or 0)
    mtd_net = float(r.get("mtd_net_sales") or 0)
    apc_m = (mtd_net / mtd_cov) if mtd_cov > 0 else 0.0
    sales_text.append(["MTD Total Covers", f"{mtd_cov:,}"])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(["APC For The Day", _rupee(r.get("apc", 0))])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(["APC For The Month", _rupee(apc_m)])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(["Complimentary", _rupee(r.get("complimentary", 0))])
    cq = float(r.get("complimentary") or 0)
    sales_kinds.append(("pink", "pink") if cq == 0 else ("tan", "tan"))
    sales_text.append(["Daily Avg. Net Sales", _rupee(r.get("mtd_avg_daily", 0))])
    sales_kinds.append(("tan", "tan"))
    sales_text.append(["MTD Net Sales", _rupee(mtd_net)])
    sales_kinds.append(("dk", "dk"))
    sales_text.append(["MTD Discount", _rupee(r.get("mtd_discount", 0))])
    sales_kinds.append(("dk", "dk"))
    mtd_tgt = float(r.get("mtd_target") or config.MONTHLY_TARGET)
    sales_text.append(["Sales Target (month)", _rupee(mtd_tgt)])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(
        ["Percentage of Target (MTD)", _pct(float(r.get("mtd_pct_target") or 0))]
    )
    sales_kinds.append(("dk", "dk"))

    total_cat_mtd = sum(mtd_category.values()) or 1.0
    std_cats = [
        "Food",
        "Liquor",
        "Beer",
        "Soft Beverages",
        "Coffee",
        "Tobacco",
    ]
    daily_cat = {
        c.get("category"): float(c.get("amount") or 0) for c in r.get("categories") or []
    }
    cat_order = [x for x in std_cats if x in daily_cat or mtd_category.get(x)]
    for k in sorted(mtd_category.keys()):
        if k not in cat_order:
            cat_order.append(k)
    if not cat_order:
        cat_order = ["—"]

    cat_text: List[List[str]] = []
    cat_text.append([f"Category Sales — {location_name[:24]}", day_lbl, "MTD"])
    cat_rows_kinds: List[Tuple[str, str, str]] = [("hdr", "hdr", "hdr")]
    cat_text.append(["Category & MTD %", "Daily", "MTD"])
    cat_rows_kinds.append(("hdr", "hdr", "hdr"))
    daily_cat_total = 0.0
    mtd_cat_total = 0.0
    for name in cat_order:
        d_amt = daily_cat.get(name, 0.0) if name != "—" else 0.0
        m_amt = float(mtd_category.get(name, 0) or 0) if name != "—" else 0.0
        daily_cat_total += d_amt
        mtd_cat_total += m_amt
        pct_lbl = int(round(100 * m_amt / total_cat_mtd)) if total_cat_mtd > 0 else 0
        label = f"{name} ({pct_lbl:02d}%)" if name != "—" else "No category data"
        row_kind = (
            ("pink", "pink", "pink")
            if d_amt == 0 and m_amt == 0
            else ("white", "white", "white")
        )
        cat_text.append([label, _rupee(d_amt), _rupee(m_amt)])
        cat_rows_kinds.append(row_kind)
    cat_text.append(["Total", _rupee(daily_cat_total), _rupee(mtd_cat_total)])
    cat_rows_kinds.append(("hdr", "hdr", "hdr"))

    std_svc = ["Breakfast", "Lunch", "Dinner", "Delivery", "Events", "Party"]
    daily_svc = {
        s.get("service_type") or s.get("type"): float(s.get("amount") or 0)
        for s in r.get("services") or []
    }
    svc_order = [x for x in std_svc if x in daily_svc or mtd_service.get(x)]
    for k in sorted(mtd_service.keys()):
        if k not in svc_order:
            svc_order.append(k)
    if not svc_order:
        svc_order = ["—"]

    total_svc_mtd = sum(mtd_service.values()) or 1.0
    svc_text: List[List[str]] = []
    svc_text.append([f"Service Sales — {location_name[:24]}", day_lbl, "MTD"])
    svc_rows_kinds: List[Tuple[str, str, str]] = [("hdr", "hdr", "hdr")]
    svc_text.append(["Service & MTD %", "Daily", "MTD"])
    svc_rows_kinds.append(("hdr", "hdr", "hdr"))
    daily_svc_total = 0.0
    mtd_svc_total = 0.0
    for name in svc_order:
        d_amt = daily_svc.get(name, 0.0) if name != "—" else 0.0
        m_amt = float(mtd_service.get(name, 0) or 0) if name != "—" else 0.0
        daily_svc_total += d_amt
        mtd_svc_total += m_amt
        pct_lbl = int(round(100 * m_amt / total_svc_mtd)) if total_svc_mtd > 0 else 0
        label = f"{name} ({pct_lbl:02d}%)" if name != "—" else "No service data"
        row_kind = (
            ("pink", "pink", "pink")
            if d_amt == 0 and m_amt == 0
            else ("white", "white", "white")
        )
        svc_text.append([label, _rupee(d_amt), _rupee(m_amt)])
        svc_rows_kinds.append(row_kind)
    svc_text.append(["Total", _rupee(daily_svc_total), _rupee(mtd_svc_total)])
    svc_rows_kinds.append(("hdr", "hdr", "hdr"))

    ft_text: List[List[str]] = []
    ft_kinds: List[Tuple[str, str, str, str]] = []
    ft_text.append(["Daily footfall (month)", "Dinner", "Lunch", "Total"])
    ft_kinds.append(("hdr", "hdr", "hdr", "hdr"))
    for row in month_footfall_rows:
        ds = str(row.get("date", ""))[:10]
        lc = row.get("lunch_covers")
        dcv = row.get("dinner_covers")
        cov = int(row.get("covers") or 0)
        if lc is not None and dcv is not None:
            di = int(dcv or 0)
            lu = int(lc or 0)
            tot = di + lu
        else:
            di = lu = 0
            tot = cov
        ft_text.append([_sheet_date_label(ds), str(di), str(lu), str(tot)])
        ft_kinds.append(("white", "white", "white", "white"))

    return SheetStyleTables(
        sales_text=sales_text,
        sales_kinds=sales_kinds,
        cat_text=cat_text,
        cat_rows_kinds=cat_rows_kinds,
        svc_text=svc_text,
        svc_rows_kinds=svc_rows_kinds,
        ft_text=ft_text,
        ft_kinds=ft_kinds,
    )


def _short_outlet_name(name: str, max_len: int = 16) -> str:
    name = (name or "").strip()
    if len(name) <= max_len:
        return name
    return name[: max_len - 1] + "…"


def _pay_kinds(amounts: List[float]) -> Tuple[str, ...]:
    return tuple("pink" if float(a or 0) == 0 else "white" for a in amounts)


def _build_sheet_style_tables_multi(
    outlets: List[Tuple[str, Dict[str, Any]]],
    combined: Dict[str, Any],
    mtd_category: Dict[str, float],
    mtd_service: Dict[str, float],
    month_footfall_rows: List[Dict],
    location_title: str,
) -> SheetStyleTables:
    """Sales grid: Label | Outlet1 | … | Combined. Category/service/footfall stay combined-only."""
    base = _build_sheet_style_tables(
        combined,
        location_title,
        mtd_category,
        mtd_service,
        month_footfall_rows,
    )
    if len(outlets) < 2:
        return base

    n = len(outlets)
    ncols = n + 2
    rs: List[List[str]] = []
    rk: List[Tuple[str, ...]] = []
    iso = str(combined.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    names = [_short_outlet_name(nm) for nm, _ in outlets]
    c = combined
    ovs = [d for _, d in outlets]

    def row_hdr_teal(cells: List[str]) -> None:
        rs.append(cells)
        rk.append(tuple(["teal"] * ncols))

    rs.append([day_lbl, "Sales summary"] + [""] * n)
    rk.append(tuple(["hdr"] * ncols))
    rs.append(["Payment mode"] + names + ["Combined"])
    rk.append(tuple(["hdr"] * ncols))

    cov_turn_row = ["Covers / turns"]
    for o in ovs:
        ci = int(o.get("covers") or 0)
        ti = float(o.get("turns") or 0)
        cov_turn_row.append(f"{ci:,} · {ti:.1f}")
    cov_turn_row.append(
        f"{int(c.get('covers') or 0):,} · {float(c.get('turns') or 0):.1f}"
    )
    row_hdr_teal(cov_turn_row)

    pay_keys = [
        ("Cash Sales", "cash_sales"),
        ("Gpay", "gpay_sales"),
        ("Zomato Gold", "zomato_sales"),
        ("Bill On Hold", None),
        ("Credit Card Sales", "card_sales"),
        ("AMEX Sales", None),
        ("Coupon Sale", None),
        ("Online Bank Transfer", None),
        ("Other / Wallet", "other_sales"),
    ]
    for label, key in pay_keys:
        if key is None:
            vals = [0.0] * n + [0.0]
        else:
            vals = [float(o.get(key) or 0) for o in ovs] + [float(c.get(key) or 0)]
        if all(float(v or 0) == 0 for v in vals):
            continue
        cells = [label] + [_rupee(v) for v in vals]
        rs.append(cells)
        rk.append(("white",) + _pay_kinds(vals))

    gross_vals = [float(o.get("gross_total") or 0) for o in ovs] + [
        float(c.get("gross_total") or 0)
    ]
    rs.append(["EOD Gross Total"] + [_rupee(v) for v in gross_vals])
    rk.append(("tan",) + tuple(["tan"] * (n + 1)))

    for lbl, key in [
        ("CGST@2.5%", "cgst"),
        ("SGST@2.5%", "sgst"),
        ("Service Charge@10%", "service_charge"),
    ]:
        vals = [float(o.get(key) or 0) for o in ovs] + [float(c.get(key) or 0)]
        row_hdr_teal([lbl] + [_rupee(v) for v in vals])

    disc = [float(o.get("discount") or 0) for o in ovs] + [float(c.get("discount") or 0)]
    rs.append(["Discount"] + [_rupee(v) for v in disc])
    rk.append(("white",) + _pay_kinds(disc))

    net_vals = [float(o.get("net_total") or 0) for o in ovs] + [
        float(c.get("net_total") or 0)
    ]
    rs.append(["EOD Net Total"] + [_rupee(v) for v in net_vals])
    rk.append(("tan",) + tuple(["tan"] * (n + 1)))

    mtd_cov = [int(o.get("mtd_total_covers") or 0) for o in ovs]
    mtd_cov_c = int(c.get("mtd_total_covers") or 0)
    row_hdr_teal(
        ["MTD Total Covers"]
        + [f"{x:,}" for x in mtd_cov]
        + [f"{mtd_cov_c:,}"]
    )

    apc_d = [float(o.get("apc") or 0) for o in ovs]
    row_hdr_teal(["APC For The Day"] + [_rupee(x) for x in apc_d] + [_rupee(c.get("apc", 0))])

    apc_m_list = []
    for o in ovs:
        mc = int(o.get("mtd_total_covers") or 0)
        mn = float(o.get("mtd_net_sales") or 0)
        apc_m_list.append((mn / mc) if mc > 0 else 0.0)
    mc_c = int(c.get("mtd_total_covers") or 0)
    mn_c = float(c.get("mtd_net_sales") or 0)
    apc_m_c = (mn_c / mc_c) if mc_c > 0 else 0.0
    row_hdr_teal(
        ["APC For The Month"]
        + [_rupee(x) for x in apc_m_list]
        + [_rupee(apc_m_c)]
    )

    comp = [float(o.get("complimentary") or 0) for o in ovs] + [
        float(c.get("complimentary") or 0)
    ]
    comp_kinds = tuple("pink" if float(v or 0) == 0 else "tan" for v in comp)
    rs.append(["Complimentary"] + [_rupee(v) for v in comp])
    rk.append(("white",) + comp_kinds)

    mtd_avg = [float(o.get("mtd_avg_daily") or 0) for o in ovs] + [
        float(c.get("mtd_avg_daily") or 0)
    ]
    rs.append(["Daily Avg. Net Sales"] + [_rupee(v) for v in mtd_avg])
    rk.append(("tan",) + tuple(["tan"] * (n + 1)))

    mtd_net = [float(o.get("mtd_net_sales") or 0) for o in ovs] + [
        float(c.get("mtd_net_sales") or 0)
    ]
    rs.append(["MTD Net Sales"] + [_rupee(v) for v in mtd_net])
    rk.append(("dk",) + tuple(["dk"] * (n + 1)))

    mtd_disc = [float(o.get("mtd_discount") or 0) for o in ovs] + [
        float(c.get("mtd_discount") or 0)
    ]
    rs.append(["MTD Discount"] + [_rupee(v) for v in mtd_disc])
    rk.append(("dk",) + tuple(["dk"] * (n + 1)))

    mtd_tgt = float(c.get("mtd_target") or config.MONTHLY_TARGET)
    row_hdr_teal(
        ["Sales Target (month)"] + [_rupee(mtd_tgt)] * (n + 1)
    )

    pct_row = ["Percentage of Target (MTD)"] + [
        _pct(float(o.get("mtd_pct_target") or 0)) for o in ovs
    ] + [_pct(float(c.get("mtd_pct_target") or 0))]
    rs.append(pct_row)
    rk.append(("dk",) + tuple(["dk"] * (n + 1)))

    return SheetStyleTables(
        sales_text=rs,
        sales_kinds=rk,
        cat_text=base.cat_text,
        cat_rows_kinds=base.cat_rows_kinds,
        svc_text=base.svc_text,
        svc_rows_kinds=base.svc_rows_kinds,
        ft_text=base.ft_text,
        ft_kinds=base.ft_kinds,
    )


def _emphasize_row_text(cell, kind_key: str) -> None:
    if kind_key in ("hdr", "dk", "tan"):
        cell.get_text().set_weight("bold")


def _paint_sales_table(ax, tables: SheetStyleTables) -> None:
    ax.axis("off")
    st = tables.sales_text
    if not st:
        return
    ncols = len(st[0])
    w0 = min(0.44, 0.26 + 0.06 * max(0, 4 - ncols))
    rest = max(0.08, (1.0 - w0) / max(1, ncols - 1))
    col_widths = [w0] + [rest] * (ncols - 1)
    if abs(sum(col_widths) - 1.0) > 0.02:
        scale = 1.0 / sum(col_widths)
        col_widths = [w * scale for w in col_widths]

    fs = 7.35 if ncols > 4 else 8.25
    t1 = ax.table(
        cellText=st,
        loc="upper center",
        cellLoc="right",
        colWidths=col_widths,
    )
    _style_table(t1, fs)
    sk = tables.sales_kinds
    for i in range(len(st)):
        row = st[i]
        n_j = len(row)
        for j in range(ncols):
            c = t1[(i, j)]
            kk = sk[i] if i < len(sk) else tuple(["white"] * ncols)
            kind_key = kk[j] if j < len(kk) else "white"
            bg = _cell_kind_bg(kind_key)
            c.set_facecolor(bg)
            fg = _fg_for_bg(bg)
            c.set_text_props(color=fg, fontfamily=FONT_SANS)
            c.get_text().set_ha("left" if j == 0 else "right")
            _apply_cell_frame(c)
            if i < 2:
                c.get_text().set_weight("bold")
                c.get_text().set_fontsize(fs + 0.85)
            else:
                _emphasize_row_text(c, kind_key)
    t1[(0, 0)].get_text().set_ha("left")
    if ncols > 1:
        t1[(0, 1)].get_text().set_ha("right")


def _paint_category_table(ax, tables: SheetStyleTables) -> None:
    ax.axis("off")
    t2 = ax.table(
        cellText=tables.cat_text,
        loc="upper center",
        cellLoc="right",
        colWidths=[0.5, 0.22, 0.22],
    )
    _style_table(t2, 8.0)
    for i in range(len(tables.cat_text)):
        for j in range(3):
            c = t2[(i, j)]
            kk = tables.cat_rows_kinds[i][j]
            bg = _cell_kind_bg(kk)
            c.set_facecolor(bg)
            fg = _fg_for_bg(bg)
            c.set_text_props(color=fg, fontfamily=FONT_SANS)
            c.get_text().set_ha("right" if j else "left")
            _apply_cell_frame(c)
            if i < 2:
                c.get_text().set_weight("bold")
                c.get_text().set_fontsize(9.0)
            else:
                _emphasize_row_text(c, kk)


def _paint_service_table(ax, tables: SheetStyleTables) -> None:
    ax.axis("off")
    t3 = ax.table(
        cellText=tables.svc_text,
        loc="upper center",
        cellLoc="right",
        colWidths=[0.5, 0.22, 0.22],
    )
    _style_table(t3, 8.0)
    for i in range(len(tables.svc_text)):
        for j in range(3):
            c = t3[(i, j)]
            kk = tables.svc_rows_kinds[i][j]
            bg = _cell_kind_bg(kk)
            c.set_facecolor(bg)
            fg = _fg_for_bg(bg)
            c.set_text_props(color=fg, fontfamily=FONT_SANS)
            c.get_text().set_ha("right" if j else "left")
            _apply_cell_frame(c)
            if i < 2:
                c.get_text().set_weight("bold")
                c.get_text().set_fontsize(9.0)
            else:
                _emphasize_row_text(c, kk)


def _paint_footfall_table(ax, tables: SheetStyleTables) -> None:
    ax.axis("off")
    if len(tables.ft_text) <= 1:
        ax.text(
            0.5,
            0.5,
            "No footfall rows for month",
            ha="center",
            va="center",
            fontsize=9.5,
            color=CLR_TEXT_MUTED,
            fontfamily=FONT_SANS,
        )
        return
    t4 = ax.table(
        cellText=tables.ft_text,
        loc="upper center",
        cellLoc="right",
        colWidths=[0.42, 0.18, 0.18, 0.18],
    )
    _style_table(t4, 8.0)
    for i in range(len(tables.ft_text)):
        for j in range(4):
            c = t4[(i, j)]
            kk = tables.ft_kinds[i][j] if i < len(tables.ft_kinds) else "white"
            bg = _cell_kind_bg(kk)
            c.set_facecolor(bg)
            fg = _fg_for_bg(bg)
            c.set_text_props(color=fg, fontfamily=FONT_SANS)
            c.get_text().set_ha("right" if j else "left")
            _apply_cell_frame(c)
            if i < 1:
                c.get_text().set_weight("bold")
                c.get_text().set_fontsize(9.0)
            else:
                _emphasize_row_text(c, kk)


def _fig_height_for_rows(n_rows: int, min_rows: int = 4, cap: float = 24.0) -> float:
    n = max(n_rows, min_rows)
    return min(cap, 1.2 + 0.22 * n)


def _save_figure_png(fig) -> BytesIO:
    buf = BytesIO()
    fig.savefig(
        buf,
        format="png",
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
        pad_inches=_COMPOSITE_PAD_INCHES,
    )
    plt.close(fig)
    buf.seek(0)
    return buf


def _sheet_tables(
    report_data: Dict,
    location_name: str,
    mtd_category: Optional[Dict[str, float]],
    mtd_service: Optional[Dict[str, float]],
    month_footfall_rows: Optional[List[Dict]],
    per_outlet_summaries: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
) -> SheetStyleTables:
    mc = dict(mtd_category or {})
    ms = dict(mtd_service or {})
    mf = list(month_footfall_rows or [])
    if per_outlet_summaries and len(per_outlet_summaries) >= 2:
        return _build_sheet_style_tables_multi(
            list(per_outlet_summaries),
            report_data,
            mc,
            ms,
            mf,
            location_name,
        )
    return _build_sheet_style_tables(
        report_data, location_name, mc, ms, mf
    )


def _sales_fig_width(tables: SheetStyleTables) -> float:
    nc = len(tables.sales_text[0]) if tables.sales_text else 2
    if nc > 4:
        return 12.0
    if nc > 2:
        return 11.0
    return 10.0


def generate_sheet_style_report_sections(
    report_data: Dict,
    location_name: str = "Boteco Bangalore",
    mtd_category: Optional[Dict[str, float]] = None,
    mtd_service: Optional[Dict[str, float]] = None,
    month_footfall_rows: Optional[List[Dict]] = None,
    per_outlet_summaries: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
) -> Dict[str, BytesIO]:
    """
    Four separate PNGs: sales_summary, category, service, footfall.
    Same styling as the composite sheet report.
    """
    tables = _sheet_tables(
        report_data,
        location_name,
        mtd_category,
        mtd_service,
        month_footfall_rows,
        per_outlet_summaries,
    )
    out: Dict[str, BytesIO] = {}

    fig_h = _fig_height_for_rows(len(tables.sales_text), 6)
    fig_w = _sales_fig_width(tables)
    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=120)
    fig.patch.set_facecolor(CLR_BG_PAGE)
    _paint_sales_table(ax, tables)
    out["sales_summary"] = _save_figure_png(fig)

    fig_h = _fig_height_for_rows(len(tables.cat_text), 4)
    fig, ax = plt.subplots(1, 1, figsize=(10, fig_h), dpi=120)
    fig.patch.set_facecolor(CLR_BG_PAGE)
    _paint_category_table(ax, tables)
    out["category"] = _save_figure_png(fig)

    fig_h = _fig_height_for_rows(len(tables.svc_text), 4)
    fig, ax = plt.subplots(1, 1, figsize=(10, fig_h), dpi=120)
    fig.patch.set_facecolor(CLR_BG_PAGE)
    _paint_service_table(ax, tables)
    out["service"] = _save_figure_png(fig)

    ft_n = max(len(tables.ft_text), 3)
    fig_h = _fig_height_for_rows(ft_n, 3)
    fig, ax = plt.subplots(1, 1, figsize=(10, fig_h), dpi=120)
    fig.patch.set_facecolor(CLR_BG_PAGE)
    _paint_footfall_table(ax, tables)
    out["footfall"] = _save_figure_png(fig)

    return out


def generate_sheet_style_report_image(
    report_data: Dict,
    location_name: str = "Boteco Bangalore",
    mtd_category: Optional[Dict[str, float]] = None,
    mtd_service: Optional[Dict[str, float]] = None,
    month_footfall_rows: Optional[List[Dict]] = None,
    per_outlet_summaries: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
) -> BytesIO:
    """
    Composite PNG styled like the Google Sheet EOD dashboard: Sales Summary,
    Category Sales, Service Sales, and optional footfall grid for the month.
    """
    tables = _sheet_tables(
        report_data,
        location_name,
        mtd_category,
        mtd_service,
        month_footfall_rows,
        per_outlet_summaries,
    )

    n1, n2, n3, n4 = (
        len(tables.sales_text),
        len(tables.cat_text),
        len(tables.svc_text),
        max(len(tables.ft_text), 2),
    )
    h_ratios = [max(n1, 6), max(n2, 4), max(n3, 4), max(n4, 3)]
    fig_h = min(36, 2.0 + 0.22 * sum(h_ratios))
    fig_w = _sales_fig_width(tables)
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(fig_w, fig_h),
        dpi=120,
        height_ratios=h_ratios,
    )
    fig.patch.set_facecolor(CLR_BG_PAGE)

    _paint_sales_table(axes[0], tables)
    _paint_category_table(axes[1], tables)
    _paint_service_table(axes[2], tables)
    _paint_footfall_table(axes[3], tables)

    plt.subplots_adjust(
        hspace=_COMPOSITE_HSPACE,
        left=0.04,
        right=0.96,
        top=0.98,
        bottom=0.02,
    )
    return _save_figure_png(fig)


def generate_report_image(
    report_data: Dict, location_name: str = "Boteco Bangalore"
) -> BytesIO:
    """Backward-compatible alias: sheet style without precomputed MTD breakdowns."""
    return generate_sheet_style_report_image(
        report_data,
        location_name,
        mtd_category={},
        mtd_service={},
        month_footfall_rows=[],
    )


def generate_simple_text_report(report_data: Dict) -> str:
    """Generate simple text report without emojis."""

    date_str = report_data.get("date", datetime.now().strftime("%d-%b-%Y"))

    lines = [
        "=" * 50,
        "BOTECO BANGALORE",
        "End of Day Report",
        f"Date: {date_str}",
        "=" * 50,
        "",
        "SALES SUMMARY",
        "-" * 30,
        f"Gross Total: {config.CURRENCY_FORMAT.format(report_data.get('gross_total', 0))}",
        f"Net Total: {config.CURRENCY_FORMAT.format(report_data.get('net_total', 0))}",
        f"Covers: {report_data.get('covers', 0)}",
        f"Turns: {report_data.get('turns', 0):.1f}",
        f"APC: {config.CURRENCY_FORMAT.format(report_data.get('apc', 0))}",
        "",
        "PAYMENT BREAKDOWN",
        "-" * 30,
        f"Cash: {config.CURRENCY_FORMAT.format(report_data.get('cash_sales', 0))}",
        f"GPay: {config.CURRENCY_FORMAT.format(report_data.get('gpay_sales', 0))}",
        f"Zomato: {config.CURRENCY_FORMAT.format(report_data.get('zomato_sales', 0))}",
        f"Card: {config.CURRENCY_FORMAT.format(report_data.get('card_sales', 0))}",
        "",
        "TARGET",
        "-" * 30,
        f"Target: {config.CURRENCY_FORMAT.format(report_data.get('target', 0))}",
        f"Achievement: {report_data.get('pct_target', 0):.1f}%",
        "",
        "MTD SUMMARY",
        "-" * 30,
        f"Total Covers: {report_data.get('mtd_total_covers', 0):,}",
        f"Net Sales: {config.CURRENCY_FORMAT.format(report_data.get('mtd_net_sales', 0))}",
        f"Avg Daily: {config.CURRENCY_FORMAT.format(report_data.get('mtd_avg_daily', 0))}",
        f"% of Target: {report_data.get('mtd_pct_target', 0):.1f}%",
        "=" * 50,
    ]

    return "\n".join(lines)


def generate_comparison_text(
    reports: List[Dict], location_name: str = "Boteco Bangalore"
) -> str:
    """Generate comparison report between multiple days."""

    if not reports:
        return "No data to compare"

    lines = [
        "=" * 50,
        f"{location_name.upper()}",
        "Daily Comparison Report",
        "=" * 50,
        "",
    ]

    for i, report in enumerate(reports, 1):
        date_str = report.get("date", "N/A")
        net = report.get("net_total", 0)

        if i > 1:
            prev = reports[i - 2]
            prev_net = prev.get("net_total", 0)
            diff = net - prev_net
            diff_pct = ((diff / prev_net) * 100) if prev_net > 0 else 0
            arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
            comparison = f" ({arrow} {diff_pct:+.1f}%)"
        else:
            comparison = ""

        lines.extend(
            [
                f"📅 {date_str}",
                f"   Net Sales: {config.CURRENCY_FORMAT.format(net)}{comparison}",
                f"   Covers: {report.get('covers', 0)} | APC: {config.CURRENCY_FORMAT.format(report.get('apc', 0))}",
                "",
            ]
        )

    return "\n".join(lines)
