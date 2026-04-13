"""
Boteco EOD Report — PNG image generator and WhatsApp text formatter.

Design language (Boteco Mango):
  - Brand blue           (#1F5FA8)
  - Brand dark           (#174A82)
  - Banner dark          (#1A3A5C)
  - Table header         (#EEF2F7)
  - Body text            (#1E293B)
  - Muted text           (#94A3B8)
  - Page bg              (#F7FAFC)
  - Card bg              (#FFFFFF)
  - Border               (#E2E8F0)
  - Leaf green           (#2E7D32)
  - Golden mustard       (#946B00)
  - Red error            (#DC2626)

The composite PNG is built with matplotlib drawing primitives
(patches + text), not tables, so every element can be positioned
and styled independently.
"""

import math
import re
from io import BytesIO
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

import config

# -- Palette (Boteco Mango) ---------------------------------------------------
C_PAGE = "#F7FAFC"  # Main background — soft off-white
C_CARD = "#FFFFFF"  # Card background — white
C_BRAND = "#1F5FA8"  # Deep Royal Blue — primary actions, accent bars
C_BRAND_DARK = "#174A82"  # Dark blue — hover/pressed
C_BANNER = "#1A3A5C"  # Dark navy blue — section banners & totals rows
C_HEADER = "#EEF2F7"  # Light grey — table header row backgrounds
C_SLATE = "#1E293B"  # Slate 800 (body text)
C_DATE_LABEL = "#8BA3BD"  # Muted blue-grey — date/location labels in banners
C_MUTED = "#64748B"  # Slate 500 (muted text — WCAG AA compliant)
C_BORDER = "#E2E8F0"  # Slate 200 (card borders)
C_BAND = "#F7FAFC"  # Soft off-white (alternating rows, matches page)
C_GREEN = "#2E7D32"  # Leaf green — positive/achievement (WCAG AA)
C_AMBER = "#946B00"  # Golden mustard — warning (WCAG AA)
C_RED = "#DC2626"  # Red — negative/discount (WCAG AA)
C_WHITE = "#FFFFFF"  # White

FONT = "DejaVu Sans"
DPI = 150

# Fixed pixel targets for consistent row spacing across all sections
# Proportional to font sizes: 11pt text at 150 DPI = 23px
# Row = font + 17px padding (8 top, 9 bottom), Banner = two text lines + 12px padding
ROW_PX = 40  # 11pt font (23px) + 17px padding
BANNER_PX = 56  # title(24px) + date(20px) + 12px padding
SECTION_GAP_PX = 6  # pixels between banner and table
BOTTOM_PAD_PX = 24  # pixels below last row


# ── Helpers ───────────────────────────────────────────────────────────────────


def _r(n) -> str:
    """Format as ₹ with Indian comma grouping."""
    if n is None:
        n = 0.0
    return f"\u20b9{int(round(float(n))):,}"


def _pct(n) -> str:
    return f"{float(n or 0):.0f}%"


def _sheet_date_label(iso_date: str) -> str:
    try:
        dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
    except ValueError:
        return iso_date
    return f"{dt.strftime('%a')}, {dt.day} {dt.strftime('%b %Y')}"


def _to_super_category(name: str) -> str:
    k = str(name or "").strip().lower()
    if not k:
        return "Other"
    if "beer" in k:
        return "Beer"
    if any(
        x in k
        for x in (
            "liquor",
            "spirit",
            "wine",
            "cocktail",
            "whisky",
            "vodka",
            "gin",
            "rum",
        )
    ):
        return "Liquor"
    if any(x in k for x in ("tobacco", "hookah", "cigar")):
        return "Tobacco"
    if any(
        x in k
        for x in ("coffee", "hot beverage", "hot beverages", "espresso", "cappuccino")
    ):
        return "Coffee"
    if any(
        x in k
        for x in (
            "soft",
            "beverage",
            "drink",
            "juice",
            "mocktail",
            "water",
            "tea",
            "soda",
        )
    ):
        return "Soft Beverages"
    return "Food"


def _collapse_super_category_amounts(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for row in rows or []:
        name = _to_super_category(str(row.get("category") or ""))
        amt = float(row.get("amount") or row.get("total") or 0)
        totals[name] = totals.get(name, 0.0) + amt
    return totals


def _collapse_super_category_totals(raw: Dict[str, float]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for name, amount in (raw or {}).items():
        super_name = _to_super_category(str(name or ""))
        totals[super_name] = totals.get(super_name, 0.0) + float(amount or 0)
    return totals


def _format_week_label(week_str: str) -> str:
    """Return week string as-is (expected format: YYYY-W##)."""
    week_str = str(week_str or "").strip()
    if not week_str:
        return "—"
    return week_str


def _achievement_color(pct: float) -> str:
    if pct >= 100:
        return C_GREEN
    if pct >= 80:
        return C_AMBER
    return C_RED


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_forecast_metrics(
    report_data: Dict[str, Any],
    daily_sales_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute blended month-end forecast (run-rate + weekday-weighted)."""
    iso = str(report_data.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
    except ValueError:
        dt = datetime.now()
    first_next = (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    dim = int((first_next - timedelta(days=1)).day)
    elapsed = int(max(1, dt.day))
    remaining = max(dim - elapsed, 0)

    mtd_net = _safe_float(report_data.get("mtd_net_sales"))
    mtd_target = _safe_float(report_data.get("mtd_target"))

    # Pure run-rate forecast
    forecast_run_rate = (mtd_net / elapsed) * dim if elapsed > 0 else 0.0

    # Weekday-weighted forecast for remaining days
    forecast_weekday = _weekday_weighted_forecast(
        dt,
        remaining,
        daily_sales_history or [],
    )

    # Blended: 50/50 if enough history, else pure run-rate
    if len(daily_sales_history or []) >= 7:
        forecast = 0.5 * forecast_run_rate + 0.5 * forecast_weekday
    else:
        forecast = forecast_run_rate

    pct = (forecast / mtd_target) * 100.0 if mtd_target > 0 else None
    gap = (forecast - mtd_target) if mtd_target > 0 else None
    req_run_rate = (
        (mtd_target - mtd_net) / remaining if mtd_target > 0 and remaining > 0 else None
    )

    return {
        "days_in_month": dim,
        "elapsed_days": elapsed,
        "remaining_days": remaining,
        "forecast_month_end_sales": forecast,
        "forecast_run_rate": forecast_run_rate,
        "forecast_weekday_weighted": forecast_weekday,
        "forecast_target_pct": pct,
        "forecast_gap_amount": gap,
        "required_daily_run_rate": req_run_rate,
    }


def _weekday_weighted_forecast(
    today: datetime,
    remaining_days: int,
    history: List[Dict[str, Any]],
) -> float:
    """Forecast remaining days using weekday averages from history."""
    if not history or remaining_days <= 0:
        return 0.0

    # Group sales by weekday (0=Mon..6=Sun)
    weekday_sums: Dict[int, float] = {}
    weekday_counts: Dict[int, int] = {}
    for row in history:
        date_str = str(row.get("date") or row.get("report_date") or "")
        net = _safe_float(row.get("net_total") or row.get("net_sales"))
        if not date_str or net <= 0:
            continue
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            continue
        wd = d.weekday()
        weekday_sums[wd] = weekday_sums.get(wd, 0) + net
        weekday_counts[wd] = weekday_counts.get(wd, 0) + 1

    if not weekday_counts:
        return 0.0

    # Compute average per weekday
    weekday_avg = {wd: weekday_sums[wd] / weekday_counts[wd] for wd in weekday_counts}

    # Sum forecast for each remaining calendar day
    forecast = 0.0
    for i in range(1, remaining_days + 1):
        future_date = today + timedelta(days=i)
        wd = future_date.weekday()
        forecast += weekday_avg.get(wd, 0.0)

    return forecast


def status_from_threshold(
    value: Optional[float],
    *,
    green_min: Optional[float] = None,
    amber_min: Optional[float] = None,
    green_max: Optional[float] = None,
    amber_max: Optional[float] = None,
    higher_is_better: bool,
) -> Dict[str, Any]:
    """Map a metric value to red/amber/green or na status."""
    if value is None:
        return {"status": "na", "color": C_MUTED, "label": "N/A"}

    v = float(value)
    if higher_is_better:
        if green_min is not None and v >= green_min:
            return {"status": "green", "color": C_GREEN, "label": "On Track"}
        if amber_min is not None and v >= amber_min:
            return {"status": "amber", "color": C_AMBER, "label": "Watch"}
        return {"status": "red", "color": C_RED, "label": "At Risk"}

    if green_max is not None and v <= green_max:
        return {"status": "green", "color": C_GREEN, "label": "Healthy"}
    if amber_max is not None and v <= amber_max:
        return {"status": "amber", "color": C_AMBER, "label": "Watch"}
    return {"status": "red", "color": C_RED, "label": "At Risk"}


def build_verbose_daily_summary(report_data: Dict[str, Any]) -> str:
    """Build a structured day brief for PNG and WhatsApp outputs."""
    r = dict(report_data or {})
    forecast = compute_forecast_metrics(r)

    net = _safe_float(r.get("net_total"))
    target = _safe_float(r.get("target"))
    pct_target = (net / target * 100.0) if target > 0 else None

    prev_day = r.get("previous_day_net_total")
    wk_ref = r.get("same_weekday_last_week_net_total")
    gross = _safe_float(r.get("gross_total"))
    discount = _safe_float(r.get("discount"))
    discount_pct = (discount / gross * 100.0) if gross > 0 else None

    apc = _safe_float(r.get("apc"))
    apc_base = r.get("apc_baseline_7d")
    apc_drop_pct = None
    if apc_base not in (None, 0):
        apc_drop_pct = ((float(apc_base) - apc) / float(apc_base)) * 100.0

    line_1 = (
        f"Today closed at {_r(net)} against target {_r(target)} ({pct_target:.0f}% achievement)."
        if pct_target is not None
        else f"Today closed at {_r(net)}; daily target is not configured."
    )
    line_2 = (
        f"Forecast month-end: {_r(forecast['forecast_month_end_sales'])} "
        f"({forecast['forecast_target_pct']:.0f}% of target)."
        if forecast["forecast_target_pct"] is not None
        else f"Forecast month-end: {_r(forecast['forecast_month_end_sales'])}; target comparison unavailable."
    )
    line_3 = (
        "Comparison to previous day/week benchmark unavailable due to incomplete history."
        if prev_day is None or wk_ref is None
        else (
            f"Vs previous day: {_r(net - float(prev_day))}; "
            f"vs same weekday last week: {_r(net - float(wk_ref))}."
        )
    )
    line_4 = (
        "Profitability watch: discount signal unavailable (gross sales missing)."
        if discount_pct is None
        else f"Profitability watch: discount at {discount_pct:.2f}% of gross."
    )
    line_5 = (
        "APC benchmark unavailable for anomaly check."
        if apc_drop_pct is None
        else f"APC is {_r(apc)} ({apc_drop_pct:.2f}% below 7-day baseline)."
    )
    line_6 = "Suggested action: tighten discount approvals and push high-APC combos in next shift."
    return "\n".join([line_1, line_2, line_3, line_4, line_5, line_6])


def compute_metric_statuses(
    report_data: Dict[str, Any],
    daily_sales_history: Optional[List[Dict]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compute status colors for core target/profitability metrics."""
    r = dict(report_data or {})
    forecast = compute_forecast_metrics(r, daily_sales_history=daily_sales_history)

    pct_target = _safe_float(r.get("pct_target"))
    target_status = status_from_threshold(
        pct_target,
        green_min=100,
        amber_min=85,
        higher_is_better=True,
    )

    forecast_status = status_from_threshold(
        forecast.get("forecast_target_pct"),
        green_min=100,
        amber_min=95,
        higher_is_better=True,
    )

    gross = _safe_float(r.get("gross_total"))
    discount = _safe_float(r.get("discount"))
    discount_pct = (discount / gross * 100.0) if gross > 0 else None
    discount_status = status_from_threshold(
        discount_pct,
        green_max=5,
        amber_max=8,
        higher_is_better=False,
    )

    apc = _safe_float(r.get("apc"))
    apc_base = r.get("apc_baseline_7d")
    apc_drop_pct = None
    if apc_base not in (None, 0):
        apc_drop_pct = ((float(apc_base) - apc) / float(apc_base)) * 100.0
    apc_status = status_from_threshold(
        apc_drop_pct,
        green_max=5,
        amber_max=12,
        higher_is_better=False,
    )

    return {
        "target": target_status,
        "forecast": forecast_status,
        "discount": discount_status,
        "apc": apc_status,
    }


def _save_fig(fig) -> BytesIO:
    buf = BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=DPI,
        bbox_inches="tight",
        pad_inches=0.05,
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


def _table_header_row(ax, x, y, cols, widths, row_h, bg=C_HEADER, font_size=None):
    """Light header row for a data table."""
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
    fs = font_size if font_size else 11.0
    cx = x
    for i, (col, cw) in enumerate(zip(cols, widths)):
        ha = "left" if i == 0 else "right"
        px = cx + 0.006 if ha == "left" else cx + cw - 0.006
        _label(
            ax,
            px,
            y + row_h * 0.5,
            col,
            size=fs,
            color=C_BRAND,
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
    row_h,
    bg=C_CARD,
    alt_bg=C_BAND,
    is_alt=False,
    bold=False,
    text_color=C_SLATE,
    right_color=None,
    font_size=None,
    cell_colors=None,
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
    fs = font_size if font_size else 11.0
    cx = x
    for i, (cell, cw) in enumerate(zip(cells, widths)):
        ha = "left" if i == 0 else "right"
        px = cx + 0.006 if ha == "left" else cx + cw - 0.006
        if cell_colors and i < len(cell_colors) and cell_colors[i]:
            rc = cell_colors[i]
        elif right_color and i > 0:
            rc = right_color
        else:
            rc = text_color
        _label(
            ax,
            px,
            y + row_h * 0.5,
            str(cell),
            size=fs,
            color=rc,
            weight="bold" if bold else "normal",
            ha=ha,
        )
        cx += cw


def _table_section_label(ax, x, y, text, w, row_h, color=C_BRAND):
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
    _label(ax, x + 0.012, y + row_h * 0.5, text, size=11.0, color=color, weight="bold")


# ══════════════════════════════════════════════════════════════════════════════
# Section builders
# ══════════════════════════════════════════════════════════════════════════════


def _banner_height(n_rows: int) -> float:
    """Compute banner height proportional to section content.

    Short sections (few rows) get a smaller banner so the banner-to-content
    ratio stays consistent across all PNG sections.
    """
    return max(0.050, min(0.065, 0.002 + 0.002 * n_rows))


def _section_sales_summary(
    ax,
    r: Dict,
    location_name: str,
    row_h: float,
    per_outlet: Optional[List[Tuple[str, Dict]]] = None,
    daily_sales_history: Optional[List[Dict]] = None,
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
    statuses = compute_metric_statuses(r, daily_sales_history=daily_sales_history)
    forecast = compute_forecast_metrics(r, daily_sales_history=daily_sales_history)
    ach_color = statuses["target"]["color"]

    # ── Header banner (slim) ─────────────────────────────────────────────
    banner_h = row_h * BANNER_PX / ROW_PX
    banner_top = 1.0
    banner_y = banner_top - banner_h
    gap = row_h * SECTION_GAP_PX / ROW_PX
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_BANNER, border=C_BANNER)
    _hbar(ax, 0, banner_top, 1.0, h=0.003, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - banner_h * 0.28,
        f"{location_name.upper()}  —  END OF DAY REPORT",
        size=11.5,
        color=C_WHITE,
        weight="bold",
    )
    _label(
        ax,
        0.012,
        banner_top - banner_h * 0.69,
        day_lbl,
        size=9.5,
        color=C_DATE_LABEL,
    )
    _label(
        ax,
        0.988,
        banner_top - banner_h * 0.28,
        f"{pct_tgt:.0f}% of target",
        size=11.0,
        color=ach_color,
        weight="bold",
        ha="right",
    )
    _label(
        ax,
        0.988,
        banner_top - banner_h * 0.69,
        _r(r.get("net_total", 0)) + " net",
        size=9.5,
        color=C_WHITE,
        ha="right",
    )

    # ── Column headers ───────────────────────────────────────────────────
    cur_y = banner_y - gap - row_h
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
                cur_y - row_h,
                section_label,
                sum(col_w),
                row_h=row_h,
            )
            cur_y -= row_h
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
        bg=C_BANNER,
        text_color=C_WHITE,
        right_color=C_WHITE,
    )

    # ── MTD block ────────────────────────────────────────────────────────
    cur_y -= row_h * 0.3
    _table_header_row(
        ax, 0, cur_y - row_h, ["MTD Summary"] + [""] * (len(col_w) - 1), col_w, row_h
    )
    cur_y -= row_h
    row_idx[0] = 0

    _row("MTD Total Covers", "mtd_total_covers", fmt="int", bold=True)
    _row("APC (Day)", "apc", fmt="currency", right_color=statuses["apc"]["color"])

    def _apc_month(d):
        mtd_net = float(d.get("mtd_net_sales") or 0)
        mtd_cov = int(d.get("mtd_total_covers") or 0)
        return mtd_net / mtd_cov if mtd_cov > 0 else 0.0

    _row("APC (Month)", _apc_month, fmt="currency")

    _row("Complimentary", "complimentary", fmt="currency")
    _row("MTD Complimentary", "mtd_complimentary", fmt="currency")
    _row("Daily Avg. Net Sales", "mtd_avg_daily", fmt="currency")
    _row("MTD Net Sales", "mtd_net_sales", fmt="currency", bold=True)
    _row(
        "MTD Discount",
        "mtd_discount",
        fmt="currency",
        right_color=statuses["discount"]["color"],
    )

    def _mtd_net_excl(d):
        return float(d.get("mtd_net_sales") or 0) - float(d.get("mtd_discount") or 0)

    _row("MTD Net (Excl. Disc.)", _mtd_net_excl, fmt="currency", bold=True)

    _row("Sales Target", "mtd_target", fmt="currency")
    _row("% of Target", "mtd_pct_target", fmt="pct", bold=True, right_color=ach_color)

    _row(None, None, section_label="Forecast")
    _row(
        "Forecast Month-End",
        lambda d: compute_forecast_metrics(d)["forecast_month_end_sales"],
    )

    def _forecast_target_pct(d):
        val = compute_forecast_metrics(d)["forecast_target_pct"]
        return _pct(val) if val is not None else "N/A"

    _row(
        "Forecast vs Target",
        _forecast_target_pct,
        fmt="str",
        right_color=statuses["forecast"]["color"],
    )

    def _required_run_rate(d):
        val = compute_forecast_metrics(d)["required_daily_run_rate"]
        return _r(val) if val is not None else "N/A"

    _row("Required Daily Run Rate", _required_run_rate, fmt="str")

    # ylim set by _fig_for_section


def _section_category(
    ax,
    r: Dict,
    location_name: str,
    row_h: float,
    mtd_category: Dict[str, float],
    day_lbl: str,
    per_outlet: Optional[List[Tuple[str, Dict]]] = None,
    per_outlet_category: Optional[List[Tuple[str, Dict[str, float]]]] = None,
) -> None:
    ax.set_xlim(0, 1)
    ax.axis("off")

    multi = per_outlet and len(per_outlet) >= 2
    std_cats = ["Food", "Liquor", "Beer", "Soft Beverages", "Coffee", "Tobacco"]

    daily_cat = _collapse_super_category_amounts(r.get("categories") or [])
    mtd_category = _collapse_super_category_totals(dict(mtd_category or {}))
    total_cat_mtd = sum(mtd_category.values()) or 1.0

    # Per-outlet daily category data
    outlet_daily_cats = []
    if multi and per_outlet:
        for _, od in per_outlet:
            od_cats = _collapse_super_category_amounts(od.get("categories") or [])
            outlet_daily_cats.append(od_cats)

    cat_order = [x for x in std_cats if x in daily_cat or x in mtd_category]
    for k in sorted(mtd_category.keys()):
        if k not in cat_order:
            cat_order.append(k)
    if not cat_order:
        cat_order = []

    # Column widths: for multi-outlet add per-outlet daily columns
    if multi:
        n_data = len(per_outlet) + 1  # outlets + combined
        label_w = 0.19
        mtd_w = 0.14
        pct_w = 0.07
        remaining = 1.0 - label_w - mtd_w - pct_w
        data_w = remaining / n_data
        col_w = [label_w] + [data_w] * n_data + [mtd_w, pct_w]
    else:
        col_w = [0.44, 0.22, 0.22, 0.06]

    tbl_x = 0.0

    # Header banner (proportional to row_h)
    banner_h = row_h * BANNER_PX / ROW_PX
    banner_top = 1.0
    banner_y = banner_top - banner_h
    gap = row_h * SECTION_GAP_PX / ROW_PX
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_BANNER, border=C_BANNER)
    _hbar(ax, 0, banner_top, 1.0, h=0.003, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - banner_h * 0.28,
        f"Category Sales \u2014 {location_name[:28]}",
        size=11.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(ax, 0.012, banner_top - banner_h * 0.69, day_lbl, size=9.0, color="#8BA3BD")

    cur_y = banner_y - gap - row_h

    # Table header
    if multi:
        headers = (
            ["Category"]
            + [
                _short_outlet_name(nm, 8 if len(per_outlet) > 2 else 10)
                for nm, _ in per_outlet
            ]
            + ["Comb.", "MTD", "%"]
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
        bg=C_BANNER,
        bold=True,
        text_color=C_WHITE,
    )

    # ylim set by _fig_for_section


def _section_service(
    ax,
    r: Dict,
    location_name: str,
    row_h: float,
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

    if multi:
        n_data = len(per_outlet) + 1
        label_w = 0.19
        mtd_w = 0.14
        pct_w = 0.07
        remaining = 1.0 - label_w - mtd_w - pct_w
        data_w = remaining / n_data
        col_w = [label_w] + [data_w] * n_data + [mtd_w, pct_w]
    else:
        col_w = [0.44, 0.22, 0.22, 0.06]
    tbl_x = 0.0

    # Slim header banner
    banner_h = row_h * BANNER_PX / ROW_PX
    banner_top = 1.0
    banner_y = banner_top - banner_h
    gap = row_h * SECTION_GAP_PX / ROW_PX
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_BANNER, border=C_BANNER)
    _hbar(ax, 0, banner_top, 1.0, h=0.003, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - banner_h * 0.28,
        f"Service Sales \u2014 {location_name[:28]}",
        size=11.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(ax, 0.012, banner_top - banner_h * 0.69, day_lbl, size=9.0, color="#8BA3BD")

    cur_y = banner_y - gap - row_h

    if multi:
        headers = (
            ["Service"]
            + [
                _short_outlet_name(nm, 8 if len(per_outlet) > 2 else 10)
                for nm, _ in per_outlet
            ]
            + ["Comb.", "MTD", "%"]
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
        # ylim set by _fig_for_section
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
        bg=C_BANNER,
        bold=True,
        text_color=C_WHITE,
    )

    # ylim set by _fig_for_section


def _section_footfall(
    ax, month_footfall_rows: List[Dict], location_name: str, row_h: float
) -> None:
    ax.set_xlim(0, 1)
    ax.axis("off")

    rows = list(month_footfall_rows or [])

    # Slim header banner
    banner_h = row_h * BANNER_PX / ROW_PX
    banner_top = 1.0
    banner_y = banner_top - banner_h
    gap = row_h * SECTION_GAP_PX / ROW_PX
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_BANNER, border=C_BANNER)
    _hbar(ax, 0, banner_top, 1.0, h=0.003, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - banner_h * 0.28,
        "Daily Footfall — Month to Date",
        size=11.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(
        ax,
        0.012,
        banner_top - banner_h * 0.69,
        location_name[:32],
        size=9.0,
        color="#8BA3BD",
    )

    if not rows:
        _label(
            ax,
            0.5,
            banner_y - gap,
            "No footfall data for this month",
            size=11.0,
            color=C_MUTED,
            ha="center",
        )
        # ylim set by _fig_for_section
        return

    col_w = [0.40, 0.16, 0.16, 0.16]
    tbl_x = 0.0

    cur_y = banner_y - gap - row_h
    _table_header_row(
        ax,
        tbl_x,
        cur_y - row_h,
        ["Date", "Dinner", "Lunch", "Total"],
        col_w,
        row_h,
        font_size=10.5,
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
        bg=C_BANNER,
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

    # ylim set by _fig_for_section


def _section_footfall_metrics(
    ax,
    monthly_rows: Optional[List[Dict]],
    weekly_rows: Optional[List[Dict]],
    location_name: str,
    row_h: float,
) -> None:
    """Footfall metrics section with monthly and weekly summary tables."""
    ax.set_xlim(0, 1)
    ax.axis("off")

    monthly = list(monthly_rows or [])
    weekly = list(weekly_rows or [])

    # Slim header banner
    banner_h = row_h * BANNER_PX / ROW_PX
    banner_top = 1.0
    banner_y = banner_top - banner_h
    gap = row_h * SECTION_GAP_PX / ROW_PX
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_BANNER, border=C_BANNER)
    _hbar(ax, 0, banner_top, 1.0, h=0.003, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - banner_h * 0.28,
        "Footfall Metrics",
        size=11.0,
        color=C_WHITE,
        weight="bold",
    )
    _label(
        ax,
        0.012,
        banner_top - banner_h * 0.69,
        location_name[:32],
        size=9.0,
        color="#8BA3BD",
    )

    cur_y = banner_y - gap - row_h

    # Helper to calculate MoM/WoW % change
    def _calc_pct_change(current: float, previous: float) -> str:
        if previous == 0:
            return "—"
        pct = ((current - previous) / previous) * 100
        return f"{pct:+.2f}%"

    # Helper to calculate daily avg % change
    def _calc_avg_pct_change(
        curr_foot: int, curr_days: int, prev_foot: int, prev_days: int
    ) -> str:
        if prev_days == 0 or prev_foot == 0:
            return "—"
        curr_avg = curr_foot / curr_days
        prev_avg = prev_foot / prev_days
        pct = ((curr_avg - prev_avg) / prev_avg) * 100
        return f"{pct:+.2f}%"

    # ── Monthly Table ─────────────────────────────────────────────────────────
    if monthly:
        cur_y -= row_h * 0.2
        _label(ax, 0.012, cur_y, "Monthly", size=11.0, color=C_BRAND, weight="bold")
        cur_y -= row_h * 0.8

        # Header - better distribution, filling more width
        col_w = [0.20, 0.15, 0.16, 0.14, 0.16, 0.17]
        headers = [
            "Month",
            "Footfall",
            "% Change",
            "Total Days",
            "Daily Avg.",
            "% Change",
        ]
        cur_y -= row_h
        _table_header_row(ax, 0.01, cur_y, headers, col_w, row_h, font_size=11.0)

        # Sort by month descending (most recent first)
        sorted_monthly = sorted(monthly, key=lambda x: x.get("month", ""), reverse=True)

        # Collect values for conditional formatting (best/worst highlighting)
        monthly_covers = []
        monthly_daily_avgs = []
        for row in sorted_monthly[:9]:
            covers = int(row.get("covers") or 0)
            total_days = int(row.get("total_days") or 0)
            daily_avg = covers / total_days if total_days > 0 else 0
            monthly_covers.append(covers)
            monthly_daily_avgs.append(daily_avg)

        # Find best/worst indices (only if 2+ rows with data)
        valid_covers = [(i, v) for i, v in enumerate(monthly_covers) if v > 0]
        valid_avgs = [(i, v) for i, v in enumerate(monthly_daily_avgs) if v > 0]

        monthly_best_idx = {}
        monthly_worst_idx = {}
        if len(valid_covers) >= 2:
            monthly_best_idx["footfall"] = max(valid_covers, key=lambda x: x[1])[0]
            monthly_worst_idx["footfall"] = min(valid_covers, key=lambda x: x[1])[0]
        if len(valid_avgs) >= 2:
            monthly_best_idx["daily_avg"] = max(valid_avgs, key=lambda x: x[1])[0]
            monthly_worst_idx["daily_avg"] = min(valid_avgs, key=lambda x: x[1])[0]

        for idx, row in enumerate(sorted_monthly[:9]):
            month = str(row.get("month", ""))
            covers = int(row.get("covers") or 0)
            total_days = int(row.get("total_days") or 0)
            daily_avg = covers / total_days if total_days > 0 else 0

            # Format month label
            try:
                dt = datetime.strptime(f"{month}-01", "%Y-%m-%d")
                month_label = dt.strftime("%b-%Y")
            except ValueError:
                month_label = month

            # Calculate % changes (compare to previous month in sorted list)
            foot_pct = "—"
            avg_pct = "—"
            if idx < len(sorted_monthly) - 1:
                prev_row = sorted_monthly[idx + 1]
                prev_covers = int(prev_row.get("covers") or 0)
                prev_days = int(prev_row.get("total_days") or 0)
                foot_pct = _calc_pct_change(covers, prev_covers)
                avg_pct = _calc_avg_pct_change(
                    covers, total_days, prev_covers, prev_days
                )

            cells = [
                month_label,
                f"{covers:,}",
                foot_pct,
                str(total_days),
                f"{daily_avg:.0f}",
                avg_pct,
            ]

            # Build per-cell colors for conditional formatting
            cell_colors = [None] * 6
            if idx == monthly_best_idx.get("footfall"):
                cell_colors[1] = C_GREEN
            elif idx == monthly_worst_idx.get("footfall"):
                cell_colors[1] = C_RED
            if idx == monthly_best_idx.get("daily_avg"):
                cell_colors[4] = C_GREEN
            elif idx == monthly_worst_idx.get("daily_avg"):
                cell_colors[4] = C_RED

            cur_y -= row_h
            _table_data_row(
                ax,
                0.01,
                cur_y,
                cells,
                col_w,
                row_h=row_h,
                is_alt=(idx % 2 == 1),
                font_size=11.0,
                cell_colors=cell_colors,
            )

        cur_y -= row_h * 0.5

    # ── Weekly Table ──────────────────────────────────────────────────────────
    if weekly:
        cur_y -= row_h * 0.2
        _label(ax, 0.012, cur_y, "Weekly", size=11.0, color=C_BRAND, weight="bold")
        cur_y -= row_h * 0.8

        # Header - better distribution, filling more width
        col_w = [0.20, 0.15, 0.16, 0.14, 0.16, 0.17]
        headers = [
            "Week",
            "Footfall",
            "% Change",
            "Total Days",
            "Daily Avg.",
            "% Change",
        ]
        cur_y -= row_h
        _table_header_row(ax, 0.01, cur_y, headers, col_w, row_h, font_size=11.0)

        # Sort by week descending (most recent first)
        sorted_weekly = sorted(weekly, key=lambda x: x.get("week", ""), reverse=True)

        # Collect values for conditional formatting (best/worst highlighting)
        weekly_covers = []
        weekly_daily_avgs = []
        for row in sorted_weekly[:4]:
            covers = int(row.get("covers") or 0)
            total_days = int(row.get("total_days") or 0)
            daily_avg = covers / total_days if total_days > 0 else 0
            weekly_covers.append(covers)
            weekly_daily_avgs.append(daily_avg)

        # Find best/worst indices (only if 2+ rows with data)
        valid_covers = [(i, v) for i, v in enumerate(weekly_covers) if v > 0]
        valid_avgs = [(i, v) for i, v in enumerate(weekly_daily_avgs) if v > 0]

        weekly_best_idx = {}
        weekly_worst_idx = {}
        if len(valid_covers) >= 2:
            weekly_best_idx["footfall"] = max(valid_covers, key=lambda x: x[1])[0]
            weekly_worst_idx["footfall"] = min(valid_covers, key=lambda x: x[1])[0]
        if len(valid_avgs) >= 2:
            weekly_best_idx["daily_avg"] = max(valid_avgs, key=lambda x: x[1])[0]
            weekly_worst_idx["daily_avg"] = min(valid_avgs, key=lambda x: x[1])[0]

        for idx, row in enumerate(sorted_weekly[:4]):
            week = str(row.get("week", ""))
            covers = int(row.get("covers") or 0)
            total_days = int(row.get("total_days") or 0)
            daily_avg = covers / total_days if total_days > 0 else 0

            # Calculate % changes (compare to previous week in sorted list)
            foot_pct = "—"
            avg_pct = "—"
            if idx < len(sorted_weekly) - 1:
                prev_row = sorted_weekly[idx + 1]
                prev_covers = int(prev_row.get("covers") or 0)
                prev_days = int(prev_row.get("total_days") or 0)
                foot_pct = _calc_pct_change(covers, prev_covers)
                avg_pct = _calc_avg_pct_change(
                    covers, total_days, prev_covers, prev_days
                )

            cells = [
                _format_week_label(week),
                f"{covers:,}",
                foot_pct,
                str(total_days),
                f"{daily_avg:.0f}",
                avg_pct,
            ]

            # Build per-cell colors for conditional formatting
            cell_colors = [None] * 6
            if idx == weekly_best_idx.get("footfall"):
                cell_colors[1] = C_GREEN
            elif idx == weekly_worst_idx.get("footfall"):
                cell_colors[1] = C_RED
            if idx == weekly_best_idx.get("daily_avg"):
                cell_colors[4] = C_GREEN
            elif idx == weekly_worst_idx.get("daily_avg"):
                cell_colors[4] = C_RED

            cur_y -= row_h
            _table_data_row(
                ax,
                0.01,
                cur_y,
                cells,
                col_w,
                row_h=row_h,
                is_alt=(idx % 2 == 1),
                font_size=11.0,
                cell_colors=cell_colors,
            )

    # If no data at all
    if not monthly and not weekly:
        cur_y -= row_h * 2
        _label(
            ax,
            0.5,
            cur_y,
            "No footfall metrics data available",
            size=11.0,
            color=C_MUTED,
            ha="center",
        )

    # ylim set by _fig_for_section


# ── Short outlet name helper ──────────────────────────────────────────────────


def _short_outlet_name(name: str, max_len: int = 18) -> str:
    name = (name or "").strip()
    for prefix in ("Boteco - ", "Boteco-", "Boteco "):
        if name.lower().startswith(prefix.lower()):
            name = name[len(prefix) :].strip()
            break
    return name if len(name) <= max_len else name[: max_len - 1] + "\u2026"


def _section_key_slug(value: str, default: str = "outlet") -> str:
    """Create a compact ascii-safe slug for PNG section keys."""
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    slug = slug.strip("_")
    if not slug:
        slug = default
    return slug[:22]


def _outlet_col_widths(n_outlets: int, label_frac: float = 0.24) -> List[float]:
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
    n_rows: int, min_rows: int = 3, cap_h: float = 20.0, w: float = 8.5
) -> Tuple[plt.Figure, plt.Axes, float]:
    """Create a figure with height computed from fixed pixel targets.

    Returns (fig, ax, row_h) where row_h is in axis units (0-1 range).
    Each row will be exactly ROW_PX pixels tall regardless of section size.
    """
    n = max(n_rows, min_rows)
    fig_h = min(cap_h, (n * ROW_PX + BANNER_PX + SECTION_GAP_PX + BOTTOM_PAD_PX) / DPI)
    fig, ax = plt.subplots(figsize=(w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(C_PAGE)
    ax.set_facecolor(C_PAGE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    row_h = ROW_PX / (DPI * fig_h)
    return fig, ax, row_h


@st.cache_data(ttl=600)
def generate_sheet_style_report_sections(
    report_data: Dict,
    location_name: str = "Boteco Bangalore",
    mtd_category: Optional[Dict[str, float]] = None,
    mtd_service: Optional[Dict[str, float]] = None,
    month_footfall_rows: Optional[List[Dict]] = None,
    per_outlet_summaries: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
    per_outlet_category: Optional[List[Tuple[str, Dict[str, float]]]] = None,
    per_outlet_service: Optional[List[Tuple[str, Dict[str, float]]]] = None,
    per_outlet_footfall: Optional[List[Tuple[str, List[Dict[str, Any]]]]] = None,
    footfall_metrics_monthly: Optional[List[Dict]] = None,
    footfall_metrics_weekly: Optional[List[Dict]] = None,
    per_outlet_footfall_metrics: Optional[
        List[Tuple[str, List[Dict], List[Dict]]]
    ] = None,
    daily_sales_history: Optional[List[Dict]] = None,
) -> Dict[str, BytesIO]:
    """Generate section PNG buffers.

    Returns keys:
      - sales_summary
      - category
      - service
      - footfall (single-outlet/legacy daily footfall)
      - footfall__{outlet_slug}_{idx} (multi-outlet per-outlet daily footfall)
      - footfall_metrics (single-outlet metrics)
      - footfall_metrics__{outlet_slug}_{idx} (multi-outlet per-outlet metrics)
    """
    r = report_data
    mc = dict(mtd_category or {})
    ms = dict(mtd_service or {})
    mf = list(month_footfall_rows or [])
    iso = str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    per_outlet = list(per_outlet_summaries) if per_outlet_summaries else None
    per_outlet_cat = list(per_outlet_category) if per_outlet_category else None
    per_outlet_svc = list(per_outlet_service) if per_outlet_service else None
    per_outlet_ff = list(per_outlet_footfall) if per_outlet_footfall else None
    ff_metrics_mo = list(footfall_metrics_monthly) if footfall_metrics_monthly else None
    ff_metrics_wk = list(footfall_metrics_weekly) if footfall_metrics_weekly else None
    per_outlet_ff_metrics = (
        list(per_outlet_footfall_metrics) if per_outlet_footfall_metrics else None
    )

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
    est_rows = 10 + n_pay + n_tax + 12  # MTD + forecast rows
    fig, ax, row_h = _fig_for_section(est_rows, min_rows=8, cap_h=36.0, w=fig_w)
    _section_sales_summary(
        ax,
        r,
        location_name,
        row_h,
        per_outlet,
        daily_sales_history=daily_sales_history,
    )
    out["sales_summary"] = _save_fig(fig)

    # Category
    n_cat = len(mc) or 3
    fig, ax, row_h = _fig_for_section(n_cat + 4, min_rows=3, cap_h=14.0, w=fig_w)
    _section_category(
        ax,
        r,
        location_name,
        row_h,
        mc,
        day_lbl,
        per_outlet=per_outlet,
        per_outlet_category=per_outlet_cat,
    )
    out["category"] = _save_fig(fig)

    # Service
    n_svc = len(ms) or 3
    fig, ax, row_h = _fig_for_section(n_svc + 4, min_rows=3, cap_h=12.0, w=fig_w)
    _section_service(
        ax,
        r,
        location_name,
        row_h,
        ms,
        day_lbl,
        per_outlet=per_outlet,
        per_outlet_service=per_outlet_svc,
    )
    out["service"] = _save_fig(fig)

    # Footfall
    # Prefer new metrics-based sections if data provided
    if per_outlet_ff_metrics and len(per_outlet_ff_metrics) > 1:
        # Multi-outlet with per-outlet metrics
        for idx, (outlet_name, mo_rows, wk_rows) in enumerate(per_outlet_ff_metrics):
            n_mo = len(mo_rows) if mo_rows else 0
            n_wk = len(wk_rows) if wk_rows else 0
            n_ft = 5 + n_mo + n_wk
            fig, ax, row_h = _fig_for_section(n_ft, min_rows=4, cap_h=16.0, w=fig_w)
            _section_footfall_metrics(ax, mo_rows, wk_rows, outlet_name, row_h)
            outlet_slug = _section_key_slug(outlet_name, default=f"outlet_{idx}")
            out[f"footfall_metrics__{outlet_slug}_{idx}"] = _save_fig(fig)
    elif ff_metrics_mo or ff_metrics_wk:
        # Single-outlet with metrics
        n_mo = len(ff_metrics_mo) if ff_metrics_mo else 0
        n_wk = len(ff_metrics_wk) if ff_metrics_wk else 0
        n_ft = 5 + n_mo + n_wk
        fig, ax, row_h = _fig_for_section(n_ft, min_rows=4, cap_h=16.0, w=fig_w)
        _section_footfall_metrics(
            ax, ff_metrics_mo, ff_metrics_wk, location_name, row_h
        )
        out["footfall_metrics"] = _save_fig(fig)
    elif per_outlet_ff and len(per_outlet_ff) > 1:
        # Fallback to daily footfall for backward compatibility
        for idx, (outlet_name, ff_rows) in enumerate(per_outlet_ff):
            ff_rows = list(ff_rows or [])
            n_ft = len(ff_rows) + 4
            fig, ax, row_h = _fig_for_section(n_ft, min_rows=5, cap_h=33.0, w=fig_w)
            _section_footfall(ax, ff_rows, outlet_name, row_h)
            outlet_slug = _section_key_slug(outlet_name, default=f"outlet_{idx}")
            out[f"footfall__{outlet_slug}_{idx}"] = _save_fig(fig)
    else:
        # Single-outlet daily footfall (legacy)
        n_ft = len(mf) + 4
        fig, ax, row_h = _fig_for_section(n_ft, min_rows=5, cap_h=33.0, w=fig_w)
        _section_footfall(ax, mf, location_name, row_h)
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
    per_outlet_footfall: Optional[List[Tuple[str, List[Dict[str, Any]]]]] = None,
    footfall_metrics_monthly: Optional[List[Dict]] = None,
    footfall_metrics_weekly: Optional[List[Dict]] = None,
    per_outlet_footfall_metrics: Optional[
        List[Tuple[str, List[Dict], List[Dict]]]
    ] = None,
) -> BytesIO:
    """
    Composite PNG from generated sections stacked vertically.
    For multi-outlet inputs this includes one footfall section per outlet,
    otherwise a single combined footfall section.
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
        per_outlet_footfall,
        footfall_metrics_monthly,
        footfall_metrics_weekly,
        per_outlet_footfall_metrics,
    )

    # Stack generated sections into one tall image using matplotlib
    from PIL import Image as PILImage
    import numpy as np

    imgs = []
    for key in ("sales_summary", "category", "service"):
        if key in sections:
            buf = sections[key]
            buf.seek(0)
            imgs.append(PILImage.open(buf).convert("RGB"))

    footfall_keys = [
        key
        for key in sections.keys()
        if isinstance(key, str) and key.startswith("footfall")
    ]
    if not footfall_keys:
        return BytesIO()

    for key in footfall_keys:
        buf = sections[key]
        buf.seek(0)
        imgs.append(PILImage.open(buf).convert("RGB"))

    total_h = sum(im.height for im in imgs)
    max_w = max(im.width for im in imgs)
    composite = PILImage.new("RGB", (max_w, total_h), color=(247, 250, 252))
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
    cat_amount_total = sum(c.get("amount", 0) for c in categories)
    has_amounts = cat_amount_total > 0
    if has_amounts:
        cat_total_divisor = cat_amount_total or 1
        cat_lines = (
            "\n".join(
                f"  \u2022 {c.get('category', '?')}: "
                f"{int(c.get('amount', 0) / cat_total_divisor * 100)}% "
                f"({config.CURRENCY_FORMAT.format(c.get('amount', 0))})"
                for c in categories
                if c.get("amount", 0) > 0
            )
            or "  \u2022 Data not available"
        )
    else:
        cat_qty_total = sum(c.get("qty", 0) for c in categories) or 1
        cat_lines = (
            "\n".join(
                f"  \u2022 {c.get('category', '?')}: "
                f"{c.get('qty', 0)} items "
                f"({int(c.get('qty', 0) / cat_qty_total * 100)}%)"
                for c in categories
                if c.get("qty", 0) > 0
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
