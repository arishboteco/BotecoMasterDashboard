"""
Boteco EOD Report — PNG image generator and WhatsApp text formatter.

Design language:
  - Coral brand accent  (#e94560)
  - Dark navy header    (#0f172a)
  - Slate body text     (#1e293b)
  - Light slate muted   (#64748b)
  - Off-white page bg   (#f8fafc)
  - White card bg       (#ffffff)
  - Subtle border       (#e2e8f0)
  - Green positive      (#16a34a)
  - Amber warning       (#d97706)

The composite PNG is built with matplotlib drawing primitives
(patches + text), not tables, so every element can be positioned
and styled independently.
"""

import math
from io import BytesIO
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

import config

# ── Palette ──────────────────────────────────────────────────────────────────
C_PAGE = "#f8fafc"
C_CARD = "#ffffff"
C_BRAND = "#e94560"  # Boteco coral
C_BRAND_DARK = "#c73652"
C_NAVY = "#0f172a"
C_SLATE = "#1e293b"
C_MUTED = "#64748b"
C_BORDER = "#e2e8f0"
C_BAND = "#f1f5f9"
C_GREEN = "#16a34a"
C_AMBER = "#d97706"
C_RED = "#dc2626"
C_WHITE = "#ffffff"

FONT = "DejaVu Sans"
DPI = 150


# ── Helpers ───────────────────────────────────────────────────────────────────


def _r(n) -> str:
    """Format as ₹ with Indian comma grouping."""
    if n is None:
        n = 0.0
    n = float(n)
    if abs(n - round(n)) < 0.005:
        return f"\u20b9{int(round(n)):,}"
    return f"\u20b9{n:,.2f}"


def _pct(n) -> str:
    return f"{float(n or 0):.1f}%"


def _sheet_date_label(iso_date: str) -> str:
    try:
        dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
    except ValueError:
        return iso_date
    return f"{dt.strftime('%a')}, {dt.day} {dt.strftime('%b %Y')}"


def _achievement_color(pct: float) -> str:
    if pct >= 100:
        return C_GREEN
    if pct >= 80:
        return C_AMBER
    return C_RED


def _save_fig(fig) -> BytesIO:
    buf = BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=DPI,
        bbox_inches="tight",
        pad_inches=0.18,
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Drawing primitives ────────────────────────────────────────────────────────


def _card(ax, x, y, w, h, radius=0.012, color=C_CARD, border=C_BORDER, lw=0.8):
    """Draw a rounded-corner card."""
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=lw,
        edgecolor=border,
        facecolor=color,
        transform=ax.transData,
        clip_on=False,
        zorder=2,
    )
    ax.add_patch(patch)


def _hbar(ax, x, y, w, h=0.006, color=C_BRAND):
    """Draw a solid horizontal rule / accent bar."""
    patch = mpatches.Rectangle(
        (x, y),
        w,
        h,
        linewidth=0,
        facecolor=color,
        transform=ax.transData,
        clip_on=False,
        zorder=3,
    )
    ax.add_patch(patch)


def _label(
    ax,
    x,
    y,
    text,
    size=7.5,
    color=C_SLATE,
    weight="normal",
    ha="left",
    va="top",
    zorder=4,
):
    ax.text(
        x,
        y,
        text,
        fontsize=size,
        color=color,
        fontfamily=FONT,
        fontweight=weight,
        ha=ha,
        va=va,
        zorder=zorder,
        clip_on=False,
    )


def _divider(ax, x, y, w, color=C_BORDER, lw=0.5):
    ax.plot(
        [x, x + w],
        [y, y],
        color=color,
        linewidth=lw,
        transform=ax.transData,
        clip_on=False,
        zorder=3,
    )


# ── KPI tile ──────────────────────────────────────────────────────────────────


def _kpi_tile(ax, x, y, w, h, label, value, sub=None, accent_color=C_BRAND):
    """A single KPI card: accent top bar → label → big value → optional sub."""
    _card(ax, x, y, w, h)
    _hbar(ax, x, y + h - 0.006, w, color=accent_color)
    _label(ax, x + 0.012, y + h - 0.024, label, size=6.8, color=C_MUTED)
    _label(ax, x + 0.012, y + h - 0.058, value, size=12.5, color=C_SLATE, weight="bold")
    if sub:
        _label(ax, x + 0.012, y + 0.018, sub, size=6.5, color=C_MUTED)


# ── Table row helpers ─────────────────────────────────────────────────────────


def _table_header_row(ax, x, y, cols, widths, row_h=0.032, bg=C_NAVY):
    """Dark header row for a data table."""
    total_w = sum(widths)
    patch = mpatches.Rectangle(
        (x, y),
        total_w,
        row_h,
        linewidth=0,
        facecolor=bg,
        transform=ax.transData,
        clip_on=False,
        zorder=2,
    )
    ax.add_patch(patch)
    cx = x
    for i, (col, cw) in enumerate(zip(cols, widths)):
        ha = "left" if i == 0 else "right"
        px = cx + 0.008 if ha == "left" else cx + cw - 0.008
        _label(
            ax,
            px,
            y + row_h - 0.008,
            col,
            size=6.8,
            color=C_WHITE,
            weight="bold",
            ha=ha,
        )
        cx += cw


def _table_data_row(
    ax,
    x,
    y,
    cells,
    widths,
    row_h=0.028,
    bg=C_CARD,
    alt_bg=C_BAND,
    is_alt=False,
    bold=False,
    text_color=C_SLATE,
    right_color=None,
):
    """One data row — alternating band if is_alt."""
    total_w = sum(widths)
    fill = alt_bg if is_alt else bg
    patch = mpatches.Rectangle(
        (x, y),
        total_w,
        row_h,
        linewidth=0,
        facecolor=fill,
        transform=ax.transData,
        clip_on=False,
        zorder=2,
    )
    ax.add_patch(patch)
    cx = x
    for i, (cell, cw) in enumerate(zip(cells, widths)):
        ha = "left" if i == 0 else "right"
        px = cx + 0.008 if ha == "left" else cx + cw - 0.008
        rc = right_color if (i > 0 and right_color) else text_color
        _label(
            ax,
            px,
            y + row_h - 0.009,
            str(cell),
            size=7.2,
            color=rc,
            weight="bold" if bold else "normal",
            ha=ha,
        )
        cx += cw


def _table_section_label(ax, x, y, text, w, row_h=0.026, color=C_BRAND):
    """A full-width accent-coloured section label inside a table."""
    patch = mpatches.Rectangle(
        (x, y),
        w,
        row_h,
        linewidth=0,
        facecolor=color + "18",  # ~10% alpha via hex
        transform=ax.transData,
        clip_on=False,
        zorder=2,
    )
    ax.add_patch(patch)
    _hbar(ax, x, y, 0.004, row_h, color=color)
    _label(ax, x + 0.012, y + row_h - 0.009, text, size=6.8, color=color, weight="bold")


# ══════════════════════════════════════════════════════════════════════════════
# Section builders
# ══════════════════════════════════════════════════════════════════════════════


def _section_sales_summary(
    ax, r: Dict, location_name: str, per_outlet: Optional[List[Tuple[str, Dict]]] = None
) -> None:
    """
    Top section: header banner → 4 KPI tiles → payment + tax table → MTD block.
    """
    ax.set_xlim(0, 1)
    ax.axis("off")

    iso = str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    pct_tgt = float(r.get("pct_target") or 0)
    ach_color = _achievement_color(pct_tgt)

    # ── Header banner ────────────────────────────────────────────────────
    banner_h = 0.092
    banner_y = 0.91
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_NAVY, border=C_NAVY)
    _hbar(ax, 0, banner_y, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.016,
        banner_y + banner_h - 0.018,
        location_name.upper(),
        size=9.5,
        color=C_WHITE,
        weight="bold",
    )
    _label(
        ax,
        0.016,
        banner_y + banner_h - 0.048,
        "END OF DAY REPORT",
        size=7.0,
        color=C_BRAND,
    )
    _label(ax, 0.016, banner_y + banner_h - 0.072, day_lbl, size=7.2, color="#94a3b8")
    # Achievement pill on the right
    _label(
        ax,
        0.984,
        banner_y + banner_h - 0.030,
        f"{pct_tgt:.1f}% of target",
        size=8.5,
        color=ach_color,
        weight="bold",
        ha="right",
    )
    _label(
        ax,
        0.984,
        banner_y + banner_h - 0.058,
        _r(r.get("net_total", 0)) + " net",
        size=7.5,
        color=C_WHITE,
        ha="right",
    )

    # ── 4 KPI tiles ──────────────────────────────────────────────────────
    kpi_y = 0.78
    kpi_h = 0.10
    tile_gap = 0.010
    tile_w = (1.0 - 3 * tile_gap) / 4
    kpis = [
        (
            "Net Sales",
            _r(r.get("net_total", 0)),
            f"Gross {_r(r.get('gross_total', 0))}",
            C_BRAND,
        ),
        (
            "Covers",
            f"{int(r.get('covers') or 0):,}",
            f"Turns {float(r.get('turns') or 0):.1f}x",
            C_SLATE,
        ),
        ("APC", _r(r.get("apc", 0)), "per cover", C_SLATE),
        ("vs Target", _pct(pct_tgt), _r(r.get("target", 0)) + " target", ach_color),
    ]
    for i, (lbl, val, sub, accent) in enumerate(kpis):
        tx = i * (tile_w + tile_gap)
        _kpi_tile(ax, tx, kpi_y, tile_w, kpi_h, lbl, val, sub, accent_color=accent)

    # ── Per-outlet mini-row (multi-outlet only) ───────────────────────────
    table_top = kpi_y - 0.018
    if per_outlet and len(per_outlet) >= 2:
        row_h = 0.028
        _hbar(ax, 0, table_top - 0.002, 1.0, h=0.001, color=C_BORDER)
        ox = 0.0
        col_w_each = 1.0 / len(per_outlet)
        for nm, od in per_outlet:
            _label(
                ax,
                ox + 0.010,
                table_top - 0.004,
                _short_outlet_name(nm),
                size=6.5,
                color=C_MUTED,
                weight="bold",
            )
            _label(
                ax,
                ox + 0.010,
                table_top - 0.022,
                f"{_r(od.get('net_total', 0))}  ·  {int(od.get('covers') or 0):,} cvr",
                size=7.0,
                color=C_SLATE,
            )
            ox += col_w_each
        table_top -= row_h * 2.2

    # ── Payment + tax table ───────────────────────────────────────────────
    tbl_x = 0.0
    tbl_w = 1.0
    col_w = [0.55, 0.45]
    row_h = 0.028

    pay_rows = [
        ("Cash", r.get("cash_sales", 0)),
        ("GPay", r.get("gpay_sales", 0)),
        ("Zomato", r.get("zomato_sales", 0)),
        ("Card", r.get("card_sales", 0)),
        ("Other / Wallet", r.get("other_sales", 0)),
    ]
    pay_rows = [(lbl, v) for lbl, v in pay_rows if float(v or 0) != 0]

    tax_rows = [
        ("CGST @ 2.5%", r.get("cgst", 0)),
        ("SGST @ 2.5%", r.get("sgst", 0)),
        ("Service Charge", r.get("service_charge", 0)),
        ("Discount", r.get("discount", 0)),
        ("Complimentary", r.get("complimentary", 0)),
    ]
    tax_rows = [(lbl, v) for lbl, v in tax_rows if float(v or 0) != 0]

    cur_y = table_top
    _table_header_row(ax, tbl_x, cur_y - row_h, ["Payment", "Amount"], col_w, row_h)
    cur_y -= row_h

    for idx, (lbl, val) in enumerate(pay_rows):
        cur_y -= row_h
        _table_data_row(
            ax, tbl_x, cur_y, [lbl, _r(val)], col_w, row_h=row_h, is_alt=(idx % 2 == 1)
        )

    if tax_rows:
        cur_y -= row_h * 0.4
        _table_section_label(
            ax,
            tbl_x,
            cur_y - row_h * 0.85,
            "Tax & Adjustments",
            tbl_w,
            row_h=row_h * 0.85,
        )
        cur_y -= row_h * 0.85
        for idx, (lbl, val) in enumerate(tax_rows):
            cur_y -= row_h
            disc_color = C_RED if lbl == "Discount" else None
            _table_data_row(
                ax,
                tbl_x,
                cur_y,
                [lbl, _r(val)],
                col_w,
                row_h=row_h,
                is_alt=(idx % 2 == 1),
                right_color=disc_color,
            )

    # EOD Net Total highlight row
    cur_y -= row_h * 0.3
    net_y = cur_y - row_h * 1.1
    patch = mpatches.Rectangle(
        (tbl_x, net_y),
        tbl_w,
        row_h * 1.1,
        linewidth=0,
        facecolor=C_NAVY,
        transform=ax.transData,
        clip_on=False,
        zorder=2,
    )
    ax.add_patch(patch)
    _label(
        ax,
        tbl_x + 0.010,
        net_y + row_h * 1.1 - 0.012,
        "EOD Net Total",
        size=7.8,
        color=C_WHITE,
        weight="bold",
    )
    _label(
        ax,
        tbl_x + tbl_w - 0.010,
        net_y + row_h * 1.1 - 0.012,
        _r(r.get("net_total", 0)),
        size=7.8,
        color=C_BRAND,
        weight="bold",
        ha="right",
    )
    cur_y = net_y

    # ── MTD block ────────────────────────────────────────────────────────
    mtd_y = cur_y - 0.032
    mtd_cov = int(r.get("mtd_total_covers") or 0)
    mtd_net = float(r.get("mtd_net_sales") or 0)
    mtd_avg = float(r.get("mtd_avg_daily") or 0)
    mtd_tgt = float(r.get("mtd_target") or config.MONTHLY_TARGET)
    mtd_pct = float(r.get("mtd_pct_target") or 0)
    apc_day = float(r.get("apc") or 0)
    apc_mtd = (mtd_net / mtd_cov) if mtd_cov > 0 else 0.0
    mtd_ach_color = _achievement_color(mtd_pct)

    _table_header_row(ax, tbl_x, mtd_y - row_h, ["MTD Summary", ""], col_w, row_h)
    mtd_rows_data = [
        ("MTD Net Sales", _r(mtd_net)),
        ("MTD Total Covers", f"{mtd_cov:,}"),
        ("Avg Daily Sales", _r(mtd_avg)),
        ("APC (Day / Month)", f"{_r(apc_day)} / {_r(apc_mtd)}"),
        ("Sales Target (month)", _r(mtd_tgt)),
        ("MTD Achievement", _pct(mtd_pct)),
        ("MTD Discount", _r(r.get("mtd_discount", 0))),
    ]
    cur_y = mtd_y - row_h
    for idx, (lbl, val) in enumerate(mtd_rows_data):
        cur_y -= row_h
        rc = mtd_ach_color if lbl == "MTD Achievement" else None
        bold = lbl in ("MTD Net Sales", "MTD Achievement")
        _table_data_row(
            ax,
            tbl_x,
            cur_y,
            [lbl, val],
            col_w,
            row_h=row_h,
            is_alt=(idx % 2 == 1),
            bold=bold,
            right_color=rc,
        )

    ax.set_ylim(cur_y - 0.04, 1.0)


def _section_category(
    ax,
    r: Dict,
    location_name: str,
    mtd_category: Dict[str, float],
    day_lbl: str,
) -> None:
    ax.set_xlim(0, 1)
    ax.axis("off")

    std_cats = ["Food", "Liquor", "Beer", "Soft Beverages", "Coffee", "Tobacco"]
    daily_cat = {
        c.get("category"): float(c.get("amount") or 0)
        for c in r.get("categories") or []
    }
    mtd_category = dict(mtd_category or {})
    total_cat_mtd = sum(mtd_category.values()) or 1.0

    cat_order = [x for x in std_cats if x in daily_cat or x in mtd_category]
    for k in sorted(mtd_category.keys()):
        if k not in cat_order:
            cat_order.append(k)
    if not cat_order:
        cat_order = []

    row_h = 0.038
    col_w = [0.50, 0.22, 0.22, 0.06]
    tbl_x = 0.0
    tbl_w = 1.0

    # Header
    _card(ax, 0, 0.92, 1.0, 0.07, color=C_NAVY, border=C_NAVY)
    _hbar(ax, 0, 0.985, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        0.974,
        f"Category Sales — {location_name[:28]}",
        size=8.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(ax, 0.012, 0.946, day_lbl, size=6.8, color="#94a3b8")

    cur_y = 0.90
    _table_header_row(
        ax, tbl_x, cur_y - row_h, ["Category", "Daily", "MTD", "%"], col_w, row_h
    )
    cur_y -= row_h

    daily_total = 0.0
    mtd_total = 0.0
    for idx, name in enumerate(cat_order):
        d_amt = daily_cat.get(name, 0.0)
        m_amt = float(mtd_category.get(name, 0) or 0)
        daily_total += d_amt
        mtd_total += m_amt
        pct_lbl = (
            f"{int(round(100 * m_amt / total_cat_mtd))}%" if total_cat_mtd > 0 else "—"
        )
        cur_y -= row_h
        _table_data_row(
            ax,
            tbl_x,
            cur_y,
            [name, _r(d_amt), _r(m_amt), pct_lbl],
            col_w,
            row_h=row_h,
            is_alt=(idx % 2 == 1),
        )

    # Totals row
    cur_y -= row_h
    _table_data_row(
        ax,
        tbl_x,
        cur_y,
        ["Total", _r(daily_total), _r(mtd_total), ""],
        col_w,
        row_h=row_h,
        bg=C_NAVY,
        bold=True,
        text_color=C_WHITE,
    )

    ax.set_ylim(cur_y - 0.04, 1.0)


def _section_service(
    ax,
    r: Dict,
    location_name: str,
    mtd_service: Dict[str, float],
    day_lbl: str,
) -> None:
    ax.set_xlim(0, 1)
    ax.axis("off")

    std_svc = ["Breakfast", "Lunch", "Dinner", "Delivery", "Events", "Party"]
    daily_svc = {
        s.get("service_type") or s.get("type"): float(s.get("amount") or 0)
        for s in r.get("services") or []
    }
    mtd_service = dict(mtd_service or {})
    total_svc_mtd = sum(mtd_service.values()) or 1.0

    svc_order = [x for x in std_svc if x in daily_svc or x in mtd_service]
    for k in sorted(mtd_service.keys()):
        if k not in svc_order:
            svc_order.append(k)

    row_h = 0.040
    col_w = [0.50, 0.22, 0.22, 0.06]
    tbl_x = 0.0

    _card(ax, 0, 0.92, 1.0, 0.07, color=C_NAVY, border=C_NAVY)
    _hbar(ax, 0, 0.985, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        0.974,
        f"Service Sales — {location_name[:28]}",
        size=8.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(ax, 0.012, 0.946, day_lbl, size=6.8, color="#94a3b8")

    cur_y = 0.90
    _table_header_row(
        ax, tbl_x, cur_y - row_h, ["Service", "Daily", "MTD", "%"], col_w, row_h
    )
    cur_y -= row_h

    daily_total = 0.0
    mtd_total = 0.0
    for idx, name in enumerate(svc_order):
        d_amt = daily_svc.get(name, 0.0)
        m_amt = float(mtd_service.get(name, 0) or 0)
        daily_total += d_amt
        mtd_total += m_amt
        pct_lbl = (
            f"{int(round(100 * m_amt / total_svc_mtd))}%" if total_svc_mtd > 0 else "—"
        )
        cur_y -= row_h
        _table_data_row(
            ax,
            tbl_x,
            cur_y,
            [name, _r(d_amt), _r(m_amt), pct_lbl],
            col_w,
            row_h=row_h,
            is_alt=(idx % 2 == 1),
        )

    if not svc_order:
        _label(
            ax,
            0.5,
            0.82,
            "No service data for this date",
            size=8.0,
            color=C_MUTED,
            ha="center",
        )
        ax.set_ylim(0.76, 1.0)
        return

    cur_y -= row_h
    _table_data_row(
        ax,
        tbl_x,
        cur_y,
        ["Total", _r(daily_total), _r(mtd_total), ""],
        col_w,
        row_h=row_h,
        bg=C_NAVY,
        bold=True,
        text_color=C_WHITE,
    )
    ax.set_ylim(cur_y - 0.04, 1.0)


def _section_footfall(ax, month_footfall_rows: List[Dict], location_name: str) -> None:
    ax.set_xlim(0, 1)
    ax.axis("off")

    rows = list(month_footfall_rows or [])

    _card(ax, 0, 0.92, 1.0, 0.07, color=C_NAVY, border=C_NAVY)
    _hbar(ax, 0, 0.985, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        0.974,
        "Daily Footfall — Month to Date",
        size=8.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(ax, 0.012, 0.946, location_name[:32], size=6.8, color="#94a3b8")

    if not rows:
        _label(
            ax,
            0.5,
            0.82,
            "No footfall data for this month",
            size=8.5,
            color=C_MUTED,
            ha="center",
        )
        ax.set_ylim(0.74, 1.0)
        return

    col_w = [0.44, 0.18, 0.18, 0.20]
    row_h = 0.032
    tbl_x = 0.0

    cur_y = 0.90
    _table_header_row(
        ax, tbl_x, cur_y - row_h, ["Date", "Dinner", "Lunch", "Total"], col_w, row_h
    )
    cur_y -= row_h

    tot_din = tot_lun = tot_cov = 0
    for idx, row in enumerate(rows):
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
        tot_din += di
        tot_lun += lu
        tot_cov += tot
        cur_y -= row_h
        _table_data_row(
            ax,
            tbl_x,
            cur_y,
            [
                _sheet_date_label(ds),
                str(di) if di else "—",
                str(lu) if lu else "—",
                str(tot),
            ],
            col_w,
            row_h=row_h,
            is_alt=(idx % 2 == 1),
        )

    # Totals row
    cur_y -= row_h
    _table_data_row(
        ax,
        tbl_x,
        cur_y,
        ["TOTAL", str(tot_din), str(tot_lun), str(tot_cov)],
        col_w,
        row_h=row_h,
        bg=C_NAVY,
        bold=True,
        text_color=C_WHITE,
    )
    # Average row
    n = len(rows)
    if n > 0:
        cur_y -= row_h
        avg_din = tot_din / n
        avg_lun = tot_lun / n
        avg_cov = tot_cov / n
        _table_data_row(
            ax,
            tbl_x,
            cur_y,
            [
                f"Avg / day ({n} days)",
                f"{avg_din:.1f}",
                f"{avg_lun:.1f}",
                f"{avg_cov:.1f}",
            ],
            col_w,
            row_h=row_h,
            bg=C_BAND,
            bold=False,
            text_color=C_MUTED,
        )

    ax.set_ylim(cur_y - 0.04, 1.0)


# ── Short outlet name helper ──────────────────────────────────────────────────


def _short_outlet_name(name: str, max_len: int = 18) -> str:
    name = (name or "").strip()
    return name if len(name) <= max_len else name[: max_len - 1] + "\u2026"


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════


def _fig_for_section(
    n_rows: int, min_rows: int = 4, cap_h: float = 20.0, w: float = 8.5
) -> Tuple[plt.Figure, plt.Axes]:
    h = min(cap_h, 2.2 + 0.32 * max(n_rows, min_rows))
    fig, ax = plt.subplots(figsize=(w, h), dpi=DPI)
    fig.patch.set_facecolor(C_PAGE)
    ax.set_facecolor(C_PAGE)
    return fig, ax


def generate_sheet_style_report_sections(
    report_data: Dict,
    location_name: str = "Boteco Bangalore",
    mtd_category: Optional[Dict[str, float]] = None,
    mtd_service: Optional[Dict[str, float]] = None,
    month_footfall_rows: Optional[List[Dict]] = None,
    per_outlet_summaries: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
) -> Dict[str, BytesIO]:
    """Four separate PNGs: sales_summary, category, service, footfall."""
    r = report_data
    mc = dict(mtd_category or {})
    ms = dict(mtd_service or {})
    mf = list(month_footfall_rows or [])
    iso = str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    per_outlet = list(per_outlet_summaries) if per_outlet_summaries else None

    out: Dict[str, BytesIO] = {}

    # Sales summary
    n_pay = len(
        [
            1
            for k in (
                "cash_sales",
                "gpay_sales",
                "zomato_sales",
                "card_sales",
                "other_sales",
            )
            if float(r.get(k) or 0) != 0
        ]
    )
    n_tax = len(
        [
            1
            for k in ("cgst", "sgst", "service_charge", "discount", "complimentary")
            if float(r.get(k) or 0) != 0
        ]
    )
    est_rows = 10 + n_pay + n_tax + (2 if per_outlet else 0)
    fig, ax = _fig_for_section(est_rows, min_rows=12, cap_h=24.0, w=8.5)
    _section_sales_summary(ax, r, location_name, per_outlet)
    out["sales_summary"] = _save_fig(fig)

    # Category
    n_cat = len(mc) or 3
    fig, ax = _fig_for_section(n_cat + 4, min_rows=6, cap_h=14.0, w=8.5)
    _section_category(ax, r, location_name, mc, day_lbl)
    out["category"] = _save_fig(fig)

    # Service
    n_svc = len(ms) or 3
    fig, ax = _fig_for_section(n_svc + 4, min_rows=5, cap_h=12.0, w=8.5)
    _section_service(ax, r, location_name, ms, day_lbl)
    out["service"] = _save_fig(fig)

    # Footfall
    n_ft = len(mf) + 4
    fig, ax = _fig_for_section(n_ft, min_rows=5, cap_h=22.0, w=8.5)
    _section_footfall(ax, mf, location_name)
    out["footfall"] = _save_fig(fig)

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
    Composite PNG: 4 sections stacked vertically.
    Sales Summary → Category Sales → Service Sales → Footfall Grid.
    """
    sections = generate_sheet_style_report_sections(
        report_data,
        location_name,
        mtd_category,
        mtd_service,
        month_footfall_rows,
        per_outlet_summaries,
    )

    # Stack the 4 PNGs into one tall image using matplotlib
    from PIL import Image as PILImage
    import numpy as np

    imgs = []
    for key in ("sales_summary", "category", "service", "footfall"):
        buf = sections[key]
        buf.seek(0)
        imgs.append(PILImage.open(buf).convert("RGB"))

    total_h = sum(im.height for im in imgs)
    max_w = max(im.width for im in imgs)
    composite = PILImage.new("RGB", (max_w, total_h), color=(248, 250, 252))
    y_off = 0
    for im in imgs:
        # centre narrower images
        x_off = (max_w - im.width) // 2
        composite.paste(im, (x_off, y_off))
        y_off += im.height

    buf = BytesIO()
    composite.save(buf, format="PNG", optimize=False)
    buf.seek(0)
    return buf


def generate_report_image(
    report_data: Dict, location_name: str = "Boteco Bangalore"
) -> BytesIO:
    """Backward-compatible alias."""
    return generate_sheet_style_report_image(
        report_data,
        location_name,
        mtd_category={},
        mtd_service={},
        month_footfall_rows=[],
    )


# ── WhatsApp text ─────────────────────────────────────────────────────────────


def generate_whatsapp_text(
    report_data: Dict,
    location_name: str = "Boteco Bangalore",
    per_outlet: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
) -> str:
    r = report_data
    date_str = r.get("date", datetime.now().strftime("%d-%b-%Y"))
    net_total = float(r.get("net_total") or 0)
    pct_target = float(r.get("pct_target") or 0)

    def _pct_of(val):
        return f"{val / net_total * 100:.0f}%" if net_total > 0 else "—"

    if pct_target >= 100:
        status_emoji, status_text = "\u2705", "Target Achieved!"
    elif pct_target >= 80:
        status_emoji, status_text = "\u26a0\ufe0f", "Almost There"
    else:
        status_emoji, status_text = "\U0001f534", "Below Target"

    # Category lines
    categories = r.get("categories") or []
    cat_total = sum(c.get("amount", 0) for c in categories) or 1
    cat_lines = (
        "\n".join(
            f"  \u2022 {c.get('category', '?')}: "
            f"{int(c.get('amount', 0) / cat_total * 100)}% "
            f"({config.CURRENCY_FORMAT.format(c.get('amount', 0))})"
            for c in categories
        )
        or "  \u2022 Data not available"
    )

    # Service lines
    services = r.get("services") or []
    svc_lines = "\n".join(
        f"  \u2022 {s.get('type') or s.get('service_type', '?')}: "
        f"{config.CURRENCY_FORMAT.format(s.get('amount', 0))}"
        for s in services
        if float(s.get("amount") or 0) > 0
    )

    # Payment lines — now includes Other
    pay_items = [
        ("Cash", r.get("cash_sales", 0)),
        ("GPay", r.get("gpay_sales", 0)),
        ("Zomato", r.get("zomato_sales", 0)),
        ("Card", r.get("card_sales", 0)),
        ("Other", r.get("other_sales", 0)),
    ]
    pay_lines = "\n".join(
        f"  \u2022 {lbl}: {config.CURRENCY_FORMAT.format(float(v or 0))} ({_pct_of(float(v or 0))})"
        for lbl, v in pay_items
        if float(v or 0) > 0
    )

    report = (
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f942 {location_name.upper()}\n"
        f"\U0001f4c5 End of Day Report  |  {date_str}\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        f"\U0001f4b0 SALES SUMMARY\n"
        f"  \u2022 Gross: {config.CURRENCY_FORMAT.format(r.get('gross_total', 0))}\n"
        f"  \u2022 Net:   {config.CURRENCY_FORMAT.format(net_total)}\n"
        f"  \u2022 Covers: {int(r.get('covers') or 0):,}  |  Turns: {float(r.get('turns') or 0):.1f}x\n"
        f"  \u2022 APC: {config.CURRENCY_FORMAT.format(r.get('apc', 0))}\n\n"
        f"\U0001f4b3 PAYMENT BREAKDOWN\n"
        f"{pay_lines}\n\n"
        f"\U0001f3af VS TARGET\n"
        f"  \u2022 Target: {config.CURRENCY_FORMAT.format(r.get('target', 0))}\n"
        f"  \u2022 Achievement: {pct_target:.1f}%\n"
        f"  {status_emoji} {status_text}\n\n"
        f"\U0001f37d\ufe0f CATEGORY MIX\n"
        f"{cat_lines}\n"
    )

    if svc_lines:
        report += f"\n\u23f0 SERVICE SPLIT\n{svc_lines}\n"

    report += (
        f"\n\U0001f465 MTD SUMMARY\n"
        f"  \u2022 Total Covers: {int(r.get('mtd_total_covers') or 0):,}\n"
        f"  \u2022 Net Sales: {config.CURRENCY_FORMAT.format(r.get('mtd_net_sales', 0))}\n"
        f"  \u2022 Avg Daily: {config.CURRENCY_FORMAT.format(r.get('mtd_avg_daily', 0))}\n"
        f"  \u2022 % of Target: {float(r.get('mtd_pct_target') or 0):.1f}%\n"
    )

    if per_outlet and len(per_outlet) >= 2:
        po_lines = "\n".join(
            f"  \u2022 {nm}: Net {config.CURRENCY_FORMAT.format(d.get('net_total', 0))} "
            f"| Covers {int(d.get('covers') or 0):,}"
            for nm, d in per_outlet
        )
        report += f"\n\U0001f3ea PER OUTLET\n{po_lines}\n"

    report += "\u2501" * 22
    return report.strip()


# ── Dead code kept for backward compatibility (not called by app.py) ──────────


def generate_simple_text_report(report_data: Dict) -> str:
    """Plain-text report without emojis (legacy, unused)."""
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
        f"Gross: {config.CURRENCY_FORMAT.format(report_data.get('gross_total', 0))}",
        f"Net:   {config.CURRENCY_FORMAT.format(report_data.get('net_total', 0))}",
        f"Covers: {report_data.get('covers', 0)}",
        f"Turns:  {report_data.get('turns', 0):.1f}",
        f"APC:    {config.CURRENCY_FORMAT.format(report_data.get('apc', 0))}",
        "",
        "TARGET",
        "-" * 30,
        f"Target: {config.CURRENCY_FORMAT.format(report_data.get('target', 0))}",
        f"Achievement: {report_data.get('pct_target', 0):.1f}%",
        "",
        "MTD",
        "-" * 30,
        f"Covers:  {report_data.get('mtd_total_covers', 0):,}",
        f"Sales:   {config.CURRENCY_FORMAT.format(report_data.get('mtd_net_sales', 0))}",
        f"Avg/day: {config.CURRENCY_FORMAT.format(report_data.get('mtd_avg_daily', 0))}",
        f"Target:  {report_data.get('mtd_pct_target', 0):.1f}%",
        "=" * 50,
    ]
    return "\n".join(lines)


def generate_comparison_text(
    reports: List[Dict], location_name: str = "Boteco Bangalore"
) -> str:
    """Day-over-day comparison text (legacy, unused)."""
    if not reports:
        return "No data to compare"
    lines = ["=" * 50, location_name.upper(), "Daily Comparison", "=" * 50, ""]
    for i, report in enumerate(reports, 1):
        net = report.get("net_total", 0)
        comparison = ""
        if i > 1:
            prev_net = reports[i - 2].get("net_total", 0)
            diff = net - prev_net
            diff_pct = (diff / prev_net * 100) if prev_net > 0 else 0
            arrow = "\u2191" if diff > 0 else "\u2193" if diff < 0 else "\u2192"
            comparison = f" ({arrow} {diff_pct:+.1f}%)"
        lines += [
            f"\U0001f4c5 {report.get('date', 'N/A')}",
            f"   Net: {config.CURRENCY_FORMAT.format(net)}{comparison}",
            f"   Covers: {report.get('covers', 0)} | APC: {config.CURRENCY_FORMAT.format(report.get('apc', 0))}",
            "",
        ]
    return "\n".join(lines)
