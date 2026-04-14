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

The composite PNG is built with ReportLab Platypus (Table + Flowables),
rendered to PDF and converted to PNG via PyMuPDF, then stacked with Pillow.
"""

import os
import re
from io import BytesIO
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Spacer,
    Flowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import fitz
from PIL import Image as PILImage

import config

# ── Font registration ────────────────────────────────────────────────────────
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(
    TTFont("DejaVuSans-Bold", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
)

# ── Palette (Boteco Mango) ─────────────────────────────────────────────────
C_PAGE = "#F7FAFC"
C_CARD = "#FFFFFF"
C_BRAND = "#1F5FA8"
C_BRAND_DARK = "#174A82"
C_BANNER = "#1A3A5C"
C_HEADER = "#EEF2F7"
C_SLATE = "#1E293B"
C_DATE_LABEL = "#A5BCD2"
C_MUTED = "#64748B"
C_BORDER = "#E2E8F0"
C_BAND = "#EDF2F7"
C_GREEN = "#2E7D32"
C_AMBER = "#946B00"
C_RED = "#DC2626"
C_WHITE = "#FFFFFF"

FONT_NAME = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
DPI = 150

# ── Layout constants (points) ───────────────────────────────────────────────
SECTION_WIDTHS = {1: 612, 2: 720}
PAGE_PAD = 12

BANNER_PAD_TOP = 8
BANNER_PAD_BOTTOM = 6
BANNER_PAD_LEFT = 10
ROW_PAD_TOP = 3
ROW_PAD_BOTTOM = 3
CELL_PAD_LEFT = 6
CELL_PAD_RIGHT = 6
GAP_BELOW_BANNER = 4
GAP_ABOVE_SECTION_LABEL = 4
GAP_ABOVE_SUBSECTION = 6

FONT_SIZE_ROW = 8.5
FONT_SIZE_HEADER = 8.5
FONT_SIZE_BANNER_TITLE = 9.5
FONT_SIZE_BANNER_SUB = 7.5
FONT_SIZE_BANNER_TITLE_SUMMARY = 10.5
FONT_SIZE_BANNER_SUB_SUMMARY = 8.5
FONT_SIZE_SECTION_LABEL = 8.5
FONT_SIZE_KPI_LABEL = 8.5
FONT_SIZE_KPI_VALUE = 16


def _hex(hx: str) -> colors.HexColor:
    return colors.HexColor(hx)


# ── Helpers ──────────────────────────────────────────────────────────────────


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
    week_str = str(week_str or "").strip()
    if not week_str:
        return "\u2014"
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

    forecast_run_rate = (mtd_net / elapsed) * dim if elapsed > 0 else 0.0

    forecast_weekday = _weekday_weighted_forecast(
        dt,
        remaining,
        daily_sales_history or [],
    )

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
    if not history or remaining_days <= 0:
        return 0.0
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
    weekday_avg = {wd: weekday_sums[wd] / weekday_counts[wd] for wd in weekday_counts}
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


# ═══════════════════════════════════════════════════════════════════════════
# PDF → PNG conversion
# ═══════════════════════════════════════════════════════════════════════════


def _pdf_bytes_to_png(pdf_bytes: BytesIO, dpi: int = DPI) -> BytesIO:
    """Convert a single-page PDF to a PNG BytesIO at the given DPI."""
    doc = fitz.open(stream=pdf_bytes.read(), filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=False)
    buf.seek(0)
    doc.close()
    return buf


def _render_elements_to_png(
    elements: list,
    width_pt: float,
    dpi: int = DPI,
) -> BytesIO:
    """Render a list of Platypus Flowables to a PNG BytesIO.

    Pre-calculates content height so the PDF page fits tightly,
    eliminating whitespace below the content.
    """
    left_margin = PAGE_PAD
    right_margin = PAGE_PAD
    top_margin = PAGE_PAD
    bottom_margin = PAGE_PAD
    avail_w = width_pt - left_margin - right_margin

    story = list(elements)

    # Calculate total content height by wrapping each flowable
    total_height = 0.0
    for flowable in story:
        w, h = flowable.wrap(avail_w, 100000)
        total_height += h

    page_h = total_height + top_margin + bottom_margin + 4
    if page_h < 100:
        page_h = 100

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(width_pt, page_h),
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )

    doc.build(story, onFirstPage=lambda d, c: None, onLaterPages=lambda d, c: None)
    buf.seek(0)

    pdf_buf = BytesIO(buf.getvalue())
    png_buf = _pdf_bytes_to_png(pdf_buf, dpi=dpi)
    return png_buf


# ═══════════════════════════════════════════════════════════════════════════
# Custom Flowables
# ═══════════════════════════════════════════════════════════════════════════


class _BannerFlowable(Flowable):
    """Full-width banner with brand bar, title, subtitle, right-aligned KPI."""

    def __init__(
        self,
        width: float,
        title: str,
        subtitle: str,
        right_title: str = "",
        right_subtitle: str = "",
        right_title_color: str = C_WHITE,
    ):
        Flowable.__init__(self)
        self.width = width
        self.title = title
        self.subtitle = subtitle
        self.right_title = right_title
        self.right_subtitle = right_subtitle
        self.right_title_color = right_title_color
        self.height = (
            BANNER_PAD_TOP
            + FONT_SIZE_BANNER_TITLE_SUMMARY
            + FONT_SIZE_BANNER_SUB_SUMMARY
            + BANNER_PAD_BOTTOM
            + 6
        )

    def wrap(self, availWidth, availHeight):
        return (self.width, self.height)

    def draw(self):
        canvas = self.canv
        h = self.height
        w = self.width

        # Dark navy background
        canvas.setFillColor(_hex(C_BANNER))
        canvas.rect(0, 0, w, h, fill=1, stroke=0)

        # Thin brand accent bar at top
        canvas.setFillColor(_hex(C_BRAND))
        canvas.rect(0, h - 2.5, w, 2.5, fill=1, stroke=0)

        # Title (left)
        canvas.setFont(FONT_BOLD, FONT_SIZE_BANNER_TITLE_SUMMARY)
        canvas.setFillColor(_hex(C_WHITE))
        canvas.drawString(
            8, h - BANNER_PAD_TOP - FONT_SIZE_BANNER_TITLE_SUMMARY, self.title
        )

        # Subtitle (left)
        canvas.setFont(FONT_NAME, FONT_SIZE_BANNER_SUB_SUMMARY)
        canvas.setFillColor(_hex(C_DATE_LABEL))
        canvas.drawString(
            8,
            h
            - BANNER_PAD_TOP
            - FONT_SIZE_BANNER_TITLE_SUMMARY
            - FONT_SIZE_BANNER_SUB_SUMMARY
            - 1,
            self.subtitle,
        )

        # Right-aligned title
        if self.right_title:
            canvas.setFont(FONT_BOLD, FONT_SIZE_BANNER_TITLE)
            canvas.setFillColor(_hex(self.right_title_color))
            canvas.drawRightString(
                w - 8, h - BANNER_PAD_TOP - FONT_SIZE_BANNER_TITLE, self.right_title
            )

        # Right-aligned subtitle
        if self.right_subtitle:
            canvas.setFont(FONT_NAME, FONT_SIZE_BANNER_SUB)
            canvas.setFillColor(_hex(C_WHITE))
            canvas.drawRightString(
                w - 8,
                h - BANNER_PAD_TOP - FONT_SIZE_BANNER_TITLE - FONT_SIZE_BANNER_SUB - 1,
                self.right_subtitle,
            )


class _SectionLabelFlowable(Flowable):
    """Full-width section label with a left accent bar."""

    def __init__(self, width: float, text: str, color: str = C_BRAND):
        Flowable.__init__(self)
        self.fwidth = width
        self.text = text
        self.color = color
        self.height = FONT_SIZE_SECTION_LABEL + 6

    def wrap(self, availWidth, availHeight):
        return (self.fwidth, self.height)

    def draw(self):
        canvas = self.canv
        h = self.height
        w = self.fwidth
        # Light tinted background
        canvas.setFillColor(_hex(self.color + "18"))
        canvas.rect(0, 0, w, h, fill=1, stroke=0)
        # Left accent bar
        canvas.setFillColor(_hex(self.color))
        canvas.rect(0, 0, 5, h, fill=1, stroke=0)
        # Label text
        canvas.setFont(FONT_BOLD, FONT_SIZE_SECTION_LABEL)
        canvas.setFillColor(_hex(self.color))
        canvas.drawString(10, 2, self.text)


class _EmptyDataFlowable(Flowable):
    """Centered muted text for empty data states."""

    def __init__(self, width: float, text: str, color: str = C_MUTED):
        Flowable.__init__(self)
        self.fwidth = width
        self.text = text
        self.color = color
        self.height = 24

    def wrap(self, availWidth, availHeight):
        return (self.fwidth, self.height)

    def draw(self):
        canvas = self.canv
        canvas.setFont(FONT_NAME, FONT_SIZE_ROW)
        canvas.setFillColor(_hex(self.color))
        canvas.drawCentredString(self.fwidth / 2, 6, self.text)


class _SubsectionLabelFlowable(Flowable):
    """Bold colored label for sub-sections (Monthly, Weekly)."""

    def __init__(self, width: float, text: str, color: str = C_BRAND):
        Flowable.__init__(self)
        self.fwidth = width
        self.text = text
        self.color = color
        self.height = FONT_SIZE_ROW + 4

    def wrap(self, availWidth, availHeight):
        return (self.fwidth, self.height)

    def draw(self):
        canvas = self.canv
        canvas.setFont(FONT_BOLD, FONT_SIZE_ROW)
        canvas.setFillColor(_hex(self.color))
        canvas.drawString(6, 2, self.text)


# ═══════════════════════════════════════════════════════════════════════════
# Table building helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_table_style(
    data_len: int,
    col_count: int,
    *,
    header_bg: str = C_HEADER,
    alt_rows: bool = True,
    highlight_last: bool = False,
    highlight_last_bg: str = C_BANNER,
    highlight_last_color: str = C_WHITE,
    row_style_overrides: Optional[List[Tuple]] = None,
) -> TableStyle:
    """Build a TableStyle with standard formatting applied row-by-row."""
    cmds = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), _hex(header_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), _hex(C_BRAND)),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_HEADER),
        # General alignment
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), ROW_PAD_TOP),
        ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PAD_BOTTOM),
        ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD_LEFT),
        ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD_RIGHT),
        # Font
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_ROW),
        # Text color
        ("TEXTCOLOR", (0, 1), (-1, -1), _hex(C_SLATE)),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
        ("LINEBELOW", (0, 0), (-1, 0), 1, _hex(C_BRAND)),
    ]

    if alt_rows:
        for i in range(1, data_len + 1):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), _hex(C_BAND)))

    if highlight_last and data_len > 0:
        last_row = data_len
        cmds.extend(
            [
                ("BACKGROUND", (0, last_row), (-1, last_row), _hex(highlight_last_bg)),
                (
                    "TEXTCOLOR",
                    (0, last_row),
                    (-1, last_row),
                    _hex(highlight_last_color),
                ),
                ("FONTNAME", (0, last_row), (-1, last_row), FONT_BOLD),
            ]
        )

    if row_style_overrides:
        cmds.extend(row_style_overrides)

    return TableStyle(cmds)


def _row_style_override(
    row_idx: int,
    col_start: int,
    col_end: int,
    text_color: Optional[str] = None,
    bold: bool = False,
    bg_color: Optional[str] = None,
) -> List[tuple]:
    """Return TableStyle command tuples for a specific row range."""
    overrides = []
    if bg_color:
        overrides.append(
            ("BACKGROUND", (col_start, row_idx), (col_end, row_idx), _hex(bg_color))
        )
    if text_color:
        overrides.append(
            ("TEXTCOLOR", (col_start, row_idx), (col_end, row_idx), _hex(text_color))
        )
    if bold:
        overrides.append(
            ("FONTNAME", (col_start, row_idx), (col_end, row_idx), FONT_BOLD)
        )
    return overrides


# ── Short outlet name helper ─────────────────────────────────────────────────


def _short_outlet_name(name: str, max_len: int = 18) -> str:
    name = (name or "").strip()
    for prefix in ("Boteco - ", "Boteco-", "Boteco "):
        if name.lower().startswith(prefix.lower()):
            name = name[len(prefix) :].strip()
            break
    return name if len(name) <= max_len else name[: max_len - 1] + "\u2026"


def _section_key_slug(value: str, default: str = "outlet") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    slug = slug.strip("_")
    if not slug:
        slug = default
    return slug[:22]


def _outlet_col_widths_pt(
    n_outlets: int, total_w: float, label_frac: float = 0.24
) -> List[float]:
    """Column widths in points for [Label, Outlet1, ..., OutletN, Combined]."""
    if n_outlets <= 1:
        return [total_w * label_frac, total_w * (1 - label_frac)]
    data_cols = n_outlets + 1
    data_w = (total_w * (1 - label_frac)) / data_cols
    return [total_w * label_frac] + [data_w] * data_cols


def _fmt_cell(v, fmt: str = "currency") -> str:
    if fmt == "currency":
        return _r(v)
    elif fmt == "int":
        return f"{int(v or 0):,}"
    elif fmt == "float1":
        return f"{float(v or 0):.0f}"
    elif fmt == "pct":
        return _pct(v)
    elif fmt == "str":
        return str(v or "\u2014")
    return str(v)


# ═══════════════════════════════════════════════════════════════════════════
# Section builders — each returns a list of Flowables
# ═══════════════════════════════════════════════════════════════════════════


def _build_sales_summary(
    r: Dict,
    location_name: str,
    n_outlets: int = 1,
    per_outlet: Optional[List[Tuple[str, Dict]]] = None,
    daily_sales_history: Optional[List[Dict]] = None,
) -> list:
    multi = per_outlet and len(per_outlet) >= 2
    if multi:
        n_outlets = len(per_outlet)

    avail_w = SECTION_WIDTHS.get(n_outlets, min(864, 720 + (n_outlets - 2) * 72))
    col_w = _outlet_col_widths_pt(n_outlets if multi else 1, avail_w - 2 * PAGE_PAD)

    iso = str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    day_lbl = _sheet_date_label(iso)
    pct_tgt = float(r.get("pct_target") or 0)
    statuses = compute_metric_statuses(r, daily_sales_history=daily_sales_history)
    ach_color = statuses["target"]["color"]

    elements = []

    elements.append(
        _BannerFlowable(
            avail_w,
            title=f"{location_name.upper()}  \u2014  END OF DAY REPORT",
            subtitle=day_lbl,
            right_title=f"{pct_tgt:.0f}% of target",
            right_subtitle=_r(r.get("net_total", 0)) + " net",
            right_title_color=ach_color,
        )
    )

    elements.append(Spacer(1, GAP_BELOW_BANNER))

    # Build table data
    headers = (
        ["", ""]
        if not multi
        else (
            [""] + [_short_outlet_name(nm, 16) for nm, _ in per_outlet] + ["Combined"]
        )
    )

    rows = [headers]
    row_idx = 0
    overrides = []

    def add_row(
        label,
        key_or_fn,
        fmt="currency",
        bold=False,
        bg=None,
        text_color=None,
        right_color=None,
        section_label=None,
    ):
        nonlocal row_idx
        if section_label:
            elements.append(_SectionLabelFlowable(avail_w, section_label))
            row_idx = 0
            return section_label

        if callable(key_or_fn):
            combined_val = key_or_fn(r)
            outlet_vals = [key_or_fn(od) for _, od in per_outlet] if multi else []
        else:
            combined_val = r.get(key_or_fn, 0)
            outlet_vals = (
                [od.get(key_or_fn, 0) for _, od in per_outlet] if multi else []
            )

        if multi:
            cells = (
                [label]
                + [_fmt_cell(v, fmt) for v in outlet_vals]
                + [_fmt_cell(combined_val, fmt)]
            )
        else:
            cells = [label, _fmt_cell(combined_val, fmt)]

        rows.append(cells)

        ri = len(rows) - 1
        override_list = []
        if bold:
            override_list.append(("FONTNAME", (0, ri), (-1, ri), FONT_BOLD))
        if bg:
            override_list.append(("BACKGROUND", (0, ri), (-1, ri), _hex(bg)))
        elif row_idx % 2 == 1:
            override_list.append(("BACKGROUND", (0, ri), (-1, ri), _hex(C_BAND)))
        if text_color:
            override_list.append(("TEXTCOLOR", (0, ri), (-1, ri), _hex(text_color)))
        if right_color:
            override_list.append(("TEXTCOLOR", (1, ri), (-1, ri), _hex(right_color)))

        # Per-cell conditional coloring (discount = red, target color, etc.)
        if key_or_fn == "discount" and not section_label:
            pass  # right_color handles this
        if fmt == "pct" and key_or_fn == "pct_target":
            override_list.append(("TEXTCOLOR", (1, ri), (1, ri), _hex(ach_color)))

        overrides.extend(override_list)
        row_idx += 1
        return section_label

    add_row("Covers", "covers", fmt="int")
    add_row("Turns", "turns", fmt="float1")

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
            add_row(lbl, key)

    add_row("EOD Gross Total", "gross_total", bold=True, bg=C_BAND)

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
            add_row(lbl, key, right_color=disc_color)

    add_row(
        "EOD Net Total",
        "net_total",
        bold=True,
        bg=C_BANNER if not multi else C_BAND,
        text_color=C_WHITE if not multi else C_SLATE,
        right_color=C_WHITE if not multi else None,
    )

    elements.append(Spacer(1, GAP_ABOVE_SECTION_LABEL))
    elements.append(_SectionLabelFlowable(avail_w, "MTD Sales"))
    row_idx = 0
    mtd_rows = (
        [["", ""]]
        if not multi
        else (
            [""] + [_short_outlet_name(nm, 16) for nm, _ in per_outlet] + ["Combined"]
        )
    )
    mtd_data = [mtd_rows]
    mtd_overrides = []
    mri = 0

    def add_mtd_row(label, key_or_fn, fmt="currency", bold=False, right_color=None):
        nonlocal mri
        if callable(key_or_fn):
            combined_val = key_or_fn(r)
            outlet_vals = [key_or_fn(od) for _, od in per_outlet] if multi else []
        else:
            combined_val = r.get(key_or_fn, 0)
            outlet_vals = (
                [od.get(key_or_fn, 0) for _, od in per_outlet] if multi else []
            )

        if multi:
            cells = (
                [label]
                + [_fmt_cell(v, fmt) for v in outlet_vals]
                + [_fmt_cell(combined_val, fmt)]
            )
        else:
            cells = [label, _fmt_cell(combined_val, fmt)]

        mtd_data.append(cells)
        ri = len(mtd_data) - 1
        ov = []
        if bold:
            ov.append(("FONTNAME", (0, ri), (-1, ri), FONT_BOLD))
        if mri % 2 == 1:
            ov.append(("BACKGROUND", (0, ri), (-1, ri), _hex(C_BAND)))
        if right_color:
            ov.append(("TEXTCOLOR", (1, ri), (-1, ri), _hex(right_color)))
        mtd_overrides.extend(ov)
        mri += 1

    add_mtd_row("MTD Total Covers", "mtd_total_covers", fmt="int", bold=True)
    add_mtd_row(
        "APC (Day)", "apc", fmt="currency", right_color=statuses["apc"]["color"]
    )

    def _apc_month(d):
        mtd_net = float(d.get("mtd_net_sales") or 0)
        mtd_cov = int(d.get("mtd_total_covers") or 0)
        return mtd_net / mtd_cov if mtd_cov > 0 else 0.0

    add_mtd_row("APC (Month)", _apc_month, fmt="currency")
    add_mtd_row("Complimentary", "complimentary", fmt="currency")
    add_mtd_row("MTD Complimentary", "mtd_complimentary", fmt="currency")
    add_mtd_row("Daily Avg. Net Sales", "mtd_avg_daily", fmt="currency")
    add_mtd_row("MTD Net Sales", "mtd_net_sales", fmt="currency", bold=True)
    add_mtd_row(
        "MTD Discount",
        "mtd_discount",
        fmt="currency",
        right_color=statuses["discount"]["color"],
    )

    def _mtd_net_excl(d):
        return float(d.get("mtd_net_sales") or 0) - float(d.get("mtd_discount") or 0)

    add_mtd_row("MTD Net (Excl. Disc.)", _mtd_net_excl, fmt="currency", bold=True)
    add_mtd_row("Sales Target", "mtd_target", fmt="currency")
    add_mtd_row(
        "% of Target", "mtd_pct_target", fmt="pct", bold=True, right_color=ach_color
    )

    def _forecast_end(d):
        return compute_forecast_metrics(d)["forecast_month_end_sales"]

    add_mtd_row("Forecast Month-End", _forecast_end)

    def _forecast_target_pct(d):
        val = compute_forecast_metrics(d)["forecast_target_pct"]
        return _pct(val) if val is not None else "N/A"

    add_mtd_row(
        "Forecast vs Target",
        _forecast_target_pct,
        fmt="str",
        right_color=statuses["forecast"]["color"],
    )

    def _required_run_rate(d):
        val = compute_forecast_metrics(d)["required_daily_run_rate"]
        return _r(val) if val is not None else "N/A"

    add_mtd_row("Required Daily Run Rate", _required_run_rate, fmt="str")

    # Build the sales summary table
    all_data = rows[1:]  # skip header for main section
    full_data = rows + mtd_data[1:]  # combine
    n_header = len(rows)
    n_mtd = len(mtd_data) - 1

    # Add section label row for MTD
    all_rows = list(rows)
    all_rows.append(["MTD Sales", ""])
    all_rows.extend(mtd_data[1:])

    tbl = Table(all_rows, colWidths=col_w)

    # Build comprehensive table style
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _hex(C_HEADER)),
        ("TEXTCOLOR", (0, 0), (-1, 0), _hex(C_BRAND)),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_HEADER),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), ROW_PAD_TOP),
        ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PAD_BOTTOM),
        ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD_LEFT),
        ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD_RIGHT),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_ROW),
        ("TEXTCOLOR", (0, 1), (-1, -1), _hex(C_SLATE)),
        ("GRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
        ("LINEBELOW", (0, 0), (-1, 0), 1, _hex(C_BRAND)),
    ]

    # Alternating rows
    for i in range(1, len(all_rows)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _hex(C_BAND)))

    # Net Total row highlight (row before MTD section label)
    net_total_row = n_header - 1
    style_cmds.extend(
        [
            ("BACKGROUND", (0, net_total_row), (-1, net_total_row), _hex(C_BANNER)),
            ("TEXTCOLOR", (0, net_total_row), (-1, net_total_row), _hex(C_WHITE)),
            ("FONTNAME", (0, net_total_row), (-1, net_total_row), FONT_BOLD),
        ]
    )

    # EOD Gross Total row highlight
    gross_row_idx = None
    for i, row in enumerate(all_rows):
        if row and row[0] == "EOD Gross Total":
            gross_row_idx = i
            break
    if gross_row_idx:
        style_cmds.extend(
            [
                ("BACKGROUND", (0, gross_row_idx), (-1, gross_row_idx), _hex(C_BAND)),
                ("FONTNAME", (0, gross_row_idx), (-1, gross_row_idx), FONT_BOLD),
            ]
        )

    # Discount row - red text
    for i, row in enumerate(all_rows):
        if row and row[0] in ("Discount", "MTD Discount"):
            style_cmds.append(("TEXTCOLOR", (1, i), (-1, i), _hex(C_RED)))

    # MTD section label row
    mtd_label_row = n_header
    style_cmds.extend(
        [
            (
                "BACKGROUND",
                (0, mtd_label_row),
                (-1, mtd_label_row),
                _hex(C_BRAND + "18"),
            ),
            ("TEXTCOLOR", (0, mtd_label_row), (-1, mtd_label_row), _hex(C_BRAND)),
            ("FONTNAME", (0, mtd_label_row), (-1, mtd_label_row), FONT_BOLD),
            ("SPAN", (0, mtd_label_row), (-1, mtd_label_row)),
            ("ALIGN", (0, mtd_label_row), (-1, mtd_label_row), "LEFT"),
        ]
    )

    # MTD rows: bold for specific ones
    for i, row in enumerate(all_rows):
        if row and row[0] in (
            "MTD Total Covers",
            "MTD Net Sales",
            "MTD Net (Excl. Disc.)",
            "% of Target",
        ):
            style_cmds.append(("FONTNAME", (0, i), (-1, i), FONT_BOLD))

    # APC day color
    for i, row in enumerate(all_rows):
        if row and row[0] == "APC (Day)":
            style_cmds.append(
                ("TEXTCOLOR", (1, i), (-1, i), _hex(statuses["apc"]["color"]))
            )
        if row and row[0] == "% of Target":
            style_cmds.append(("TEXTCOLOR", (1, i), (-1, i), _hex(ach_color)))
        if row and row[0] == "Forecast vs Target":
            style_cmds.append(
                ("TEXTCOLOR", (1, i), (-1, i), _hex(statuses["forecast"]["color"]))
            )

    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)
    return elements


def _build_category(
    r: Dict,
    location_name: str,
    mtd_category: Dict[str, float],
    day_lbl: str,
    n_outlets: int = 1,
    per_outlet: Optional[List[Tuple[str, Dict]]] = None,
    per_outlet_category: Optional[List[Tuple[str, Dict[str, float]]]] = None,
) -> list:
    multi = per_outlet and len(per_outlet) >= 2
    if multi:
        n_outlets = len(per_outlet)

    avail_w = SECTION_WIDTHS.get(n_outlets, min(864, 720 + (n_outlets - 2) * 72))

    std_cats = ["Food", "Liquor", "Beer", "Soft Beverages", "Coffee", "Tobacco"]
    daily_cat = _collapse_super_category_amounts(r.get("categories") or [])
    mtd_category = _collapse_super_category_totals(dict(mtd_category or {}))
    total_cat_mtd = sum(mtd_category.values()) or 1.0

    outlet_daily_cats = []
    if multi and per_outlet:
        for _, od in per_outlet:
            outlet_daily_cats.append(
                _collapse_super_category_amounts(od.get("categories") or [])
            )

    cat_order = [x for x in std_cats if x in daily_cat or x in mtd_category]
    for k in sorted(mtd_category.keys()):
        if k not in cat_order:
            cat_order.append(k)

    if multi:
        n_data = len(per_outlet) + 1
        label_w = avail_w * 0.19
        mtd_w = avail_w * 0.14
        pct_w = avail_w * 0.07
        remaining = avail_w - label_w - mtd_w - pct_w - 2 * PAGE_PAD
        data_w = remaining / n_data
        col_w = [label_w] + [data_w] * n_data + [mtd_w, pct_w]
    else:
        col_w = [avail_w * 0.44, avail_w * 0.22, avail_w * 0.22, avail_w * 0.06]

    elements = []
    elements.append(
        _BannerFlowable(
            avail_w,
            title=f"Category Sales \u2014 {location_name[:28]}",
            subtitle=day_lbl,
        )
    )
    elements.append(Spacer(1, GAP_BELOW_BANNER))

    headers = (
        ["Category", "Daily", "MTD", "%"]
        if not multi
        else (
            ["Category"]
            + [
                _short_outlet_name(nm, 8 if len(per_outlet) > 2 else 10)
                for nm, _ in per_outlet
            ]
            + ["Comb.", "MTD", "%"]
        )
    )

    rows = [headers]
    daily_total = 0.0
    mtd_total = 0.0
    outlet_totals = [0.0] * len(outlet_daily_cats) if multi else []

    for idx, name in enumerate(cat_order):
        d_amt = daily_cat.get(name, 0.0)
        m_amt = float(mtd_category.get(name, 0) or 0)
        daily_total += d_amt
        mtd_total += m_amt
        pct_lbl = (
            f"{int(round(100 * m_amt / total_cat_mtd))}%"
            if total_cat_mtd > 0
            else "\u2014"
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
        rows.append(cells)

    # Totals row
    if multi:
        tot_cells = (
            ["Total"]
            + [_r(t) for t in outlet_totals]
            + [_r(daily_total), _r(mtd_total), ""]
        )
    else:
        tot_cells = ["Total", _r(daily_total), _r(mtd_total), ""]
    rows.append(tot_cells)

    tbl = Table(rows, colWidths=col_w)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _hex(C_HEADER)),
        ("TEXTCOLOR", (0, 0), (-1, 0), _hex(C_BRAND)),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_HEADER),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), ROW_PAD_TOP),
        ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PAD_BOTTOM),
        ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD_LEFT),
        ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD_RIGHT),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_ROW),
        ("TEXTCOLOR", (0, 1), (-1, -1), _hex(C_SLATE)),
        ("GRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
        ("LINEBELOW", (0, 0), (-1, 0), 1, _hex(C_BRAND)),
        # Totals row
        ("BACKGROUND", (0, -1), (-1, -1), _hex(C_BANNER)),
        ("TEXTCOLOR", (0, -1), (-1, -1), _hex(C_WHITE)),
        ("FONTNAME", (0, -1), (-1, -1), FONT_BOLD),
    ]
    for i in range(1, len(rows) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _hex(C_BAND)))

    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)
    return elements


def _build_service(
    r: Dict,
    location_name: str,
    mtd_service: Dict[str, float],
    day_lbl: str,
    n_outlets: int = 1,
    per_outlet: Optional[List[Tuple[str, Dict]]] = None,
    per_outlet_service: Optional[List[Tuple[str, Dict[str, float]]]] = None,
) -> list:
    multi = per_outlet and len(per_outlet) >= 2
    if multi:
        n_outlets = len(per_outlet)

    avail_w = SECTION_WIDTHS.get(n_outlets, min(864, 720 + (n_outlets - 2) * 72))
    std_svc = ["Breakfast", "Lunch", "Dinner", "Delivery", "Events", "Party"]

    daily_svc = {
        s.get("service_type") or s.get("type"): float(s.get("amount") or 0)
        for s in r.get("services") or []
    }
    mtd_service = dict(mtd_service or {})
    total_svc_mtd = sum(mtd_service.values()) or 1.0

    outlet_daily_svcs = []
    if multi and per_outlet:
        for _, od in per_outlet:
            outlet_daily_svcs.append(
                {
                    s.get("service_type") or s.get("type"): float(s.get("amount") or 0)
                    for s in od.get("services") or []
                }
            )

    svc_order = [x for x in std_svc if x in daily_svc or x in mtd_service]
    for k in sorted(mtd_service.keys()):
        if k not in svc_order:
            svc_order.append(k)

    if multi:
        n_data = len(per_outlet) + 1
        label_w = avail_w * 0.19
        mtd_w = avail_w * 0.14
        pct_w = avail_w * 0.07
        remaining = avail_w - label_w - mtd_w - pct_w - 2 * PAGE_PAD
        data_w = remaining / n_data
        col_w = [label_w] + [data_w] * n_data + [mtd_w, pct_w]
    else:
        col_w = [avail_w * 0.44, avail_w * 0.22, avail_w * 0.22, avail_w * 0.06]

    elements = []
    elements.append(
        _BannerFlowable(
            avail_w,
            title=f"Service Sales \u2014 {location_name[:28]}",
            subtitle=day_lbl,
        )
    )
    elements.append(Spacer(1, GAP_BELOW_BANNER))

    if not svc_order:
        elements.append(_EmptyDataFlowable(avail_w, "No service data for this date"))
        return elements

    headers = (
        ["Service", "Daily", "MTD", "%"]
        if not multi
        else (
            ["Service"]
            + [
                _short_outlet_name(nm, 8 if len(per_outlet) > 2 else 10)
                for nm, _ in per_outlet
            ]
            + ["Comb.", "MTD", "%"]
        )
    )

    rows = [headers]
    daily_total = 0.0
    mtd_total = 0.0
    outlet_totals = [0.0] * len(outlet_daily_svcs) if multi else []

    for idx, name in enumerate(svc_order):
        d_amt = daily_svc.get(name, 0.0)
        m_amt = float(mtd_service.get(name, 0) or 0)
        daily_total += d_amt
        mtd_total += m_amt
        pct_lbl = (
            f"{int(round(100 * m_amt / total_svc_mtd))}%"
            if total_svc_mtd > 0
            else "\u2014"
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
        rows.append(cells)

    if multi:
        tot_cells = (
            ["Total"]
            + [_r(t) for t in outlet_totals]
            + [_r(daily_total), _r(mtd_total), ""]
        )
    else:
        tot_cells = ["Total", _r(daily_total), _r(mtd_total), ""]
    rows.append(tot_cells)

    tbl = Table(rows, colWidths=col_w)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _hex(C_HEADER)),
        ("TEXTCOLOR", (0, 0), (-1, 0), _hex(C_BRAND)),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_HEADER),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), ROW_PAD_TOP),
        ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PAD_BOTTOM),
        ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD_LEFT),
        ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD_RIGHT),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_ROW),
        ("TEXTCOLOR", (0, 1), (-1, -1), _hex(C_SLATE)),
        ("GRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
        ("LINEBELOW", (0, 0), (-1, 0), 1, _hex(C_BRAND)),
        ("BACKGROUND", (0, -1), (-1, -1), _hex(C_BANNER)),
        ("TEXTCOLOR", (0, -1), (-1, -1), _hex(C_WHITE)),
        ("FONTNAME", (0, -1), (-1, -1), FONT_BOLD),
    ]
    for i in range(1, len(rows) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _hex(C_BAND)))

    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)
    return elements


def _build_footfall(
    month_footfall_rows: List[Dict], location_name: str, n_outlets: int = 1
) -> list:
    rows_data = list(month_footfall_rows or [])
    avail_w = SECTION_WIDTHS.get(n_outlets, min(864, 720 + (n_outlets - 2) * 72))

    elements = []
    elements.append(
        _BannerFlowable(
            avail_w,
            title="Daily Footfall \u2014 Month to Date",
            subtitle=location_name[:32],
        )
    )
    elements.append(Spacer(1, GAP_BELOW_BANNER))

    col_w = [avail_w * 0.40, avail_w * 0.16, avail_w * 0.16, avail_w * 0.16]

    if not rows_data:
        elements.append(_EmptyDataFlowable(avail_w, "No footfall data for this month"))
        return elements

    headers = ["Date", "Dinner", "Lunch", "Total"]
    table_rows = [headers]

    tot_din = tot_lun = tot_cov = 0
    for row in rows_data:
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
        table_rows.append(
            [
                _sheet_date_label(ds),
                str(di) if di else "\u2014",
                str(lu) if lu else "\u2014",
                str(tot),
            ]
        )

    # Totals row
    table_rows.append(["TOTAL", str(tot_din), str(tot_lun), str(tot_cov)])

    # Average row
    n = len(rows_data)
    if n > 0:
        avg_din = tot_din / n
        avg_lun = tot_lun / n
        avg_cov = tot_cov / n
        table_rows.append(
            [
                f"Avg / day ({n} days)",
                f"{avg_din:.0f}",
                f"{avg_lun:.0f}",
                f"{avg_cov:.0f}",
            ]
        )

    tbl = Table(table_rows, colWidths=col_w)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _hex(C_HEADER)),
        ("TEXTCOLOR", (0, 0), (-1, 0), _hex(C_BRAND)),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_HEADER),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), ROW_PAD_TOP),
        ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PAD_BOTTOM),
        ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD_LEFT),
        ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD_RIGHT),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_ROW),
        ("TEXTCOLOR", (0, 1), (-1, -1), _hex(C_SLATE)),
        ("GRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
        ("LINEBELOW", (0, 0), (-1, 0), 1, _hex(C_BRAND)),
        # Total row
        (
            "BACKGROUND",
            (0, -2) if n > 0 else (0, -1),
            (-1, -2) if n > 0 else (-1, -1),
            _hex(C_BANNER),
        ),
        (
            "TEXTCOLOR",
            (0, -2) if n > 0 else (0, -1),
            (-1, -2) if n > 0 else (-1, -1),
            _hex(C_WHITE),
        ),
        (
            "FONTNAME",
            (0, -2) if n > 0 else (0, -1),
            (-1, -2) if n > 0 else (-1, -1),
            FONT_BOLD,
        ),
    ]
    for i in range(1, len(table_rows) - (2 if n > 0 else 1)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _hex(C_BAND)))

    # Average row styling
    if n > 0:
        style_cmds.extend(
            [
                ("BACKGROUND", (0, -1), (-1, -1), _hex(C_BAND)),
                ("TEXTCOLOR", (0, -1), (-1, -1), _hex(C_MUTED)),
            ]
        )

    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)
    return elements


def _build_footfall_metrics(
    monthly_rows: Optional[List[Dict]],
    weekly_rows: Optional[List[Dict]],
    location_name: str,
    n_outlets: int = 1,
) -> list:
    monthly = list(monthly_rows or [])
    weekly = list(weekly_rows or [])
    avail_w = SECTION_WIDTHS.get(n_outlets, min(864, 720 + (n_outlets - 2) * 72))

    elements = []
    elements.append(
        _BannerFlowable(
            avail_w,
            title="Footfall Metrics",
            subtitle=location_name[:32],
        )
    )
    elements.append(Spacer(1, GAP_BELOW_BANNER))

    def _calc_pct_change(current: float, previous: float) -> str:
        if previous == 0:
            return "\u2014"
        pct = ((current - previous) / previous) * 100
        return f"{pct:+.2f}%"

    def _calc_avg_pct_change(
        curr_foot: int, curr_days: int, prev_foot: int, prev_days: int
    ) -> str:
        if prev_days == 0 or prev_foot == 0:
            return "\u2014"
        curr_avg = curr_foot / curr_days
        prev_avg = prev_foot / prev_days
        pct = ((curr_avg - prev_avg) / prev_avg) * 100
        return f"{pct:+.2f}%"

    col_w = [
        avail_w * 0.20,
        avail_w * 0.15,
        avail_w * 0.16,
        avail_w * 0.14,
        avail_w * 0.16,
        avail_w * 0.17,
    ]

    if monthly:
        elements.append(_SubsectionLabelFlowable(avail_w, "Monthly"))
        headers = [
            "Month",
            "Footfall",
            "% Change",
            "Total Days",
            "Daily Avg.",
            "% Change",
        ]

        sorted_monthly = sorted(monthly, key=lambda x: x.get("month", ""), reverse=True)

        # Precompute best/worst
        monthly_covers = []
        monthly_daily_avgs = []
        for row in sorted_monthly[:9]:
            covers = int(row.get("covers") or 0)
            total_days = int(row.get("total_days") or 0)
            daily_avg = covers / total_days if total_days > 0 else 0
            monthly_covers.append(covers)
            monthly_daily_avgs.append(daily_avg)

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

        table_rows = [headers]
        for idx, row in enumerate(sorted_monthly[:9]):
            month = str(row.get("month", ""))
            covers = int(row.get("covers") or 0)
            total_days = int(row.get("total_days") or 0)
            daily_avg = covers / total_days if total_days > 0 else 0

            try:
                dt = datetime.strptime(f"{month}-01", "%Y-%m-%d")
                month_label = dt.strftime("%b-%Y")
            except ValueError:
                month_label = month

            foot_pct = "\u2014"
            avg_pct = "\u2014"
            if idx < len(sorted_monthly) - 1:
                prev_row = sorted_monthly[idx + 1]
                prev_covers = int(prev_row.get("covers") or 0)
                prev_days = int(prev_row.get("total_days") or 0)
                foot_pct = _calc_pct_change(covers, prev_covers)
                avg_pct = _calc_avg_pct_change(
                    covers, total_days, prev_covers, prev_days
                )

            table_rows.append(
                [
                    month_label,
                    f"{covers:,}",
                    foot_pct,
                    str(total_days),
                    f"{daily_avg:.0f}",
                    avg_pct,
                ]
            )

        tbl = Table(table_rows, colWidths=col_w)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), _hex(C_HEADER)),
            ("TEXTCOLOR", (0, 0), (-1, 0), _hex(C_BRAND)),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_HEADER),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), ROW_PAD_TOP),
            ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PAD_BOTTOM),
            ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD_LEFT),
            ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD_RIGHT),
            ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_ROW),
            ("TEXTCOLOR", (0, 1), (-1, -1), _hex(C_SLATE)),
            ("GRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
            ("LINEBELOW", (0, 0), (-1, 0), 1, _hex(C_BRAND)),
        ]
        for i in range(1, len(table_rows)):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), _hex(C_BAND)))

        # Best/worst highlighting
        for idx in range(len(sorted_monthly[:9])):
            ri = idx + 1
            if idx == monthly_best_idx.get("footfall"):
                style_cmds.append(("TEXTCOLOR", (1, ri), (1, ri), _hex(C_GREEN)))
            elif idx == monthly_worst_idx.get("footfall"):
                style_cmds.append(("TEXTCOLOR", (1, ri), (1, ri), _hex(C_RED)))
            if idx == monthly_best_idx.get("daily_avg"):
                style_cmds.append(("TEXTCOLOR", (4, ri), (4, ri), _hex(C_GREEN)))
            elif idx == monthly_worst_idx.get("daily_avg"):
                style_cmds.append(("TEXTCOLOR", (4, ri), (4, ri), _hex(C_RED)))

        tbl.setStyle(TableStyle(style_cmds))
        elements.append(tbl)
        elements.append(Spacer(1, GAP_ABOVE_SECTION_LABEL))

    if weekly:
        elements.append(_SubsectionLabelFlowable(avail_w, "Weekly"))
        headers = [
            "Week",
            "Footfall",
            "% Change",
            "Total Days",
            "Daily Avg.",
            "% Change",
        ]

        sorted_weekly = sorted(weekly, key=lambda x: x.get("week", ""), reverse=True)

        weekly_covers = []
        weekly_daily_avgs = []
        for row in sorted_weekly[:4]:
            covers = int(row.get("covers") or 0)
            total_days = int(row.get("total_days") or 0)
            daily_avg = covers / total_days if total_days > 0 else 0
            weekly_covers.append(covers)
            weekly_daily_avgs.append(daily_avg)

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

        table_rows = [headers]
        for idx, row in enumerate(sorted_weekly[:4]):
            week = str(row.get("week", ""))
            covers = int(row.get("covers") or 0)
            total_days = int(row.get("total_days") or 0)
            daily_avg = covers / total_days if total_days > 0 else 0

            foot_pct = "\u2014"
            avg_pct = "\u2014"
            if idx < len(sorted_weekly) - 1:
                prev_row = sorted_weekly[idx + 1]
                prev_covers = int(prev_row.get("covers") or 0)
                prev_days = int(prev_row.get("total_days") or 0)
                foot_pct = _calc_pct_change(covers, prev_covers)
                avg_pct = _calc_avg_pct_change(
                    covers, total_days, prev_covers, prev_days
                )

            table_rows.append(
                [
                    _format_week_label(week),
                    f"{covers:,}",
                    foot_pct,
                    str(total_days),
                    f"{daily_avg:.0f}",
                    avg_pct,
                ]
            )

        tbl = Table(table_rows, colWidths=col_w)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), _hex(C_HEADER)),
            ("TEXTCOLOR", (0, 0), (-1, 0), _hex(C_BRAND)),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE", (0, 0), (-1, 0), FONT_SIZE_HEADER),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), ROW_PAD_TOP),
            ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PAD_BOTTOM),
            ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD_LEFT),
            ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD_RIGHT),
            ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 1), (-1, -1), FONT_SIZE_ROW),
            ("TEXTCOLOR", (0, 1), (-1, -1), _hex(C_SLATE)),
            ("GRID", (0, 0), (-1, -1), 0.25, _hex(C_BORDER)),
            ("LINEBELOW", (0, 0), (-1, 0), 1, _hex(C_BRAND)),
        ]
        for i in range(1, len(table_rows)):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), _hex(C_BAND)))

        for idx in range(len(sorted_weekly[:4])):
            ri = idx + 1
            if idx == weekly_best_idx.get("footfall"):
                style_cmds.append(("TEXTCOLOR", (1, ri), (1, ri), _hex(C_GREEN)))
            elif idx == weekly_worst_idx.get("footfall"):
                style_cmds.append(("TEXTCOLOR", (1, ri), (1, ri), _hex(C_RED)))
            if idx == weekly_best_idx.get("daily_avg"):
                style_cmds.append(("TEXTCOLOR", (4, ri), (4, ri), _hex(C_GREEN)))
            elif idx == weekly_worst_idx.get("daily_avg"):
                style_cmds.append(("TEXTCOLOR", (4, ri), (4, ri), _hex(C_RED)))

        tbl.setStyle(TableStyle(style_cmds))
        elements.append(tbl)

    if not monthly and not weekly:
        elements.append(
            _EmptyDataFlowable(avail_w, "No footfall metrics data available")
        )

    return elements


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


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
    r = report_data
    mc = dict(mtd_category or {})
    ms = dict(mtd_service or {})
    mf = list(month_footfall_rows or [])
    per_outlet = list(per_outlet_summaries) if per_outlet_summaries else None
    per_outlet_cat = list(per_outlet_category) if per_outlet_category else None
    per_outlet_svc = list(per_outlet_service) if per_outlet_service else None
    per_outlet_ff = list(per_outlet_footfall) if per_outlet_footfall else None
    ff_metrics_mo = list(footfall_metrics_monthly) if footfall_metrics_monthly else None
    ff_metrics_wk = list(footfall_metrics_weekly) if footfall_metrics_weekly else None
    per_outlet_ff_metrics = (
        list(per_outlet_footfall_metrics) if per_outlet_footfall_metrics else None
    )

    n_outlets = len(per_outlet) if per_outlet and len(per_outlet) >= 2 else 1
    out: Dict[str, BytesIO] = {}

    # Sales summary
    elements = _build_sales_summary(
        r,
        location_name,
        n_outlets=n_outlets,
        per_outlet=per_outlet,
        daily_sales_history=daily_sales_history,
    )
    width = SECTION_WIDTHS.get(n_outlets, min(864, 720 + (n_outlets - 2) * 72))
    out["sales_summary"] = _render_elements_to_png(elements, width)

    # Category
    elements = _build_category(
        r,
        location_name,
        mc,
        _sheet_date_label(
            str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
        ),
        n_outlets=n_outlets,
        per_outlet=per_outlet,
        per_outlet_category=per_outlet_cat,
    )
    out["category"] = _render_elements_to_png(elements, width)

    # Service
    elements = _build_service(
        r,
        location_name,
        ms,
        _sheet_date_label(
            str(r.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
        ),
        n_outlets=n_outlets,
        per_outlet=per_outlet,
        per_outlet_service=per_outlet_svc,
    )
    out["service"] = _render_elements_to_png(elements, width)

    # Footfall
    if per_outlet_ff_metrics and len(per_outlet_ff_metrics) > 1:
        for idx, (outlet_name, mo_rows, wk_rows) in enumerate(per_outlet_ff_metrics):
            elements = _build_footfall_metrics(
                mo_rows, wk_rows, outlet_name, n_outlets=n_outlets
            )
            outlet_slug = _section_key_slug(outlet_name, default=f"outlet_{idx}")
            out[f"footfall_metrics__{outlet_slug}_{idx}"] = _render_elements_to_png(
                elements, width
            )
    elif ff_metrics_mo or ff_metrics_wk:
        elements = _build_footfall_metrics(
            ff_metrics_mo, ff_metrics_wk, location_name, n_outlets=n_outlets
        )
        out["footfall_metrics"] = _render_elements_to_png(elements, width)
    elif per_outlet_ff and len(per_outlet_ff) > 1:
        for idx, (outlet_name, ff_rows) in enumerate(per_outlet_ff):
            ff_rows = list(ff_rows or [])
            elements = _build_footfall(ff_rows, outlet_name, n_outlets=n_outlets)
            outlet_slug = _section_key_slug(outlet_name, default=f"outlet_{idx}")
            out[f"footfall__{outlet_slug}_{idx}"] = _render_elements_to_png(
                elements, width
            )
    else:
        elements = _build_footfall(mf, location_name, n_outlets=n_outlets)
        out["footfall"] = _render_elements_to_png(elements, width)

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
    return generate_sheet_style_report_image(
        report_data,
        location_name,
        mtd_category={},
        mtd_service={},
        month_footfall_rows=[],
    )


# ── WhatsApp text ───────────────────────────────────────────────────────────


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
        return f"{val / net_total * 100:.0f}%" if net_total > 0 else "\u2014"

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
