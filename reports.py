import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import config

# Google-Sheet-inspired EOD palette (approximate)
CLR_HEADER = "#001f3f"
CLR_TEAL = "#004d4d"
CLR_TEAL_LT = "#5f9ea0"
CLR_TAN = "#c5a059"
CLR_PINK = "#f4cccc"
CLR_WHITE = "#ffffff"
CLR_TEXT = "#1a1a1a"
CLR_RED_HI = "#e74c3c"

MONO = "DejaVu Sans Mono"


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


def _style_table(tbl, fontsize: float = 7.5) -> None:
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    for cell in tbl.get_celld().values():
        cell.set_text_props(fontfamily=MONO)
    tbl.scale(1, 1.65)


def generate_whatsapp_text(
    report_data: Dict, location_name: str = "Boteco Bangalore"
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
━━━━━━━━━━━━━━━━━━━━━━"""

    return report.strip()


def _cell_kind_bg(kind: str) -> str:
    if kind == "hdr":
        return CLR_HEADER
    if kind == "teal":
        return CLR_TEAL_LT
    if kind == "tan":
        return CLR_TAN
    if kind == "pink":
        return CLR_PINK
    if kind == "dk":
        return CLR_HEADER
    return CLR_WHITE


def _fg_for_bg(bg: str) -> str:
    if bg == CLR_HEADER:
        return CLR_WHITE
    if bg in (CLR_TAN, CLR_PINK, CLR_WHITE, CLR_TEAL_LT):
        return CLR_TEXT
    return CLR_TEXT


def generate_sheet_style_report_image(
    report_data: Dict,
    location_name: str = "Boteco Bangalore",
    mtd_category: Optional[Dict[str, float]] = None,
    mtd_service: Optional[Dict[str, float]] = None,
    month_footfall_rows: Optional[List[Dict]] = None,
) -> BytesIO:
    """
    Composite PNG styled like the Google Sheet EOD dashboard: Sales Summary,
    Category Sales, Service Sales, and optional footfall grid for the month.
    """
    mtd_category = dict(mtd_category or {})
    mtd_service = dict(mtd_service or {})
    month_footfall_rows = list(month_footfall_rows or [])

    iso = str(report_data.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    r = report_data

    def zpay(label: str, val: float, red_lbl: bool = False) -> Tuple[str, str, str, str]:
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
    sales_text.append(["Food vs Bar", "—"])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(["Covers", f"{int(r.get('covers') or 0):,}"])
    sales_kinds.append(("teal", "teal"))
    sales_text.append(["Turns", f"{float(r.get('turns') or 0):.1f}"])
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
        row = zpay(label, float(val or 0))
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
    sales_text.append(["Percentage of Target (MTD)", _pct(float(r.get("mtd_pct_target") or 0))])
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
    daily_cat = {c.get("category"): float(c.get("amount") or 0) for c in r.get("categories") or []}
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
        row_kind = ("pink", "pink", "pink") if d_amt == 0 and m_amt == 0 else ("white", "white", "white")
        cat_text.append([label, _rupee(d_amt), _rupee(m_amt)])
        cat_rows_kinds.append(row_kind)
    cat_text.append(["Total", _rupee(daily_cat_total), _rupee(mtd_cat_total)])
    cat_rows_kinds.append(("hdr", "hdr", "hdr"))

    std_svc = ["Breakfast", "Lunch", "Dinner", "Delivery", "Events", "Party"]
    daily_svc = {s.get("service_type") or s.get("type"): float(s.get("amount") or 0) for s in r.get("services") or []}
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
        row_kind = ("pink", "pink", "pink") if d_amt == 0 and m_amt == 0 else ("white", "white", "white")
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

    n1, n2, n3, n4 = len(sales_text), len(cat_text), len(svc_text), max(len(ft_text), 2)
    h_ratios = [max(n1, 6), max(n2, 4), max(n3, 4), max(n4, 3)]
    fig_h = min(36, 2.0 + 0.22 * sum(h_ratios))
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(10, fig_h),
        dpi=120,
        height_ratios=h_ratios,
    )
    fig.patch.set_facecolor("#ececec")

    for ax in axes:
        ax.axis("off")

    # Sales table
    t1 = axes[0].table(
        cellText=sales_text,
        loc="upper center",
        cellLoc="right",
        colWidths=[0.52, 0.38],
    )
    _style_table(t1, 7)
    for i in range(len(sales_text)):
        for j in range(2):
            c = t1[(i, j)]
            kk = sales_kinds[i] if i < len(sales_kinds) else ("white", "white")
            bg = _cell_kind_bg(kk[j])
            c.set_facecolor(bg)
            fg = _fg_for_bg(bg)
            c.set_text_props(color=fg, fontfamily=MONO)
            c.get_text().set_ha("right" if j == 1 else "left")
            c.set_edgecolor("#333333")
    t1[(0, 0)].get_text().set_ha("left")
    t1[(0, 1)].get_text().set_ha("right")

    # Category table
    t2 = axes[1].table(
        cellText=cat_text,
        loc="upper center",
        cellLoc="right",
        colWidths=[0.5, 0.22, 0.22],
    )
    _style_table(t2, 7)
    for i in range(len(cat_text)):
        for j in range(3):
            c = t2[(i, j)]
            kk = cat_rows_kinds[i][j]
            bg = _cell_kind_bg(kk)
            c.set_facecolor(bg)
            fg = _fg_for_bg(bg)
            c.set_text_props(color=fg, fontfamily=MONO)
            c.get_text().set_ha("right" if j else "left")
            c.set_edgecolor("#333333")

    # Service table
    t3 = axes[2].table(
        cellText=svc_text,
        loc="upper center",
        cellLoc="right",
        colWidths=[0.5, 0.22, 0.22],
    )
    _style_table(t3, 7)
    for i in range(len(svc_text)):
        for j in range(3):
            c = t3[(i, j)]
            kk = svc_rows_kinds[i][j]
            bg = _cell_kind_bg(kk)
            c.set_facecolor(bg)
            fg = _fg_for_bg(bg)
            c.set_text_props(color=fg, fontfamily=MONO)
            c.get_text().set_ha("right" if j else "left")
            c.set_edgecolor("#333333")

    # Footfall
    if len(ft_text) <= 1:
        axes[3].text(0.5, 0.5, "No footfall rows for month", ha="center", va="center", fontsize=9)
    else:
        t4 = axes[3].table(
            cellText=ft_text,
            loc="upper center",
            cellLoc="right",
            colWidths=[0.42, 0.18, 0.18, 0.18],
        )
        _style_table(t4, 7)
        for i in range(len(ft_text)):
            for j in range(4):
                c = t4[(i, j)]
                kk = ft_kinds[i][j] if i < len(ft_kinds) else "white"
                bg = _cell_kind_bg(kk)
                c.set_facecolor(bg)
                fg = _fg_for_bg(bg)
                c.set_text_props(color=fg, fontfamily=MONO)
                c.get_text().set_ha("right" if j else "left")
                c.set_edgecolor("#333333")

    plt.subplots_adjust(hspace=0.25, left=0.04, right=0.96, top=0.98, bottom=0.02)
    buf = BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    buf.seek(0)
    return buf


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
