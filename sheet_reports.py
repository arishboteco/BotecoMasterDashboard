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
    return f"{float(n or 0):.0f}%"


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
        pad_inches=0.02,
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


def _hbar(ax, x, y, w, h=0.009, color=C_BRAND):
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
    size=11.0,
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
    _hbar(ax, x, y + h - 0.009, w, color=accent_color)
    _label(ax, x + 0.012, y + h - 0.036, label, size=10.2, color=C_MUTED)
    _label(
        ax, x + 0.012, y + h - 0.087, value, size=18.75, color=C_SLATE, weight="bold"
    )
    if sub:
        _label(ax, x + 0.012, y + 0.027, sub, size=9.5, color=C_MUTED)


# ── Table row helpers ─────────────────────────────────────────────────────────


def _table_header_row(ax, x, y, cols, widths, row_h=0.048, bg=C_NAVY, font_size=None):
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
    n_cols = len(cols)
    fs = font_size if font_size else (10.2 if n_cols > 4 else 10.8)
    cx = x
    for i, (col, cw) in enumerate(zip(cols, widths)):
        ha = "left" if i == 0 else "right"
        px = cx + 0.012 if ha == "left" else cx + cw - 0.012
        _label(
            ax,
            px,
            y + row_h - 0.012,
            col,
            size=fs,
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
    row_h=0.042,
    bg=C_CARD,
    alt_bg=C_BAND,
    is_alt=False,
    bold=False,
    text_color=C_SLATE,
    right_color=None,
    font_size=None,
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
    n_cols = len(cells)
    fs = font_size if font_size else (10.8 if n_cols > 4 else 11.2)
    cx = x
    for i, (cell, cw) in enumerate(zip(cells, widths)):
        ha = "left" if i == 0 else "right"
        px = cx + 0.012 if ha == "left" else cx + cw - 0.012
        rc = right_color if (i > 0 and right_color) else text_color
        _label(
            ax,
            px,
            y + row_h - 0.0135,
            str(cell),
            size=fs,
            color=rc,
            weight="bold" if bold else "normal",
            ha=ha,
        )
        cx += cw


def _table_section_label(ax, x, y, text, w, row_h=0.039, color=C_BRAND):
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
    _hbar(ax, x, y, 0.006, row_h, color=color)
    _label(
        ax, x + 0.012, y + row_h - 0.0135, text, size=10.0, color=color, weight="bold"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Section builders
# ══════════════════════════════════════════════════════════════════════════════


def _section_sales_summary(
    ax, r: Dict, location_name: str, per_outlet: Optional[List[Tuple[str, Dict]]] = None
) -> None:
    """
    Compact sales summary table — Google Sheets style.
    Columns: Metric | (Outlet1 | Outlet2 | ...) Combined/Value
    """
    ax.set_xlim(0, 1)
    ax.axis("off")

    multi = per_outlet and len(per_outlet) >= 2
    n_outlets = len(per_outlet) if multi else 0
    col_w = _outlet_col_widths(n_outlets)

    iso = str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    pct_tgt = float(r.get("pct_target") or 0)
    ach_color = _achievement_color(pct_tgt)

    # ── Header banner (slim) ─────────────────────────────────────────────
    banner_h = 0.08
    banner_y = 0.93
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_NAVY, border=C_NAVY)
    _hbar(ax, 0, banner_y + banner_h, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_y + banner_h - 0.018,
        f"{location_name.upper()}  —  END OF DAY REPORT",
        size=11.5,
        color=C_WHITE,
        weight="bold",
    )
    _label(
        ax,
        0.012,
        banner_y + banner_h - 0.048,
        day_lbl,
        size=9.5,
        color="#94a3b8",
    )
    _label(
        ax,
        0.988,
        banner_y + banner_h - 0.018,
        f"{pct_tgt:.0f}% of target",
        size=11.0,
        color=ach_color,
        weight="bold",
        ha="right",
    )
    _label(
        ax,
        0.988,
        banner_y + banner_h - 0.048,
        _r(r.get("net_total", 0)) + " net",
        size=9.5,
        color=C_WHITE,
        ha="right",
    )

    # ── Column headers ───────────────────────────────────────────────────
    row_h = 0.038
    cur_y = banner_y - 0.01
    if multi:
        headers = (
            [""] + [_short_outlet_name(nm, 16) for nm, _ in per_outlet] + ["Combined"]
        )
    else:
        headers = ["", ""]
    _table_header_row(ax, 0, cur_y - row_h, headers, col_w, row_h)
    cur_y -= row_h

    # ── Helper to add a data row ─────────────────────────────────────────
    row_idx = [0]

    def _row(
        label,
        key_or_fn,
        fmt="currency",
        bold=False,
        bg=None,
        text_color=C_SLATE,
        right_color=None,
        section_label=None,
    ):
        nonlocal cur_y
        if section_label:
            _table_section_label(
                ax,
                0,
                cur_y - row_h * 0.85,
                section_label,
                sum(col_w),
                row_h=row_h * 0.85,
            )
            cur_y -= row_h * 0.85
            row_idx[0] = 0
            return
        # Gather values
        if callable(key_or_fn):
            combined_val = key_or_fn(r)
            outlet_vals = [key_or_fn(od) for _, od in per_outlet] if multi else []
        else:
            combined_val = r.get(key_or_fn, 0)
            outlet_vals = (
                [od.get(key_or_fn, 0) for _, od in per_outlet] if multi else []
            )

        def _fmt(v):
            if fmt == "currency":
                return _r(v)
            elif fmt == "int":
                return f"{int(v or 0):,}"
            elif fmt == "float1":
                return f"{float(v or 0):.0f}"
            elif fmt == "pct":
                return _pct(v)
            elif fmt == "str":
                return str(v or "—")
            return str(v)

        if multi:
            cells = [label] + [_fmt(v) for v in outlet_vals] + [_fmt(combined_val)]
        else:
            cells = [label, _fmt(combined_val)]

        cur_y -= row_h
        _table_data_row(
            ax,
            0,
            cur_y,
            cells,
            col_w,
            row_h=row_h,
            bg=bg or C_CARD,
            is_alt=(bg is None and row_idx[0] % 2 == 1),
            bold=bold,
            text_color=text_color,
            right_color=right_color,
        )
        row_idx[0] += 1

    # ── Daily sales rows ─────────────────────────────────────────────────
    _row("Covers", "covers", fmt="int")
    _row("Turns", "turns", fmt="float1")

    # Payment rows
    _row(None, None, section_label="Payment")
    pay_keys = [
        ("Cash", "cash_sales"),
        ("GPay", "gpay_sales"),
        ("Zomato", "zomato_sales"),
        ("Card", "card_sales"),
        ("Other / Wallet", "other_sales"),
    ]
    for lbl, key in pay_keys:
        combined_v = float(r.get(key) or 0)
        outlet_vs = [float(od.get(key) or 0) for _, od in per_outlet] if multi else []
        if combined_v != 0 or any(v != 0 for v in outlet_vs):
            _row(lbl, key)

    # EOD Gross Total
    _row("EOD Gross Total", "gross_total", bold=True, bg=C_BAND)

    # Tax & adjustments
    _row(None, None, section_label="Tax & Adjustments")
    tax_keys = [
        ("CGST @ 2.5%", "cgst"),
        ("SGST @ 2.5%", "sgst"),
        ("Service Charge", "service_charge"),
        ("Discount", "discount"),
        ("Complimentary", "complimentary"),
    ]
    for lbl, key in tax_keys:
        combined_v = float(r.get(key) or 0)
        outlet_vs = [float(od.get(key) or 0) for _, od in per_outlet] if multi else []
        if combined_v != 0 or any(v != 0 for v in outlet_vs):
            disc_color = C_RED if key == "discount" else None
            _row(lbl, key, right_color=disc_color)

    # EOD Net Total highlight
    _row(
        "EOD Net Total",
        "net_total",
        bold=True,
        bg=C_NAVY,
        text_color=C_WHITE,
        right_color=C_BRAND,
    )

    # ── MTD block ────────────────────────────────────────────────────────
    cur_y -= row_h * 0.3
    _table_header_row(
        ax, 0, cur_y - row_h, ["MTD Summary"] + [""] * (len(col_w) - 1), col_w, row_h
    )
    cur_y -= row_h
    row_idx[0] = 0

    _row("MTD Total Covers", "mtd_total_covers", fmt="int", bold=True)
    _row("APC (Day)", "apc", fmt="currency")

    def _apc_month(d):
        mtd_net = float(d.get("mtd_net_sales") or 0)
        mtd_cov = int(d.get("mtd_total_covers") or 0)
        return mtd_net / mtd_cov if mtd_cov > 0 else 0.0

    _row("APC (Month)", _apc_month, fmt="currency")

    _row("Complimentary", "complimentary", fmt="currency")
    _row("MTD Complimentary", "mtd_complimentary", fmt="currency")
    _row("Daily Avg. Net Sales", "mtd_avg_daily", fmt="currency")
    _row("MTD Net Sales", "mtd_net_sales", fmt="currency", bold=True)
    _row("MTD Discount", "mtd_discount", fmt="currency")

    def _mtd_net_excl(d):
        return float(d.get("mtd_net_sales") or 0) - float(d.get("mtd_discount") or 0)

    _row("MTD Net (Excl. Disc.)", _mtd_net_excl, fmt="currency", bold=True)

    _row("Sales Target", "mtd_target", fmt="currency")
    _row("% of Target", "mtd_pct_target", fmt="pct", bold=True, right_color=ach_color)

    ax.set_ylim(cur_y - 0.04, 1.0)


def _section_category(
    ax,
    r: Dict,
    location_name: str,
    mtd_category: Dict[str, float],
    day_lbl: str,
    per_outlet: Optional[List[Tuple[str, Dict]]] = None,
    per_outlet_category: Optional[List[Tuple[str, Dict[str, float]]]] = None,
) -> None:
    ax.set_xlim(0, 1)
    ax.axis("off")

    multi = per_outlet and len(per_outlet) >= 2
    std_cats = ["Food", "Liquor", "Beer", "Soft Beverages", "Coffee", "Tobacco"]

    daily_cat = {
        c.get("category"): float(c.get("amount") or 0)
        for c in r.get("categories") or []
    }
    mtd_category = dict(mtd_category or {})
    total_cat_mtd = sum(mtd_category.values()) or 1.0

    # Per-outlet daily category data
    outlet_daily_cats = []
    if multi and per_outlet:
        for _, od in per_outlet:
            od_cats = {
                c.get("category"): float(c.get("amount") or 0)
                for c in od.get("categories") or []
            }
            outlet_daily_cats.append(od_cats)

    cat_order = [x for x in std_cats if x in daily_cat or x in mtd_category]
    for k in sorted(mtd_category.keys()):
        if k not in cat_order:
            cat_order.append(k)
    if not cat_order:
        cat_order = []

    row_h = 0.052

    # Column widths: for multi-outlet add per-outlet daily columns
    if multi:
        n_data = len(per_outlet) + 1  # outlets + combined
        label_w = 0.22
        mtd_w = 0.14
        pct_w = 0.06
        remaining = 1.0 - label_w - mtd_w - pct_w
        data_w = remaining / n_data
        col_w = [label_w] + [data_w] * n_data + [mtd_w, pct_w]
    else:
        col_w = [0.50, 0.22, 0.22, 0.06]

    tbl_x = 0.0

    # Header banner (slim)
    banner_h = 0.065
    banner_top = 0.995
    banner_y = banner_top - banner_h
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_NAVY, border=C_NAVY)
    _hbar(ax, 0, banner_top, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - 0.018,
        f"Category Sales — {location_name[:28]}",
        size=11.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(ax, 0.012, banner_top - 0.045, day_lbl, size=9.0, color="#94a3b8")

    cur_y = banner_y - 0.01

    # Table header
    if multi:
        headers = (
            ["Category"]
            + [_short_outlet_name(nm, 12) for nm, _ in per_outlet]
            + ["Combined", "MTD", "%"]
        )
    else:
        headers = ["Category", "Daily", "MTD", "%"]
    _table_header_row(ax, tbl_x, cur_y - row_h, headers, col_w, row_h)
    cur_y -= row_h

    daily_total = 0.0
    mtd_total = 0.0
    outlet_totals = [0.0] * len(outlet_daily_cats) if multi else []

    for idx, name in enumerate(cat_order):
        d_amt = daily_cat.get(name, 0.0)
        m_amt = float(mtd_category.get(name, 0) or 0)
        daily_total += d_amt
        mtd_total += m_amt
        pct_lbl = (
            f"{int(round(100 * m_amt / total_cat_mtd))}%" if total_cat_mtd > 0 else "—"
        )

        if multi:
            outlet_amts = []
            for oi, od_cats in enumerate(outlet_daily_cats):
                ov = od_cats.get(name, 0.0)
                outlet_totals[oi] += ov
                outlet_amts.append(_r(ov))
            cells = [name] + outlet_amts + [_r(d_amt), _r(m_amt), pct_lbl]
        else:
            cells = [name, _r(d_amt), _r(m_amt), pct_lbl]

        cur_y -= row_h
        _table_data_row(
            ax,
            tbl_x,
            cur_y,
            cells,
            col_w,
            row_h=row_h,
            is_alt=(idx % 2 == 1),
        )

    # Totals row
    cur_y -= row_h
    if multi:
        tot_cells = (
            ["Total"]
            + [_r(t) for t in outlet_totals]
            + [_r(daily_total), _r(mtd_total), ""]
        )
    else:
        tot_cells = ["Total", _r(daily_total), _r(mtd_total), ""]
    _table_data_row(
        ax,
        tbl_x,
        cur_y,
        tot_cells,
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
    per_outlet: Optional[List[Tuple[str, Dict]]] = None,
    per_outlet_service: Optional[List[Tuple[str, Dict[str, float]]]] = None,
) -> None:
    ax.set_xlim(0, 1)
    ax.axis("off")

    multi = per_outlet and len(per_outlet) >= 2
    std_svc = ["Breakfast", "Lunch", "Dinner", "Delivery", "Events", "Party"]

    daily_svc = {
        s.get("service_type") or s.get("type"): float(s.get("amount") or 0)
        for s in r.get("services") or []
    }
    mtd_service = dict(mtd_service or {})
    total_svc_mtd = sum(mtd_service.values()) or 1.0

    # Per-outlet daily service data
    outlet_daily_svcs = []
    if multi and per_outlet:
        for _, od in per_outlet:
            od_svcs = {
                s.get("service_type") or s.get("type"): float(s.get("amount") or 0)
                for s in od.get("services") or []
            }
            outlet_daily_svcs.append(od_svcs)

    svc_order = [x for x in std_svc if x in daily_svc or x in mtd_service]
    for k in sorted(mtd_service.keys()):
        if k not in svc_order:
            svc_order.append(k)

    row_h = 0.052

    if multi:
        n_data = len(per_outlet) + 1
        label_w = 0.22
        mtd_w = 0.14
        pct_w = 0.06
        remaining = 1.0 - label_w - mtd_w - pct_w
        data_w = remaining / n_data
        col_w = [label_w] + [data_w] * n_data + [mtd_w, pct_w]
    else:
        col_w = [0.50, 0.22, 0.22, 0.06]
    tbl_x = 0.0

    # Slim header banner
    banner_h = 0.065
    banner_top = 0.995
    banner_y = banner_top - banner_h
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_NAVY, border=C_NAVY)
    _hbar(ax, 0, banner_top, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - 0.018,
        f"Service Sales — {location_name[:28]}",
        size=11.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(ax, 0.012, banner_top - 0.045, day_lbl, size=9.0, color="#94a3b8")

    cur_y = banner_y - 0.01

    if multi:
        headers = (
            ["Service"]
            + [_short_outlet_name(nm, 12) for nm, _ in per_outlet]
            + ["Combined", "MTD", "%"]
        )
    else:
        headers = ["Service", "Daily", "MTD", "%"]
    _table_header_row(ax, tbl_x, cur_y - row_h, headers, col_w, row_h)
    cur_y -= row_h

    if not svc_order:
        _label(
            ax,
            0.5,
            cur_y - 0.05,
            "No service data for this date",
            size=11.0,
            color=C_MUTED,
            ha="center",
        )
        ax.set_ylim(cur_y - 0.12, 1.0)
        return

    daily_total = 0.0
    mtd_total = 0.0
    outlet_totals = [0.0] * len(outlet_daily_svcs) if multi else []

    for idx, name in enumerate(svc_order):
        d_amt = daily_svc.get(name, 0.0)
        m_amt = float(mtd_service.get(name, 0) or 0)
        daily_total += d_amt
        mtd_total += m_amt
        pct_lbl = (
            f"{int(round(100 * m_amt / total_svc_mtd))}%" if total_svc_mtd > 0 else "—"
        )

        if multi:
            outlet_amts = []
            for oi, od_svcs in enumerate(outlet_daily_svcs):
                ov = od_svcs.get(name, 0.0)
                outlet_totals[oi] += ov
                outlet_amts.append(_r(ov))
            cells = [name] + outlet_amts + [_r(d_amt), _r(m_amt), pct_lbl]
        else:
            cells = [name, _r(d_amt), _r(m_amt), pct_lbl]

        cur_y -= row_h
        _table_data_row(
            ax,
            tbl_x,
            cur_y,
            cells,
            col_w,
            row_h=row_h,
            is_alt=(idx % 2 == 1),
        )

    # Totals row
    cur_y -= row_h
    if multi:
        tot_cells = (
            ["Total"]
            + [_r(t) for t in outlet_totals]
            + [_r(daily_total), _r(mtd_total), ""]
        )
    else:
        tot_cells = ["Total", _r(daily_total), _r(mtd_total), ""]
    _table_data_row(
        ax,
        tbl_x,
        cur_y,
        tot_cells,
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

    # Slim header banner (consistent with other sections)
    banner_h = 0.065
    banner_top = 0.995
    banner_y = banner_top - banner_h
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_NAVY, border=C_NAVY)
    _hbar(ax, 0, banner_top, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - 0.018,
        "Daily Footfall — Month to Date",
        size=11.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(ax, 0.012, banner_top - 0.045, location_name[:32], size=9.0, color="#94a3b8")

    if not rows:
        _label(
            ax,
            0.5,
            banner_y - 0.06,
            "No footfall data for this month",
            size=11.0,
            color=C_MUTED,
            ha="center",
        )
        ax.set_ylim(banner_y - 0.15, 1.0)
        return

    col_w = [0.44, 0.18, 0.18, 0.20]
    row_h = 0.045
    tbl_x = 0.0

    cur_y = banner_y - 0.01
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
                f"{avg_din:.0f}",
                f"{avg_lun:.0f}",
                f"{avg_cov:.0f}",
            ],
            col_w,
            row_h=row_h,
            bg=C_BAND,
            bold=False,
            text_color=C_MUTED,
        )

    ax.set_ylim(cur_y - 0.06, 1.0)


# ── Short outlet name helper ──────────────────────────────────────────────────


def _short_outlet_name(name: str, max_len: int = 18) -> str:
    name = (name or "").strip()
    for prefix in ("Boteco - ", "Boteco-", "Boteco "):
        if name.lower().startswith(prefix.lower()):
            name = name[len(prefix) :].strip()
            break
    return name if len(name) <= max_len else name[: max_len - 1] + "\u2026"


def _outlet_col_widths(n_outlets: int, label_frac: float = 0.30) -> List[float]:
    """Compute column widths for [Label, Outlet1, ..., OutletN, Combined].

    When n_outlets <= 1, returns [label_frac, 1 - label_frac] (two columns).
    When n_outlets >= 2, splits remaining space equally among outlets + combined.
    """
    if n_outlets <= 1:
        return [label_frac, 1.0 - label_frac]
    data_cols = n_outlets + 1  # per-outlet + combined
    data_w = (1.0 - label_frac) / data_cols
    return [label_frac] + [data_w] * data_cols


def _section_fig_width(n_outlets: int) -> float:
    """Figure width in inches. Wider when multi-outlet."""
    if n_outlets <= 1:
        return 8.5
    if n_outlets == 2:
        return 10.0
    return min(12.0, 10.0 + (n_outlets - 2) * 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════


def _fig_for_section(
    n_rows: int, min_rows: int = 4, cap_h: float = 20.0, w: float = 8.5
) -> Tuple[plt.Figure, plt.Axes]:
    h = min(cap_h, 2.8 + 0.48 * max(n_rows, min_rows))
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
    per_outlet_category: Optional[List[Tuple[str, Dict[str, float]]]] = None,
    per_outlet_service: Optional[List[Tuple[str, Dict[str, float]]]] = None,
) -> Dict[str, BytesIO]:
    """Four separate PNGs: sales_summary, category, service, footfall."""
    r = report_data
    mc = dict(mtd_category or {})
    ms = dict(mtd_service or {})
    mf = list(month_footfall_rows or [])
    iso = str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    per_outlet = list(per_outlet_summaries) if per_outlet_summaries else None
    per_outlet_cat = list(per_outlet_category) if per_outlet_category else None
    per_outlet_svc = list(per_outlet_service) if per_outlet_service else None

    out: Dict[str, BytesIO] = {}

    # Dynamic figure width for multi-outlet
    n_outlets = len(per_outlet) if per_outlet and len(per_outlet) >= 2 else 0
    fig_w = _section_fig_width(n_outlets)

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
    est_rows = 10 + n_pay + n_tax + 12  # MTD rows
    fig, ax = _fig_for_section(est_rows, min_rows=12, cap_h=36.0, w=fig_w)
    _section_sales_summary(ax, r, location_name, per_outlet)
    out["sales_summary"] = _save_fig(fig)

    # Category
    n_cat = len(mc) or 3
    fig, ax = _fig_for_section(n_cat + 4, min_rows=6, cap_h=21.0, w=fig_w)
    _section_category(
        ax,
        r,
        location_name,
        mc,
        day_lbl,
        per_outlet=per_outlet,
        per_outlet_category=per_outlet_cat,
    )
    out["category"] = _save_fig(fig)

    # Service
    n_svc = len(ms) or 3
    fig, ax = _fig_for_section(n_svc + 4, min_rows=5, cap_h=18.0, w=fig_w)
    _section_service(
        ax,
        r,
        location_name,
        ms,
        day_lbl,
        per_outlet=per_outlet,
        per_outlet_service=per_outlet_svc,
    )
    out["service"] = _save_fig(fig)

    # Footfall
    n_ft = len(mf) + 4
    fig, ax = _fig_for_section(n_ft, min_rows=5, cap_h=33.0, w=fig_w)
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
    per_outlet_category: Optional[List[Tuple[str, Dict[str, float]]]] = None,
    per_outlet_service: Optional[List[Tuple[str, Dict[str, float]]]] = None,
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
        per_outlet_category,
        per_outlet_service,
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

    services = r.get("services") or []
    svc_lines = "\n".join(
        f"  \u2022 {s.get('type') or s.get('service_type', '?')}: "
        f"{config.CURRENCY_FORMAT.format(s.get('amount', 0))}"
        for s in services
        if float(s.get("amount") or 0) > 0
    )

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
        f"  \u2022 Covers: {int(r.get('covers') or 0):,}  |  Turns: {float(r.get('turns') or 0):.0f}x\n"
        f"  \u2022 APC: {config.CURRENCY_FORMAT.format(r.get('apc', 0))}\n\n"
        f"\U0001f4b3 PAYMENT BREAKDOWN\n"
        f"{pay_lines}\n\n"
        f"\U0001f3af VS TARGET\n"
        f"  \u2022 Target: {config.CURRENCY_FORMAT.format(r.get('target', 0))}\n"
        f"  \u2022 Achievement: {pct_target:.0f}%\n"
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
        f"  \u2022 % of Target: {float(r.get('mtd_pct_target') or 0):.0f}%\n"
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
