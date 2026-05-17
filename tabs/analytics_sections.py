"""Section render helpers for analytics tab."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import database
import scope
import ui_theme
import utils
from components import KpiMetric, kpi_row
from tabs.analytics_logic import (
    build_daily_view_table,
    build_zomato_economics,
    classify_platform_cost_coverage,
)
from tabs.chart_builders import _hex_to_rgba, _period_supports_trend_analysis
from tabs.forecasting import (
    build_forecast_explanation,
    calculate_forecast_days,
    linear_forecast,
    moving_average,
)

_WEEKEND_DAYS = {"Friday", "Saturday", "Sunday"}
_WEEKDAY_DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday"}


def _format_ratio(ratio: float | None) -> str:
    """Format a multiplier ratio for KPI display."""
    return "N/A" if ratio is None else f"{ratio:.2f}x"


def _build_action_cards(
    current_df: pd.DataFrame,
    prior_df: pd.DataFrame,
    monthly_target: float,
    forecast_total: float,
) -> list[dict[str, str]]:
    """Build ranked, explainable action cards from available signals."""
    cards: list[dict[str, str]] = []

    if current_df.empty:
        return cards

    current_sales = float(pd.to_numeric(current_df["net_total"], errors="coerce").fillna(0).sum())
    current_covers = float(pd.to_numeric(current_df["covers"], errors="coerce").fillna(0).sum())
    current_apc = current_sales / current_covers if current_covers > 0 else 0.0

    prior_sales = 0.0
    prior_covers = 0.0
    prior_apc = 0.0
    if not prior_df.empty:
        prior_sales = float(pd.to_numeric(prior_df["net_total"], errors="coerce").fillna(0).sum())
        prior_covers = float(pd.to_numeric(prior_df["covers"], errors="coerce").fillna(0).sum())
        prior_apc = prior_sales / prior_covers if prior_covers > 0 else 0.0

    if monthly_target > 0 and forecast_total > 0 and forecast_total < monthly_target:
        gap = monthly_target - forecast_total
        cards.append(
            {
                "severity": "high",
                "title": "Target at Risk",
                "reason": (
                    f"Forecast projects {utils.format_rupee_short(forecast_total)} vs "
                    f"target {utils.format_rupee_short(monthly_target)}."
                ),
                "action": "Push high-conversion bundles on peak hours and monitor daily pace.",
                "metric": f"Gap: {utils.format_rupee_short(gap)}",
            }
        )

    if prior_sales > 0:
        sales_change = ((current_sales - prior_sales) / prior_sales) * 100
        if sales_change <= -8:
            cards.append(
                {
                    "severity": "high",
                    "title": "Sales Trend Softening",
                    "reason": f"Sales are {sales_change:.1f}% below previous period.",
                    "action": (
                        "Audit low days and launch a short tactical promo for demand recovery."
                    ),
                    "metric": f"Delta: {sales_change:.1f}%",
                }
            )
        elif sales_change >= 8:
            cards.append(
                {
                    "severity": "medium",
                    "title": "Momentum Opportunity",
                    "reason": f"Sales are {sales_change:.1f}% above previous period.",
                    "action": (
                        "Protect momentum by keeping top categories in stock "
                        "and staffing peak slots."
                    ),
                    "metric": f"Delta: +{sales_change:.1f}%",
                }
            )

    if prior_covers > 0 and prior_apc > 0:
        covers_change = ((current_covers - prior_covers) / prior_covers) * 100
        apc_change = ((current_apc - prior_apc) / prior_apc) * 100
        if covers_change >= 8 and apc_change <= -8:
            cards.append(
                {
                    "severity": "high",
                    "title": "APC Under Pressure",
                    "reason": (
                        f"Covers are +{covers_change:.1f}% but APC is "
                        f"{apc_change:.1f}% vs previous period."
                    ),
                    "action": (
                        "Prioritize upsell scripts and premium pairings to recover ticket size."
                    ),
                    "metric": f"APC: {utils.format_currency(current_apc)}",
                }
            )

    if not cards:
        cards.append(
            {
                "severity": "low",
                "title": "Stable Performance",
                "reason": "No major risk signal detected from forecast and prior-period deltas.",
                "action": (
                    "Maintain current run-rate and continue monitoring weekday/category shifts."
                ),
                "metric": "Signal: Neutral",
            }
        )

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    cards = sorted(cards, key=lambda c: severity_rank.get(c["severity"], 3))
    return cards[:3]

def _safe_pct_change(current: float | None, prior: float | None) -> float | None:
    """Return percentage change, safely handling empty or zero prior values."""
    if current is None or prior is None:
        return None

    current_value = float(current or 0)
    prior_value = float(prior or 0)

    if prior_value <= 0:
        return None

    return ((current_value - prior_value) / prior_value) * 100


def _format_owner_delta(value: float | None) -> str:
    """Format percentage deltas for owner-facing readout text."""
    if value is None:
        return "N/A"
    return f"{value:+.1f}%"


def render_owner_readout_and_data_confidence(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    prior_df: pd.DataFrame,
    analysis_period: str,
    start_date: date,
    end_date: date,
    monthly_target: float,
    total_sales: float,
    total_covers: int,
    prior_total: float | None,
    prior_covers: int | None,
    analytics_loc_ids: list[int],
) -> None:
    """Render an owner-facing readout plus data confidence check."""
    if df.empty:
        return

    work_df = df.copy()

    work_df["date"] = pd.to_datetime(work_df["date"], errors="coerce")
    work_df = work_df[work_df["date"].notna()].copy()

    if work_df.empty:
        return

    work_df["net_total"] = pd.to_numeric(
        work_df["net_total"],
        errors="coerce",
    ).fillna(0)

    work_df["covers"] = pd.to_numeric(
        work_df["covers"],
        errors="coerce",
    ).fillna(0)

    if "target" in work_df.columns:
        work_df["target"] = pd.to_numeric(
            work_df["target"],
            errors="coerce",
        ).fillna(0)
    else:
        work_df["target"] = 0

    # Fallback in case prior totals were not calculated before this function call.
    if prior_total is None and not prior_df.empty and "net_total" in prior_df.columns:
        prior_total = float(
            pd.to_numeric(prior_df["net_total"], errors="coerce").fillna(0).sum()
        )

    if prior_covers is None and not prior_df.empty and "covers" in prior_df.columns:
        prior_covers = int(
            pd.to_numeric(prior_df["covers"], errors="coerce").fillna(0).sum()
        )

    selected_target = float(work_df["target"].sum())
    achievement_pct = (
        total_sales / selected_target * 100
        if selected_target > 0
        else 0
    )

    selected_target_gap = (
        selected_target - total_sales
        if selected_target > 0
        else None
    )

    current_apc = total_sales / total_covers if total_covers > 0 else 0.0

    prior_apc = None
    if (
        prior_total is not None
        and prior_covers is not None
        and prior_covers > 0
    ):
        prior_apc = prior_total / prior_covers

    sales_delta_pct = _safe_pct_change(total_sales, prior_total)
    covers_delta_pct = _safe_pct_change(total_covers, prior_covers)
    apc_delta_pct = _safe_pct_change(current_apc, prior_apc)

    selected_range_days = max(1, (end_date - start_date).days + 1)
    forecast_days = calculate_forecast_days(
        analysis_period,
        data_points=len(work_df),
        selected_range_days=selected_range_days,
    )

    forecast_total = None
    forecast_reliability = _forecast_reliability_label(len(work_df))

    if forecast_days > 0:
        forecast = linear_forecast(
            work_df["date"],
            work_df["net_total"].tolist(),
            forecast_days=forecast_days,
        )
        if forecast:
            forecast_total = total_sales + sum(float(item["value"]) for item in forecast)

    forecast_gap = None
    if monthly_target > 0 and forecast_total is not None:
        forecast_gap = monthly_target - forecast_total

    daily_recovery_required = None
    if forecast_gap is not None and forecast_gap > 0 and forecast_days > 0:
        daily_recovery_required = forecast_gap / forecast_days

    # ── Owner readout decision rules ─────────────────────────────
    severity = "info"
    title = "Performance is stable"
    diagnosis = (
        "No major risk signal is visible from sales, covers, APC, target pace "
        "and the selected comparison period."
    )
    primary_action = (
        "Maintain current operating rhythm and continue monitoring outlet, weekday and category movement."
    )
    secondary_action = (
        "Use the deep-dive layers only if a KPI starts moving materially."
    )

    if (
        covers_delta_pct is not None
        and apc_delta_pct is not None
        and covers_delta_pct >= 8
        and apc_delta_pct <= -8
    ):
        severity = "warning"
        title = "Traffic is improving, but spend per guest is falling"
        diagnosis = (
            f"Covers are {_format_owner_delta(covers_delta_pct)} vs comparison, "
            f"but APC is {_format_owner_delta(apc_delta_pct)}. "
            "Demand exists, but guests are spending less per cover."
        )
        primary_action = (
            "Push high-margin upsells, premium pairings, cocktails, desserts and sharing platters during peak hours."
        )
        secondary_action = (
            "Check the Mix layer to see whether premium categories are losing contribution."
        )

    elif sales_delta_pct is not None and sales_delta_pct <= -8:
        severity = "error"
        title = "Sales are soft versus the comparison period"
        diagnosis = (
            f"Net sales are {_format_owner_delta(sales_delta_pct)} vs comparison. "
            "This points to a demand, visibility, conversion or operating issue."
        )
        primary_action = (
            "Identify which outlet and weekdays created the drop, then run a tactical demand push."
        )
        secondary_action = (
            "Use the Drivers layer to check whether the issue is covers, APC or both."
        )

    elif apc_delta_pct is not None and apc_delta_pct <= -8:
        severity = "warning"
        title = "APC is under pressure"
        diagnosis = (
            f"APC is {_format_owner_delta(apc_delta_pct)} vs comparison. "
            "Guests are spending less per cover even if sales look stable."
        )
        primary_action = (
            "Review menu mix, server upsell behaviour and premium item availability."
        )
        secondary_action = (
            "Use Category Pareto and Weekday Summary to identify where spend quality is weakening."
        )

    elif covers_delta_pct is not None and covers_delta_pct <= -8:
        severity = "warning"
        title = "Guest count is under pressure"
        diagnosis = (
            f"Covers are {_format_owner_delta(covers_delta_pct)} vs comparison. "
            "The main issue appears to be traffic rather than ticket size."
        )
        primary_action = (
            "Check reservations, corporate bookings, aggregator visibility and local marketing for weak days."
        )
        secondary_action = (
            "Use the Covers vs APC Matrix to separate low-traffic days from low-spend days."
        )

    elif selected_target > 0 and achievement_pct < 70:
        severity = "error"
        title = "Selected period is materially behind target"
        diagnosis = (
            f"Achievement is {achievement_pct:.1f}% against the selected-period target. "
            "The business needs an immediate recovery plan."
        )
        primary_action = (
            "Focus on the strongest weekdays, high-conversion offers and premium upsell opportunities."
        )
        secondary_action = (
            "Use Daily Target Variance to identify the exact days creating the target gap."
        )

    elif selected_target > 0 and achievement_pct >= 100:
        severity = "success"
        title = "Selected period is ahead of target"
        diagnosis = (
            f"Achievement is {achievement_pct:.1f}% against the selected-period target. "
            "The priority is to protect the drivers that created this performance."
        )
        primary_action = (
            "Protect availability of top categories and keep staffing aligned to peak demand."
        )
        secondary_action = (
            "Use Mix and Drivers to identify which behaviours should be repeated."
        )

    # Forecast risk should override stable/positive readouts, but not erase stronger operational warnings.
    if forecast_gap is not None and forecast_gap > 0:
        if severity in {"info", "success"}:
            severity = "warning"
            title = "Forecast close is below monthly target"
            diagnosis = (
                f"Forecast close is {utils.format_rupee_short(forecast_total or 0)} "
                f"against a monthly target of {utils.format_rupee_short(monthly_target)}. "
                f"Projected gap is {utils.format_rupee_short(forecast_gap)}."
            )

            if daily_recovery_required is not None:
                primary_action = (
                    f"Generate roughly {utils.format_rupee_short(daily_recovery_required)} "
                    "extra sales per forecast day versus current pace."
                )
            else:
                primary_action = (
                    "Focus the next operating cycle on days and categories with the highest conversion potential."
                )

            secondary_action = (
                "Track required daily sales and review progress every 2–3 days."
            )
        else:
            diagnosis += (
                f" Forecast close is {utils.format_rupee_short(forecast_total or 0)} "
                f"against target {utils.format_rupee_short(monthly_target)}."
            )

    evidence_lines = [
        f"Net Sales: {utils.format_rupee_short(total_sales)} ({_format_owner_delta(sales_delta_pct)} vs comparison)",
        f"Covers: {int(total_covers):,} ({_format_owner_delta(covers_delta_pct)} vs comparison)",
        f"APC: {utils.format_currency(current_apc)} ({_format_owner_delta(apc_delta_pct)} vs comparison)",
    ]

    if selected_target > 0:
        evidence_lines.append(
            f"Selected Target Achievement: {achievement_pct:.1f}%"
        )

    if selected_target_gap is not None:
        if selected_target_gap > 0:
            evidence_lines.append(
                f"Selected Period Target Gap: {utils.format_rupee_short(selected_target_gap)}"
            )
        else:
            evidence_lines.append(
                f"Selected Period Target Surplus: {utils.format_rupee_short(abs(selected_target_gap))}"
            )

    if forecast_total is not None:
        evidence_lines.append(
            f"Forecast Close: {utils.format_rupee_short(forecast_total)} · Reliability: {forecast_reliability}"
        )

    if daily_recovery_required is not None:
        evidence_lines.append(
            f"Extra Sales Needed per Forecast Day: {utils.format_rupee_short(daily_recovery_required)}"
        )

    # ── Data confidence checks ───────────────────────────────────
    effective_end_date = min(end_date, date.today())

    if start_date <= effective_end_date:
        expected_dates = set(pd.date_range(start_date, effective_end_date).date)
    else:
        expected_dates = set()

    observed_dates = set(work_df["date"].dt.date.dropna())

    missing_dates = sorted(expected_dates - observed_dates)
    missing_days_count = len(missing_dates)

    zero_covers_with_sales = int(
        len(work_df[(work_df["net_total"] > 0) & (work_df["covers"] <= 0)])
    )

    zero_sales_with_covers = int(
        len(work_df[(work_df["net_total"] <= 0) & (work_df["covers"] > 0)])
    )

    missing_target_rows = int(len(work_df[work_df["target"] <= 0]))

    duplicate_raw_rows = 0
    if (
        not df_raw.empty
        and {"location_id", "date"}.issubset(set(df_raw.columns))
    ):
        duplicate_raw_rows = int(
            df_raw.duplicated(subset=["location_id", "date"]).sum()
        )

    confidence_reasons: list[str] = []

    if missing_days_count > 0:
        confidence_reasons.append(
            f"{missing_days_count} date(s) are missing from the selected window."
        )

    if zero_covers_with_sales > 0:
        confidence_reasons.append(
            f"{zero_covers_with_sales} day(s) have sales but zero covers. APC may be unreliable."
        )

    if zero_sales_with_covers > 0:
        confidence_reasons.append(
            f"{zero_sales_with_covers} day(s) have covers but zero sales. Check upload or mapping."
        )

    if missing_target_rows > 0:
        confidence_reasons.append(
            f"{missing_target_rows} row(s) have no target. Target achievement may be incomplete."
        )

    if duplicate_raw_rows > 0:
        confidence_reasons.append(
            f"{duplicate_raw_rows} duplicate outlet-date row(s) found in raw data."
        )

    missing_ratio = (
        missing_days_count / len(expected_dates)
        if expected_dates
        else 0
    )

    if (
        duplicate_raw_rows > 0
        or zero_covers_with_sales >= 2
        or missing_ratio >= 0.20
    ):
        confidence_label = "Low"
        confidence_severity = "error"
    elif confidence_reasons:
        confidence_label = "Medium"
        confidence_severity = "warning"
    else:
        confidence_label = "High"
        confidence_severity = "success"
        confidence_reasons.append(
            "Sales, covers, targets and selected dates look usable for decision-making."
        )

    with st.container(border=True):
        owner_col, confidence_col = st.columns([2, 1])

        with owner_col:
            st.markdown("### Owner Readout")

            body = (
                f"**{title}**\n\n"
                f"{diagnosis}\n\n"
                f"**Priority action:** {primary_action}\n\n"
                f"**Next check:** {secondary_action}"
            )

            if severity == "success":
                st.success(body)
            elif severity == "warning":
                st.warning(body)
            elif severity == "error":
                st.error(body)
            else:
                st.info(body)

            with st.expander("Why this readout was generated", expanded=False):
                for line in evidence_lines:
                    st.caption(line)

        with confidence_col:
            st.markdown("### Data Confidence")

            confidence_body = (
                f"**{confidence_label} confidence**\n\n"
                + "\n\n".join(f"- {reason}" for reason in confidence_reasons[:5])
            )

            if confidence_severity == "success":
                st.success(confidence_body)
            elif confidence_severity == "warning":
                st.warning(confidence_body)
            else:
                st.error(confidence_body)

            st.caption(
                f"Scope checked: {len(analytics_loc_ids)} outlet(s), "
                f"{len(expected_dates)} calendar day(s)."
            )

def _last_day_of_month(anchor_date: date) -> date:
    """Return the last calendar day of the month for a date."""
    if anchor_date.month == 12:
        return date(anchor_date.year, 12, 31)

    next_month = date(anchor_date.year, anchor_date.month + 1, 1)
    return next_month - pd.Timedelta(days=1)


def _quarter_end(anchor_date: date) -> date:
    """Return the calendar quarter-end date for a date."""
    quarter_start_month = ((anchor_date.month - 1) // 3) * 3 + 1
    quarter_end_month = quarter_start_month + 2

    if quarter_end_month == 12:
        return date(anchor_date.year, 12, 31)

    next_month = date(anchor_date.year, quarter_end_month + 1, 1)
    return next_month - pd.Timedelta(days=1)


def _remaining_day_split(
    latest_data_date: date,
    plan_end_date: date,
) -> tuple[int, int, int]:
    """Return total, weekday and weekend remaining days after latest uploaded data date."""
    if latest_data_date >= plan_end_date:
        return 0, 0, 0

    remaining_dates = pd.date_range(
        latest_data_date + pd.Timedelta(days=1),
        plan_end_date,
    )

    total_days = len(remaining_dates)
    weekend_days = int(
        sum(day.day_name() in _WEEKEND_DAYS for day in remaining_dates)
    )
    weekday_days = total_days - weekend_days

    return total_days, weekday_days, weekend_days


def render_required_sales_plan(
    df: pd.DataFrame,
    analysis_period: str,
    start_date: date,
    end_date: date,
    monthly_target: float,
    total_sales: float,
    total_covers: int,
) -> None:
    """Render target recovery plan using required sales, covers and APC."""
    if df.empty:
        return

    work_df = df.copy()

    work_df["date"] = pd.to_datetime(work_df["date"], errors="coerce")
    work_df = work_df[work_df["date"].notna()].copy()

    if work_df.empty:
        return

    work_df["net_total"] = pd.to_numeric(
        work_df["net_total"],
        errors="coerce",
    ).fillna(0)

    work_df["covers"] = pd.to_numeric(
        work_df["covers"],
        errors="coerce",
    ).fillna(0)

    if "target" in work_df.columns:
        work_df["target"] = pd.to_numeric(
            work_df["target"],
            errors="coerce",
        ).fillna(0)
    else:
        work_df["target"] = 0

    latest_data_date = work_df["date"].max().date()
    period_key = analysis_period.lower().replace(" ", "_")

    selected_target = float(work_df["target"].sum())
    selected_target_gap = selected_target - total_sales if selected_target > 0 else 0.0

    # Decide which target this plan should recover against.
    # Current open periods use full period targets; rolling/historical periods use selected-window target only.
    if period_key in {"mtd", "this_month"}:
        plan_label = "Monthly recovery plan"
        plan_target = float(monthly_target or 0)
        plan_end_date = _last_day_of_month(latest_data_date)
        plan_gap = plan_target - total_sales

    elif period_key == "qtd":
        plan_label = "Quarter recovery plan"
        plan_target = float(monthly_target or 0) * 3
        plan_end_date = _quarter_end(latest_data_date)
        plan_gap = plan_target - total_sales

    elif period_key == "ytd":
        plan_label = "Year recovery plan"
        plan_target = float(monthly_target or 0) * 12
        plan_end_date = date(latest_data_date.year, 12, 31)
        plan_gap = plan_target - total_sales

    else:
        plan_label = "Selected-period target check"
        plan_target = selected_target
        plan_end_date = end_date
        plan_gap = selected_target_gap

    days_with_sales = int(len(work_df[work_df["net_total"] > 0]))
    avg_daily_sales = total_sales / days_with_sales if days_with_sales > 0 else 0.0
    avg_daily_covers = total_covers / days_with_sales if days_with_sales > 0 else 0.0
    current_apc = total_sales / total_covers if total_covers > 0 else 0.0

    remaining_days, remaining_weekdays, remaining_weekends = _remaining_day_split(
        latest_data_date,
        plan_end_date,
    )

    with st.container(border=True):
        st.markdown("### Required Sales Plan")
        st.caption(
            "Use this to translate the target gap into daily sales, covers and APC requirements."
        )

        if plan_target <= 0:
            st.info(
                "No target is available for this period, so a recovery plan cannot be calculated."
            )
            return

        if plan_gap <= 0:
            surplus = abs(plan_gap)

            success_body = (
                f"**{plan_label}: ahead of target**\n\n"
                f"Current sales are {utils.format_rupee_short(total_sales)} "
                f"against a target of {utils.format_rupee_short(plan_target)}. "
                f"Surplus: {utils.format_rupee_short(surplus)}.\n\n"
                "**Priority:** Protect the drivers that created the surplus — category availability, staffing and service consistency."
            )

            st.success(success_body)
            return

        if remaining_days <= 0:
            st.warning(
                f"**{plan_label}: gap exists but no remaining calendar days are available in this plan window.**\n\n"
                f"Gap: {utils.format_rupee_short(plan_gap)} against target "
                f"{utils.format_rupee_short(plan_target)}. Use this as a performance review, not a recovery plan."
            )
            return

        required_daily_sales = plan_gap / remaining_days
        required_covers_at_current_apc = (
            required_daily_sales / current_apc
            if current_apc > 0
            else 0
        )
        required_apc_at_current_covers = (
            required_daily_sales / avg_daily_covers
            if avg_daily_covers > 0
            else 0
        )

        required_sales_lift_pct = (
            ((required_daily_sales - avg_daily_sales) / avg_daily_sales) * 100
            if avg_daily_sales > 0
            else None
        )

        metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)

        with metric_col_1:
            st.metric(
                "Target Gap",
                utils.format_rupee_short(plan_gap),
                help="Sales still needed to reach the selected plan target.",
            )

        with metric_col_2:
            st.metric(
                "Remaining Days",
                f"{remaining_days}",
                help="Calendar days remaining after the latest uploaded sales date.",
            )

        with metric_col_3:
            st.metric(
                "Required Daily Sales",
                utils.format_rupee_short(required_daily_sales),
                (
                    f"{required_sales_lift_pct:+.1f}% vs current run-rate"
                    if required_sales_lift_pct is not None
                    else None
                ),
            )

        with metric_col_4:
            st.metric(
                "Current APC",
                utils.format_currency(current_apc),
                help="Current selected-period net sales divided by covers.",
            )

        st.caption(
            f"Latest uploaded date: {latest_data_date.strftime('%d %b %Y')} · "
            f"Plan end date: {plan_end_date.strftime('%d %b %Y')} · "
            f"Remaining weekdays: {remaining_weekdays} · Remaining weekends: {remaining_weekends}"
        )

        scenario_rows: list[dict[str, object]] = []

        scenario_rows.append(
            {
                "Scenario": "Traffic-led recovery",
                "Required Sales / Day": utils.format_rupee_short(required_daily_sales),
                "Covers / Day": f"{required_covers_at_current_apc:,.0f}",
                "APC Needed": utils.format_currency(current_apc),
                "Interpretation": "Keep APC stable; recover mainly through more covers.",
            }
        )

        scenario_rows.append(
            {
                "Scenario": "Ticket-size recovery",
                "Required Sales / Day": utils.format_rupee_short(required_daily_sales),
                "Covers / Day": f"{avg_daily_covers:,.0f}",
                "APC Needed": utils.format_currency(required_apc_at_current_covers),
                "Interpretation": "Keep covers stable; recover mainly through APC improvement.",
            }
        )

        if avg_daily_sales > 0 and avg_daily_covers > 0 and current_apc > 0:
            lift_factor = max(required_daily_sales / avg_daily_sales, 0)

            if lift_factor > 0:
                balanced_factor = lift_factor ** 0.5
                balanced_covers = avg_daily_covers * balanced_factor
                balanced_apc = current_apc * balanced_factor

                scenario_rows.append(
                    {
                        "Scenario": "Balanced recovery",
                        "Required Sales / Day": utils.format_rupee_short(required_daily_sales),
                        "Covers / Day": f"{balanced_covers:,.0f}",
                        "APC Needed": utils.format_currency(balanced_apc),
                        "Interpretation": "Split recovery between traffic and ticket-size improvement.",
                    }
                )

        if remaining_weekends > 0:
            weekend_share = 0.60 if remaining_weekdays > 0 else 1.00
            weekday_share = 1.00 - weekend_share

            weekend_sales_per_day = (plan_gap * weekend_share) / remaining_weekends
            weekday_sales_per_day = (
                (plan_gap * weekday_share) / remaining_weekdays
                if remaining_weekdays > 0
                else 0
            )

            scenario_rows.append(
                {
                    "Scenario": "Weekend-weighted push",
                    "Required Sales / Day": (
                        f"Weekend {utils.format_rupee_short(weekend_sales_per_day)}"
                        + (
                            f" / Weekday {utils.format_rupee_short(weekday_sales_per_day)}"
                            if remaining_weekdays > 0
                            else ""
                        )
                    ),
                    "Covers / Day": "Varies",
                    "APC Needed": "Varies",
                    "Interpretation": "Recover more of the gap on Friday–Sunday when demand potential is usually higher.",
                }
            )

        st.markdown("#### Recovery Scenarios")
        st.dataframe(
            pd.DataFrame(scenario_rows),
            width="stretch",
            hide_index=True,
        )

        # Owner-facing recommendation.
        if required_sales_lift_pct is None:
            st.info(
                "No current run-rate is available, so use the scenario table as a starting estimate."
            )
        elif required_sales_lift_pct <= 10:
            st.success(
                "Recovery looks realistic if current run-rate is maintained and small improvements are made in conversion, upsell or covers."
            )
        elif required_sales_lift_pct <= 25:
            st.warning(
                "Recovery requires a meaningful lift versus current run-rate. Focus on the strongest weekdays, weekend conversion and premium item upsell."
            )
        else:
            st.error(
                "Recovery requires a large lift versus current run-rate. Treat this as a high-risk target and review whether the target, demand plan or remaining days are realistic."
            )

        with st.expander("How this plan is calculated", expanded=False):
            st.caption(
                f"- Plan target: {utils.format_rupee_short(plan_target)}"
            )
            st.caption(
                f"- Current sales: {utils.format_rupee_short(total_sales)}"
            )
            st.caption(
                f"- Gap: {utils.format_rupee_short(plan_gap)}"
            )
            st.caption(
                f"- Required daily sales: gap divided by remaining days = {utils.format_rupee_short(required_daily_sales)}"
            )
            st.caption(
                "- Covers-led recovery assumes APC remains at the current selected-period APC."
            )
            st.caption(
                "- APC-led recovery assumes average daily covers remain at the current selected-period run-rate."
            )
            st.caption(
                "- Balanced recovery splits the required lift across covers and APC."
            )

def render_outlet_performance_scorecard(
    df_raw: pd.DataFrame,
    prior_df: pd.DataFrame,
    analysis_period: str,
    start_date: date,
    end_date: date,
    all_locs: list,
) -> None:
    """Render outlet-level owner scorecard for multi-outlet decision-making."""
    required_columns = {"location_id", "date", "net_total", "covers"}

    if df_raw.empty or not required_columns.issubset(set(df_raw.columns)):
        return

    work_df = df_raw.copy()

    work_df["date"] = pd.to_datetime(work_df["date"], errors="coerce")
    work_df = work_df[work_df["date"].notna()].copy()

    if work_df.empty:
        return

    work_df["net_total"] = pd.to_numeric(
        work_df["net_total"],
        errors="coerce",
    ).fillna(0)

    work_df["covers"] = pd.to_numeric(
        work_df["covers"],
        errors="coerce",
    ).fillna(0)

    if "target" in work_df.columns:
        work_df["target"] = pd.to_numeric(
            work_df["target"],
            errors="coerce",
        ).fillna(0)
    else:
        work_df["target"] = 0

    loc_lookup = {
        int(loc["id"]): str(loc.get("name", loc["id"]))
        for loc in all_locs
        if "id" in loc
    }

    work_df["Outlet"] = work_df["location_id"].apply(
        lambda loc_id: loc_lookup.get(int(loc_id), str(loc_id))
    )

    unique_outlets = sorted(work_df["Outlet"].dropna().unique().tolist())

    if len(unique_outlets) < 2:
        return

    prior_work_df = prior_df.copy() if prior_df is not None else pd.DataFrame()

    if not prior_work_df.empty and required_columns.issubset(set(prior_work_df.columns)):
        prior_work_df["date"] = pd.to_datetime(prior_work_df["date"], errors="coerce")
        prior_work_df = prior_work_df[prior_work_df["date"].notna()].copy()

        prior_work_df["net_total"] = pd.to_numeric(
            prior_work_df["net_total"],
            errors="coerce",
        ).fillna(0)

        prior_work_df["covers"] = pd.to_numeric(
            prior_work_df["covers"],
            errors="coerce",
        ).fillna(0)

        prior_work_df["Outlet"] = prior_work_df["location_id"].apply(
            lambda loc_id: loc_lookup.get(int(loc_id), str(loc_id))
        )
    else:
        prior_work_df = pd.DataFrame()

    selected_range_days = max(1, (end_date - start_date).days + 1)

    rows: list[dict[str, object]] = []

    for outlet_name, outlet_df in work_df.groupby("Outlet"):
        outlet_df = outlet_df.sort_values("date").copy()

        net_sales = float(outlet_df["net_total"].sum())
        covers = float(outlet_df["covers"].sum())
        target = float(outlet_df["target"].sum())
        apc = net_sales / covers if covers > 0 else 0.0
        achievement_pct = net_sales / target * 100 if target > 0 else 0.0
        target_gap = target - net_sales if target > 0 else 0.0

        days_with_sales = int(len(outlet_df[outlet_df["net_total"] > 0]))

        outlet_prior_df = (
            prior_work_df[prior_work_df["Outlet"] == outlet_name].copy()
            if not prior_work_df.empty
            else pd.DataFrame()
        )

        prior_sales = (
            float(outlet_prior_df["net_total"].sum())
            if not outlet_prior_df.empty
            else None
        )
        prior_covers = (
            float(outlet_prior_df["covers"].sum())
            if not outlet_prior_df.empty
            else None
        )
        prior_apc = (
            prior_sales / prior_covers
            if prior_sales is not None and prior_covers is not None and prior_covers > 0
            else None
        )

        sales_delta_pct = _safe_pct_change(net_sales, prior_sales)
        covers_delta_pct = _safe_pct_change(covers, prior_covers)
        apc_delta_pct = _safe_pct_change(apc, prior_apc)

        forecast_days = calculate_forecast_days(
            analysis_period,
            data_points=len(outlet_df),
            selected_range_days=selected_range_days,
        )

        forecast_close = None

        if forecast_days > 0:
            forecast = linear_forecast(
                outlet_df["date"],
                outlet_df["net_total"].tolist(),
                forecast_days=forecast_days,
            )

            if forecast:
                forecast_close = net_sales + sum(
                    float(item.get("value", 0) or 0)
                    for item in forecast
                )

        data_flags: list[str] = []

        if days_with_sales < len(outlet_df):
            data_flags.append("Missing / zero-sales day")

        if len(outlet_df[(outlet_df["net_total"] > 0) & (outlet_df["covers"] <= 0)]) > 0:
            data_flags.append("Sales with zero covers")

        if target <= 0:
            data_flags.append("Missing target")

        priority_issue = "No major issue visible"

        if target > 0 and achievement_pct < 70:
            priority_issue = "Materially behind target"
        elif sales_delta_pct is not None and sales_delta_pct <= -8:
            priority_issue = "Sales declining vs comparison"
        elif covers_delta_pct is not None and covers_delta_pct <= -8:
            priority_issue = "Covers declining"
        elif apc_delta_pct is not None and apc_delta_pct <= -8:
            priority_issue = "APC declining"
        elif target > 0 and target_gap > 0:
            priority_issue = "Target gap still open"

        if target <= 0 or data_flags:
            status = "Watch"
        elif achievement_pct >= 100 and (
            sales_delta_pct is None or sales_delta_pct >= -5
        ):
            status = "Strong"
        elif achievement_pct < 70 or (
            sales_delta_pct is not None and sales_delta_pct <= -12
        ):
            status = "At Risk"
        else:
            status = "Watch"

        rows.append(
            {
                "Outlet": outlet_name,
                "Status": status,
                "Net Sales": net_sales,
                "Target": target,
                "Achievement %": achievement_pct,
                "Target Gap": target_gap,
                "Covers": covers,
                "APC": apc,
                "Sales Trend %": sales_delta_pct,
                "Covers Trend %": covers_delta_pct,
                "APC Trend %": apc_delta_pct,
                "Forecast Close": forecast_close,
                "Priority Issue": priority_issue,
                "Data Flags": ", ".join(data_flags) if data_flags else "OK",
            }
        )

    if not rows:
        return

    scorecard_df = pd.DataFrame(rows)

    status_rank = {
        "At Risk": 0,
        "Watch": 1,
        "Strong": 2,
    }

    scorecard_df["status_rank"] = scorecard_df["Status"].map(status_rank).fillna(3)
    scorecard_df = scorecard_df.sort_values(
        ["status_rank", "Achievement %", "Net Sales"],
        ascending=[True, True, False],
    ).reset_index(drop=True)

    at_risk_count = int((scorecard_df["Status"] == "At Risk").sum())
    watch_count = int((scorecard_df["Status"] == "Watch").sum())
    strong_count = int((scorecard_df["Status"] == "Strong").sum())

    with st.container(border=True):
        st.markdown("### Outlet Performance Scorecard")
        st.caption(
            "Use this to identify which outlet needs attention first and why."
        )

        metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)

        with metric_col_1:
            st.metric("At Risk", f"{at_risk_count}")

        with metric_col_2:
            st.metric("Watch", f"{watch_count}")

        with metric_col_3:
            st.metric("Strong", f"{strong_count}")

        with metric_col_4:
            weakest_row = scorecard_df.iloc[0]
            st.metric(
                "Needs Attention",
                str(weakest_row["Outlet"]),
                str(weakest_row["Priority Issue"]),
            )

        display_df = scorecard_df.copy()

        display_df["Net Sales"] = display_df["Net Sales"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )
        display_df["Target"] = display_df["Target"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )
        display_df["Target Gap"] = display_df["Target Gap"].apply(
            lambda value: (
                "Ahead"
                if float(value) <= 0
                else utils.format_rupee_short(float(value))
            )
        )
        display_df["Achievement %"] = display_df["Achievement %"].apply(
            lambda value: f"{float(value):.1f}%"
        )
        display_df["Covers"] = display_df["Covers"].apply(
            lambda value: f"{int(value):,}"
        )
        display_df["APC"] = display_df["APC"].apply(
            lambda value: utils.format_currency(float(value))
        )

        for col in ["Sales Trend %", "Covers Trend %", "APC Trend %"]:
            display_df[col] = display_df[col].apply(
                lambda value: "N/A" if pd.isna(value) else f"{float(value):+.1f}%"
            )

        display_df["Forecast Close"] = display_df["Forecast Close"].apply(
            lambda value: (
                "N/A"
                if pd.isna(value)
                else utils.format_rupee_short(float(value))
            )
        )

        st.dataframe(
            display_df[
                [
                    "Outlet",
                    "Status",
                    "Net Sales",
                    "Achievement %",
                    "Target Gap",
                    "Covers",
                    "APC",
                    "Sales Trend %",
                    "Covers Trend %",
                    "APC Trend %",
                    "Forecast Close",
                    "Priority Issue",
                    "Data Flags",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        if at_risk_count > 0:
            at_risk_names = ", ".join(
                scorecard_df[scorecard_df["Status"] == "At Risk"]["Outlet"].tolist()
            )
            st.error(
                f"Priority focus: {at_risk_names}. Review target gap, traffic and APC before pushing broad promotions."
            )
        elif watch_count > 0:
            watch_names = ", ".join(
                scorecard_df[scorecard_df["Status"] == "Watch"]["Outlet"].tolist()
            )
            st.warning(
                f"Watch list: {watch_names}. Track these outlets closely before the gap widens."
            )
        else:
            st.success(
                "All visible outlets are currently in a strong position against the selected scorecard rules."
            )

        with st.expander("How outlet status is calculated", expanded=False):
            st.caption("- Strong: outlet is at or above target and not materially declining versus comparison.")
            st.caption("- Watch: outlet has a target gap, data flags, or moderate performance risk.")
            st.caption("- At Risk: outlet is materially behind target or sales are sharply declining.")
            st.caption("- Trends are calculated versus the selected comparison period.")
            st.caption("- Forecast Close appears only for open/forward-looking periods where forecast days are available.")

def _build_action_tracker_suggestions(
    df: pd.DataFrame,
    prior_df: pd.DataFrame,
    monthly_target: float,
    total_sales: float,
    total_covers: int,
    analysis_period: str,
    selected_scope: str,
) -> list[dict[str, str]]:
    """Build actionable owner tasks from current dashboard signals."""
    suggestions: list[dict[str, str]] = []

    if df.empty:
        return suggestions

    work_df = df.copy()

    work_df["net_total"] = pd.to_numeric(
        work_df["net_total"],
        errors="coerce",
    ).fillna(0)

    work_df["covers"] = pd.to_numeric(
        work_df["covers"],
        errors="coerce",
    ).fillna(0)

    if "target" in work_df.columns:
        work_df["target"] = pd.to_numeric(
            work_df["target"],
            errors="coerce",
        ).fillna(0)
    else:
        work_df["target"] = 0

    selected_target = float(work_df["target"].sum())
    selected_gap = selected_target - total_sales if selected_target > 0 else 0.0
    current_apc = total_sales / total_covers if total_covers > 0 else 0.0

    prior_total = None
    prior_covers = None
    prior_apc = None

    if prior_df is not None and not prior_df.empty:
        prior_total = float(
            pd.to_numeric(prior_df["net_total"], errors="coerce").fillna(0).sum()
        )
        prior_covers = float(
            pd.to_numeric(prior_df["covers"], errors="coerce").fillna(0).sum()
        )
        prior_apc = prior_total / prior_covers if prior_covers > 0 else None

    sales_delta_pct = _safe_pct_change(total_sales, prior_total)
    covers_delta_pct = _safe_pct_change(total_covers, prior_covers)
    apc_delta_pct = _safe_pct_change(current_apc, prior_apc)

    if monthly_target > 0 and total_sales < monthly_target and analysis_period in {"MTD", "QTD", "YTD"}:
        suggestions.append(
            {
                "priority": "High",
                "action": "Review target recovery plan",
                "reason": (
                    f"Sales are below the active target plan. Current sales: "
                    f"{utils.format_rupee_short(total_sales)}."
                ),
                "owner": "Operations",
                "due": "Today",
                "success_metric": "Daily sales run-rate improves versus required sales plan.",
            }
        )

    if selected_target > 0 and selected_gap > 0:
        suggestions.append(
            {
                "priority": "High",
                "action": "Close selected-period target gap",
                "reason": f"Selected-period target gap is {utils.format_rupee_short(selected_gap)}.",
                "owner": "Outlet Manager",
                "due": "Next 3 days",
                "success_metric": "Target gap reduces versus current selected-period pace.",
            }
        )

    if covers_delta_pct is not None and covers_delta_pct <= -8:
        suggestions.append(
            {
                "priority": "High",
                "action": "Recover covers on weak days",
                "reason": f"Covers are {_format_owner_delta(covers_delta_pct)} versus comparison.",
                "owner": "Marketing / Reservations",
                "due": "This week",
                "success_metric": "Covers improve versus comparison period.",
            }
        )

    if apc_delta_pct is not None and apc_delta_pct <= -8:
        suggestions.append(
            {
                "priority": "High",
                "action": "Run APC improvement push",
                "reason": f"APC is {_format_owner_delta(apc_delta_pct)} versus comparison.",
                "owner": "Restaurant Manager",
                "due": "This week",
                "success_metric": "APC improves through premium items, drinks, desserts and sharing platters.",
            }
        )

    if (
        covers_delta_pct is not None
        and apc_delta_pct is not None
        and covers_delta_pct >= 8
        and apc_delta_pct <= -8
    ):
        suggestions.append(
            {
                "priority": "High",
                "action": "Convert traffic into higher spend",
                "reason": (
                    f"Covers are {_format_owner_delta(covers_delta_pct)}, "
                    f"but APC is {_format_owner_delta(apc_delta_pct)}."
                ),
                "owner": "Restaurant Manager",
                "due": "Next peak weekend",
                "success_metric": "APC improves without reducing covers.",
            }
        )

    if sales_delta_pct is not None and sales_delta_pct <= -8:
        suggestions.append(
            {
                "priority": "High",
                "action": "Diagnose sales decline",
                "reason": f"Sales are {_format_owner_delta(sales_delta_pct)} versus comparison.",
                "owner": "Operations",
                "due": "Today",
                "success_metric": "Primary decline driver is identified: traffic, APC, outlet, weekday, or category mix.",
            }
        )

    if not suggestions:
        suggestions.append(
            {
                "priority": "Medium",
                "action": "Protect current momentum",
                "reason": "No major negative signal is visible from sales, covers, APC or selected-period target gap.",
                "owner": "Operations",
                "due": "This week",
                "success_metric": "Top categories remain available and staffing matches peak demand.",
            }
        )

    # Remove duplicate action titles while keeping order.
    seen_actions: set[str] = set()
    unique_suggestions: list[dict[str, str]] = []

    for suggestion in suggestions:
        action_title = suggestion["action"]
        if action_title not in seen_actions:
            seen_actions.add(action_title)
            unique_suggestions.append(suggestion)

    priority_rank = {"High": 0, "Medium": 1, "Low": 2}
    unique_suggestions = sorted(
        unique_suggestions,
        key=lambda item: priority_rank.get(item["priority"], 3),
    )

    return unique_suggestions[:5]


def _ensure_action_tracker_state() -> None:
    """Initialise session state for the analytics action tracker."""
    if "analytics_action_tracker" not in st.session_state:
        st.session_state.analytics_action_tracker = []


def _action_exists(action_key: str) -> bool:
    """Check whether an action is already present in session state."""
    _ensure_action_tracker_state()
    return any(
        action.get("action_key") == action_key
        for action in st.session_state.analytics_action_tracker
    )


def render_action_tracker(
    df: pd.DataFrame,
    prior_df: pd.DataFrame,
    monthly_target: float,
    total_sales: float,
    total_covers: int,
    analysis_period: str,
    selected_scope: str,
    layout: str = "vertical",
) -> None:
    """Render owner action tracker from dashboard recommendations."""
    if df.empty:
        return

    _ensure_action_tracker_state()

    is_horizontal = layout == "horizontal"

    suggestions = _build_action_tracker_suggestions(
        df=df,
        prior_df=prior_df,
        monthly_target=monthly_target,
        total_sales=total_sales,
        total_covers=total_covers,
        analysis_period=analysis_period,
        selected_scope=selected_scope,
    )

    active_actions = [
        action
        for action in st.session_state.analytics_action_tracker
        if action.get("status") not in {"Done", "Cancelled"}
    ]

    done_actions = [
        action
        for action in st.session_state.analytics_action_tracker
        if action.get("status") == "Done"
    ]

    high_priority_open = len(
        [
            action
            for action in active_actions
            if action.get("priority") == "High"
        ]
    )

    def _action_key(index: int, suggestion: dict[str, str]) -> str:
        return (
            f"{selected_scope}_{analysis_period}_{index}_{suggestion['action']}"
            .lower()
            .replace(" ", "_")
            .replace("/", "_")
        )

    def _render_suggested_actions() -> None:
        st.markdown("#### Suggested Actions")

        if is_horizontal:
            cards_per_row = 3

            for row_start in range(0, len(suggestions), cards_per_row):
                row_suggestions = suggestions[row_start: row_start + cards_per_row]
                card_cols = st.columns(cards_per_row)

                for offset, suggestion in enumerate(row_suggestions):
                    index = row_start + offset
                    action_key = _action_key(index, suggestion)

                    with card_cols[offset]:
                        with st.container(border=True):
                            st.markdown(f"**{suggestion['action']}**")
                            st.caption(
                                f"{suggestion['priority']} priority · "
                                f"{suggestion['owner']} · "
                                f"Due: {suggestion['due']}"
                            )
                            st.caption(f"Reason: {suggestion['reason']}")
                            st.caption(f"Success: {suggestion['success_metric']}")

                            if _action_exists(action_key):
                                st.success("Added")
                            else:
                                if st.button(
                                    "Add",
                                    key=f"add_action_{action_key}",
                                    width="stretch",
                                ):
                                    st.session_state.analytics_action_tracker.append(
                                        {
                                            "action_key": action_key,
                                            "scope": selected_scope,
                                            "period": analysis_period,
                                            "priority": suggestion["priority"],
                                            "action": suggestion["action"],
                                            "reason": suggestion["reason"],
                                            "owner": suggestion["owner"],
                                            "due": suggestion["due"],
                                            "status": "Open",
                                            "success_metric": suggestion["success_metric"],
                                            "owner_note": "",
                                        }
                                    )
                                    st.rerun()

            return

        for index, suggestion in enumerate(suggestions):
            action_key = _action_key(index, suggestion)

            with st.container(border=True):
                s_col_1, s_col_2 = st.columns([4, 1])

                with s_col_1:
                    st.markdown(f"**{suggestion['action']}**")
                    st.caption(
                        f"Priority: {suggestion['priority']} · "
                        f"Suggested owner: {suggestion['owner']} · "
                        f"Due: {suggestion['due']}"
                    )
                    st.caption(f"Reason: {suggestion['reason']}")
                    st.caption(f"Success metric: {suggestion['success_metric']}")

                with s_col_2:
                    if _action_exists(action_key):
                        st.success("Added")
                    else:
                        if st.button(
                            "Add",
                            key=f"add_action_{action_key}",
                            width="stretch",
                        ):
                            st.session_state.analytics_action_tracker.append(
                                {
                                    "action_key": action_key,
                                    "scope": selected_scope,
                                    "period": analysis_period,
                                    "priority": suggestion["priority"],
                                    "action": suggestion["action"],
                                    "reason": suggestion["reason"],
                                    "owner": suggestion["owner"],
                                    "due": suggestion["due"],
                                    "status": "Open",
                                    "success_metric": suggestion["success_metric"],
                                    "owner_note": "",
                                }
                            )
                            st.rerun()

    def _render_action_management() -> None:
        with st.expander("Add custom action", expanded=False):
            with st.form("custom_analytics_action_form", clear_on_submit=True):
                custom_action = st.text_input(
                    "Action",
                    placeholder="Example: Push cocktail upsell script this weekend",
                )
                custom_owner = st.text_input(
                    "Owner",
                    placeholder="Example: Outlet Manager",
                )
                custom_priority = st.selectbox(
                    "Priority",
                    options=["High", "Medium", "Low"],
                    index=1,
                )
                custom_due = st.text_input(
                    "Due",
                    placeholder="Example: Friday / This week / 2026-05-20",
                )
                custom_success_metric = st.text_input(
                    "Success metric",
                    placeholder="Example: APC improves by 8%",
                )
                custom_note = st.text_area(
                    "Note",
                    placeholder="Add operating context or instructions.",
                    height=80,
                )

                submitted = st.form_submit_button("Add custom action")

                if submitted and custom_action.strip():
                    custom_key = (
                        f"custom_{selected_scope}_{analysis_period}_{custom_action}"
                        .lower()
                        .replace(" ", "_")
                        .replace("/", "_")
                    )

                    if not _action_exists(custom_key):
                        st.session_state.analytics_action_tracker.append(
                            {
                                "action_key": custom_key,
                                "scope": selected_scope,
                                "period": analysis_period,
                                "priority": custom_priority,
                                "action": custom_action.strip(),
                                "reason": "Custom owner-entered action.",
                                "owner": custom_owner.strip() or "Unassigned",
                                "due": custom_due.strip() or "Not set",
                                "status": "Open",
                                "success_metric": custom_success_metric.strip(),
                                "owner_note": custom_note.strip(),
                            }
                        )
                        st.success("Custom action added.")
                        st.rerun()
                    else:
                        st.warning("This custom action is already in the tracker.")

        if not st.session_state.analytics_action_tracker:
            st.info("No tracked actions yet. Add one of the suggested actions above.")
            return

        st.markdown("#### Tracked Actions")

        updated_actions: list[dict[str, object]] = []

        for index, action in enumerate(st.session_state.analytics_action_tracker):
            with st.container(border=True):
                header_col, remove_col = st.columns([5, 1])

                with header_col:
                    st.markdown(f"**{action.get('action', 'Untitled action')}**")
                    st.caption(
                        f"Scope: {action.get('scope', selected_scope)} · "
                        f"Period: {action.get('period', analysis_period)} · "
                        f"Reason: {action.get('reason', '')}"
                    )

                with remove_col:
                    remove_clicked = st.button(
                        "Remove",
                        key=f"remove_action_{index}_{action.get('action_key', index)}",
                    )

                if remove_clicked:
                    continue

                edit_col_1, edit_col_2, edit_col_3 = st.columns(3)

                with edit_col_1:
                    action["status"] = st.selectbox(
                        "Status",
                        options=["Open", "In Progress", "Blocked", "Done", "Cancelled"],
                        index=(
                            ["Open", "In Progress", "Blocked", "Done", "Cancelled"].index(
                                action.get("status", "Open")
                            )
                            if action.get("status", "Open")
                            in ["Open", "In Progress", "Blocked", "Done", "Cancelled"]
                            else 0
                        ),
                        key=f"action_status_{index}_{action.get('action_key', index)}",
                    )

                with edit_col_2:
                    action["owner"] = st.text_input(
                        "Owner",
                        value=str(action.get("owner", "")),
                        key=f"action_owner_{index}_{action.get('action_key', index)}",
                    )

                with edit_col_3:
                    action["due"] = st.text_input(
                        "Due",
                        value=str(action.get("due", "")),
                        key=f"action_due_{index}_{action.get('action_key', index)}",
                    )

                action["owner_note"] = st.text_area(
                    "Owner note / impact check",
                    value=str(action.get("owner_note", "")),
                    key=f"action_note_{index}_{action.get('action_key', index)}",
                    height=80,
                )

                st.caption(
                    f"Success metric: {action.get('success_metric', 'Not set')}"
                )

                updated_actions.append(action)

        st.session_state.analytics_action_tracker = updated_actions

        export_df = pd.DataFrame(st.session_state.analytics_action_tracker)

        if not export_df.empty:
            st.download_button(
                label="Download action tracker CSV",
                data=export_df.to_csv(index=False).encode("utf-8"),
                file_name="analytics_action_tracker.csv",
                mime="text/csv",
                key="download_analytics_action_tracker",
            )

        st.caption(
            "Current limitation: actions are stored in the app session. "
            "Download the CSV before refreshing if you need to preserve them. "
            "Database persistence can be added later."
        )

    with st.container(border=True):
        if is_horizontal:
            title_col, metric_col_1, metric_col_2, metric_col_3 = st.columns([3, 1, 1, 1])

            with title_col:
                st.markdown("### Action Tracker")
                st.caption(
                    "Convert dashboard signals into trackable operating actions."
                )

            with metric_col_1:
                st.metric("Open", f"{len(active_actions)}")

            with metric_col_2:
                st.metric("High Priority", f"{high_priority_open}")

            with metric_col_3:
                st.metric("Completed", f"{len(done_actions)}")

            _render_suggested_actions()

            with st.expander("Manage tracked actions", expanded=False):
                _render_action_management()

        else:
            st.markdown("### Action Tracker")
            st.caption(
                "Convert dashboard signals into trackable operating actions. "
                "This version stores actions in the current app session and allows CSV export."
            )

            tracker_col_1, tracker_col_2, tracker_col_3 = st.columns(3)

            with tracker_col_1:
                st.metric("Open Actions", f"{len(active_actions)}")

            with tracker_col_2:
                st.metric("High Priority", f"{high_priority_open}")

            with tracker_col_3:
                st.metric("Completed", f"{len(done_actions)}")

            _render_suggested_actions()
            _render_action_management()

def render_sales_quality_layer(
    df: pd.DataFrame,
    prior_df: pd.DataFrame,
    total_sales: float,
    total_covers: int,
) -> None:
    """Render owner-facing sales quality and estimated contribution layer."""
    if df.empty:
        return

    work_df = df.copy()

    numeric_columns = [
        "gross_total",
        "net_total",
        "discount",
        "complimentary",
        "service_charge",
        "zomato_sales",
        "covers",
    ]

    for column in numeric_columns:
        if column not in work_df.columns:
            work_df[column] = 0

        work_df[column] = pd.to_numeric(
            work_df[column],
            errors="coerce",
        ).fillna(0)

    gross_sales = float(work_df["gross_total"].sum())
    net_sales = float(work_df["net_total"].sum())
    discount_total = float(work_df["discount"].sum())
    complimentary_total = float(work_df["complimentary"].sum())
    service_charge_total = float(work_df["service_charge"].sum())
    zomato_pay_sales = float(work_df["zomato_sales"].sum())
    covers = float(work_df["covers"].sum())

    sales_base = gross_sales if gross_sales > 0 else net_sales
    current_apc = net_sales / covers if covers > 0 else 0.0

    prior_work_df = prior_df.copy() if prior_df is not None else pd.DataFrame()

    prior_net_sales = None
    prior_covers = None
    prior_apc = None
    prior_discount_total = None
    prior_complimentary_total = None
    prior_zomato_sales = None
    prior_sales_base = None

    if not prior_work_df.empty:
        for column in numeric_columns:
            if column not in prior_work_df.columns:
                prior_work_df[column] = 0

            prior_work_df[column] = pd.to_numeric(
                prior_work_df[column],
                errors="coerce",
            ).fillna(0)

        prior_gross_sales = float(prior_work_df["gross_total"].sum())
        prior_net_sales = float(prior_work_df["net_total"].sum())
        prior_discount_total = float(prior_work_df["discount"].sum())
        prior_complimentary_total = float(prior_work_df["complimentary"].sum())
        prior_zomato_sales = float(prior_work_df["zomato_sales"].sum())
        prior_covers = float(prior_work_df["covers"].sum())
        prior_sales_base = prior_gross_sales if prior_gross_sales > 0 else prior_net_sales
        prior_apc = prior_net_sales / prior_covers if prior_covers > 0 else None

    sales_delta_pct = _safe_pct_change(net_sales, prior_net_sales)
    apc_delta_pct = _safe_pct_change(current_apc, prior_apc)

    discount_pct = discount_total / sales_base * 100 if sales_base > 0 else 0.0
    complimentary_pct = complimentary_total / sales_base * 100 if sales_base > 0 else 0.0
    service_charge_pct = service_charge_total / net_sales * 100 if net_sales > 0 else 0.0
    zomato_exposure_pct = zomato_pay_sales / net_sales * 100 if net_sales > 0 else 0.0

    prior_discount_pct = (
        prior_discount_total / prior_sales_base * 100
        if prior_discount_total is not None
        and prior_sales_base is not None
        and prior_sales_base > 0
        else None
    )

    prior_complimentary_pct = (
        prior_complimentary_total / prior_sales_base * 100
        if prior_complimentary_total is not None
        and prior_sales_base is not None
        and prior_sales_base > 0
        else None
    )

    prior_zomato_exposure_pct = (
        prior_zomato_sales / prior_net_sales * 100
        if prior_zomato_sales is not None
        and prior_net_sales is not None
        and prior_net_sales > 0
        else None
    )

    discount_delta_pts = (
        discount_pct - prior_discount_pct
        if prior_discount_pct is not None
        else None
    )

    complimentary_delta_pts = (
        complimentary_pct - prior_complimentary_pct
        if prior_complimentary_pct is not None
        else None
    )

    zomato_exposure_delta_pts = (
        zomato_exposure_pct - prior_zomato_exposure_pct
        if prior_zomato_exposure_pct is not None
        else None
    )

    with st.container(border=True):
        st.markdown("### Sales Quality")
        st.caption(
            "Use this to check whether sales are healthy after leakage, platform exposure and APC movement."
        )

        assumption_col_1, assumption_col_2, assumption_col_3 = st.columns(3)

        with assumption_col_1:
            food_cost_pct = st.number_input(
                "Food cost %",
                min_value=0.0,
                max_value=100.0,
                value=33.0,
                step=1.0,
                key="sales_quality_food_cost_pct",
                help="Used only for estimated contribution. Adjust this to your current food-cost assumption.",
            )

        with assumption_col_2:
            other_variable_cost_pct = st.number_input(
                "Other variable cost %",
                min_value=0.0,
                max_value=100.0,
                value=5.0,
                step=1.0,
                key="sales_quality_other_variable_cost_pct",
                help="Packaging, payment charges, direct variable costs or other cost assumptions.",
            )

        with assumption_col_3:
            zomato_pay_fee_pct = st.number_input(
                "Zomato Pay fee %",
                min_value=0.0,
                max_value=100.0,
                value=5.9,
                step=0.1,
                key="sales_quality_zomato_fee_pct",
                help="Estimated fee on Zomato Pay sales. Change if your commercial terms are different.",
            )

        platform_cost = zomato_pay_sales * (zomato_pay_fee_pct / 100)
        food_cost_estimate = net_sales * (food_cost_pct / 100)
        other_variable_cost_estimate = net_sales * (other_variable_cost_pct / 100)

        estimated_contribution = (
            net_sales
            - food_cost_estimate
            - other_variable_cost_estimate
            - platform_cost
        )

        estimated_contribution_pct = (
            estimated_contribution / net_sales * 100
            if net_sales > 0
            else 0.0
        )

        leakage_total = discount_total + complimentary_total + platform_cost
        leakage_pct = leakage_total / sales_base * 100 if sales_base > 0 else 0.0

        quality_score = 100.0

        if discount_pct > 5:
            quality_score -= min(20, (discount_pct - 5) * 2)

        if complimentary_pct > 2:
            quality_score -= min(15, (complimentary_pct - 2) * 3)

        if zomato_exposure_pct > 20:
            quality_score -= min(15, (zomato_exposure_pct - 20) * 0.5)

        if apc_delta_pct is not None and apc_delta_pct < -5:
            quality_score -= min(20, abs(apc_delta_pct))

        if estimated_contribution_pct < 12:
            quality_score -= 15
        elif estimated_contribution_pct < 18:
            quality_score -= 8

        quality_score = max(0.0, min(100.0, quality_score))

        if quality_score >= 80:
            quality_label = "Strong"
            quality_severity = "success"
            quality_message = "Sales quality looks healthy from the available data."
        elif quality_score >= 65:
            quality_label = "Watch"
            quality_severity = "warning"
            quality_message = "Sales quality is acceptable, but at least one leakage or contribution risk is visible."
        else:
            quality_label = "Weak"
            quality_severity = "error"
            quality_message = "Sales quality is weak. Review leakage, APC and platform exposure before chasing more revenue."

        metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)

        with metric_col_1:
            st.metric(
                "Net Sales",
                utils.format_rupee_short(net_sales),
                (
                    f"{sales_delta_pct:+.1f}% vs comparison"
                    if sales_delta_pct is not None
                    else None
                ),
            )

        with metric_col_2:
            st.metric(
                "Estimated Contribution",
                utils.format_rupee_short(estimated_contribution),
                f"{estimated_contribution_pct:.1f}% of net sales",
                help="Net sales minus estimated food cost, other variable cost and Zomato Pay platform cost.",
            )

        with metric_col_3:
            st.metric(
                "Total Leakage",
                utils.format_rupee_short(leakage_total),
                f"{leakage_pct:.1f}% of sales base",
                help="Discounts + complimentary + estimated Zomato Pay platform cost.",
            )

        with metric_col_4:
            st.metric(
                "Sales Quality Score",
                f"{quality_score:.0f}/100",
                quality_label,
            )

        if quality_severity == "success":
            st.success(f"**{quality_label} sales quality** — {quality_message}")
        elif quality_severity == "warning":
            st.warning(f"**{quality_label} sales quality** — {quality_message}")
        else:
            st.error(f"**{quality_label} sales quality** — {quality_message}")

        leakage_rows = [
            {
                "Metric": "Discount",
                "Value": utils.format_rupee_short(discount_total),
                "% of Sales": f"{discount_pct:.1f}%",
                "Change vs Comparison": (
                    "N/A"
                    if discount_delta_pts is None
                    else f"{discount_delta_pts:+.1f} pts"
                ),
                "Owner Interpretation": (
                    "High discount leakage"
                    if discount_pct > 5
                    else "Controlled"
                ),
            },
            {
                "Metric": "Complimentary",
                "Value": utils.format_rupee_short(complimentary_total),
                "% of Sales": f"{complimentary_pct:.1f}%",
                "Change vs Comparison": (
                    "N/A"
                    if complimentary_delta_pts is None
                    else f"{complimentary_delta_pts:+.1f} pts"
                ),
                "Owner Interpretation": (
                    "High complimentary leakage"
                    if complimentary_pct > 2
                    else "Controlled"
                ),
            },
            {
                "Metric": "Zomato Pay Exposure",
                "Value": utils.format_rupee_short(zomato_pay_sales),
                "% of Sales": f"{zomato_exposure_pct:.1f}%",
                "Change vs Comparison": (
                    "N/A"
                    if zomato_exposure_delta_pts is None
                    else f"{zomato_exposure_delta_pts:+.1f} pts"
                ),
                "Owner Interpretation": (
                    "High platform exposure"
                    if zomato_exposure_pct > 20
                    else "Controlled"
                ),
            },
            {
                "Metric": "Estimated Zomato Pay Cost",
                "Value": utils.format_rupee_short(platform_cost),
                "% of Sales": f"{platform_cost / net_sales * 100:.1f}%" if net_sales > 0 else "0.0%",
                "Change vs Comparison": "N/A",
                "Owner Interpretation": "Estimated from Zomato Pay sales × fee assumption.",
            },
            {
                "Metric": "Service Charge",
                "Value": utils.format_rupee_short(service_charge_total),
                "% of Sales": f"{service_charge_pct:.1f}%",
                "Change vs Comparison": "N/A",
                "Owner Interpretation": "Positive revenue line, not leakage.",
            },
            {
                "Metric": "APC",
                "Value": utils.format_currency(current_apc),
                "% of Sales": "N/A",
                "Change vs Comparison": (
                    "N/A"
                    if apc_delta_pct is None
                    else f"{apc_delta_pct:+.1f}%"
                ),
                "Owner Interpretation": (
                    "APC declining"
                    if apc_delta_pct is not None and apc_delta_pct < -5
                    else "Stable / acceptable"
                ),
            },
        ]

        st.markdown("#### Quality Drivers")
        st.dataframe(
            pd.DataFrame(leakage_rows),
            width="stretch",
            hide_index=True,
        )

        risk_messages: list[str] = []

        if discount_pct > 5:
            risk_messages.append(
                f"Discount is {discount_pct:.1f}% of sales base. Check whether discounts are intentional and profitable."
            )

        if complimentary_pct > 2:
            risk_messages.append(
                f"Complimentary is {complimentary_pct:.1f}% of sales base. Review approval controls."
            )

        if zomato_exposure_pct > 20:
            risk_messages.append(
                f"Zomato Pay exposure is {zomato_exposure_pct:.1f}% of net sales. Check whether incremental sales justify platform cost."
            )

        if apc_delta_pct is not None and apc_delta_pct < -5:
            risk_messages.append(
                f"APC is {apc_delta_pct:+.1f}% vs comparison. Sales quality may be weakening even if sales look stable."
            )

        if estimated_contribution_pct < 15:
            risk_messages.append(
                f"Estimated contribution is {estimated_contribution_pct:.1f}% of net sales. Check assumptions and margin leakage."
            )

        with st.expander("Sales quality risks and assumptions", expanded=False):
            if risk_messages:
                for message in risk_messages:
                    st.warning(message)
            else:
                st.success("No major sales quality risk detected from the available data.")

            st.caption(
                "- Estimated contribution is not accounting profit. It is a directional contribution estimate based on your assumptions."
            )
            st.caption(
                "- Zomato Pay cost is estimated only from the Zomato Pay sales field and the fee percentage entered above."
            )
            st.caption(
                "- Discount and complimentary percentages use gross sales when available; otherwise they use net sales."
            )
            st.caption(
                "- Sales Quality Score is a decision signal, not an accounting metric."
            )

def render_category_quality_layer(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
    prior_start: date | None,
    prior_end: date | None,
    total_sales: float,
    prior_total: float | None,
) -> None:
    """Render owner-facing actual category quality and menu mix layer."""
    import database_analytics

    if not report_loc_ids:
        return

    current_rows = database_analytics.get_category_sales_for_date_range(
        report_loc_ids,
        start_str,
        end_str,
    )

    if not current_rows:
        return

    current_df = pd.DataFrame(current_rows)

    if (
        current_df.empty
        or "category" not in current_df.columns
        or "amount" not in current_df.columns
    ):
        return

    current_df["category"] = current_df["category"].astype(str).str.strip()
    current_df["category"] = current_df["category"].replace("", "Uncategorized")

    current_df["amount"] = pd.to_numeric(
        current_df["amount"],
        errors="coerce",
    ).fillna(0)

    if "qty" in current_df.columns:
        current_df["qty"] = pd.to_numeric(
            current_df["qty"],
            errors="coerce",
        ).fillna(0)
    else:
        current_df["qty"] = 0

    current_df = current_df[current_df["amount"] > 0].copy()

    if current_df.empty:
        return

    category_total = float(current_df["amount"].sum())

    if category_total <= 0:
        return

    current_df["share_pct"] = current_df["amount"] / category_total * 100

    prior_df = pd.DataFrame()

    if prior_start and prior_end:
        prior_rows = database_analytics.get_category_sales_for_date_range(
            report_loc_ids,
            prior_start.strftime("%Y-%m-%d"),
            prior_end.strftime("%Y-%m-%d"),
        )

        if prior_rows:
            prior_df = pd.DataFrame(prior_rows)

            if (
                not prior_df.empty
                and "category" in prior_df.columns
                and "amount" in prior_df.columns
            ):
                prior_df["category"] = prior_df["category"].astype(str).str.strip()
                prior_df["category"] = prior_df["category"].replace("", "Uncategorized")

                prior_df["amount"] = pd.to_numeric(
                    prior_df["amount"],
                    errors="coerce",
                ).fillna(0)

                if "qty" in prior_df.columns:
                    prior_df["qty"] = pd.to_numeric(
                        prior_df["qty"],
                        errors="coerce",
                    ).fillna(0)
                else:
                    prior_df["qty"] = 0

                prior_total_amount = float(prior_df["amount"].sum())
                prior_df["share_pct"] = (
                    prior_df["amount"] / prior_total_amount * 100
                    if prior_total_amount > 0
                    else 0
                )
            else:
                prior_df = pd.DataFrame()

    merged_df = current_df.merge(
        prior_df[["category", "amount", "share_pct"]].rename(
            columns={
                "amount": "prior_amount",
                "share_pct": "prior_share_pct",
            }
        )
        if not prior_df.empty
        else pd.DataFrame(columns=["category", "prior_amount", "prior_share_pct"]),
        on="category",
        how="left",
    )

    merged_df["prior_amount"] = pd.to_numeric(
        merged_df["prior_amount"],
        errors="coerce",
    ).fillna(0)

    merged_df["prior_share_pct"] = pd.to_numeric(
        merged_df["prior_share_pct"],
        errors="coerce",
    ).fillna(0)

    merged_df["growth_pct"] = merged_df.apply(
        lambda row: (
            (
                (float(row["amount"]) - float(row["prior_amount"]))
                / float(row["prior_amount"])
                * 100
            )
            if float(row["prior_amount"]) > 0
            else None
        ),
        axis=1,
    )

    merged_df["share_change_pts"] = merged_df["share_pct"] - merged_df["prior_share_pct"]

    merged_df = merged_df.sort_values("amount", ascending=False).reset_index(drop=True)

    def _is_beverage_category(category_name: str) -> bool:
        text = str(category_name or "").lower()
        beverage_terms = [
            "liquor",
            "beer",
            "wine",
            "spirit",
            "cocktail",
            "mocktail",
            "beverage",
            "drink",
            "coffee",
            "tea",
            "juice",
            "soft",
            "water",
        ]
        return any(term in text for term in beverage_terms)

    def _is_premium_category(category_name: str) -> bool:
        text = str(category_name or "").lower()
        premium_terms = [
            "meat",
            "beef",
            "pork",
            "seafood",
            "grill",
            "steak",
            "platter",
            "special",
            "chef",
            "wine",
            "cocktail",
            "liquor",
        ]
        return any(term in text for term in premium_terms)

    merged_df["is_beverage"] = merged_df["category"].apply(_is_beverage_category)
    merged_df["is_premium_signal"] = merged_df["category"].apply(_is_premium_category)

    beverage_sales = float(merged_df[merged_df["is_beverage"]]["amount"].sum())
    beverage_share = beverage_sales / category_total * 100 if category_total > 0 else 0.0

    prior_beverage_share = None

    if not prior_df.empty:
        prior_df["is_beverage"] = prior_df["category"].apply(_is_beverage_category)
        prior_category_total = float(prior_df["amount"].sum())
        prior_beverage_sales = float(prior_df[prior_df["is_beverage"]]["amount"].sum())

        prior_beverage_share = (
            prior_beverage_sales / prior_category_total * 100
            if prior_category_total > 0
            else None
        )

    beverage_share_delta = (
        beverage_share - prior_beverage_share
        if prior_beverage_share is not None
        else None
    )

    premium_sales = float(merged_df[merged_df["is_premium_signal"]]["amount"].sum())
    premium_share = premium_sales / category_total * 100 if category_total > 0 else 0.0

    top_category = str(merged_df.iloc[0]["category"])
    top_category_share = float(merged_df.iloc[0]["share_pct"])

    top_5_share = float(merged_df.head(5)["amount"].sum() / category_total * 100)

    category_coverage_pct = (
        category_total / total_sales * 100
        if total_sales > 0
        else 0.0
    )

    quality_score = 100.0

    if top_category_share >= 35:
        quality_score -= 18
    elif top_category_share >= 25:
        quality_score -= 10

    if top_5_share >= 80:
        quality_score -= 15
    elif top_5_share >= 65:
        quality_score -= 8

    if beverage_share < 12:
        quality_score -= 15
    elif beverage_share < 18:
        quality_score -= 8

    if beverage_share_delta is not None and beverage_share_delta <= -3:
        quality_score -= 10

    declining_major_categories = merged_df[
        (merged_df["share_pct"] >= 5)
        & (merged_df["growth_pct"].notna())
        & (merged_df["growth_pct"] <= -8)
    ]

    if not declining_major_categories.empty:
        quality_score -= 12

    if category_coverage_pct < 70:
        quality_score -= 10

    quality_score = max(0.0, min(100.0, quality_score))

    if quality_score >= 80:
        quality_label = "Strong"
        quality_severity = "success"
        quality_message = "Actual category mix looks healthy from the available data."
    elif quality_score >= 65:
        quality_label = "Watch"
        quality_severity = "warning"
        quality_message = "Actual category mix is usable, but at least one mix risk needs review."
    else:
        quality_label = "Weak"
        quality_severity = "error"
        quality_message = "Actual category mix quality is weak. Review concentration, beverage share and declining categories."

    with st.container(border=True):
        st.markdown("### Category Quality & Menu Mix")
        st.caption(
            "Uses actual POS category names. Beverage and premium signals are derived from category-name keywords."
        )

        metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)

        with metric_col_1:
            st.metric(
                "Top Actual Category",
                top_category,
                f"{top_category_share:.1f}% of category sales",
            )

        with metric_col_2:
            st.metric(
                "Beverage Share",
                f"{beverage_share:.1f}%",
                (
                    "N/A"
                    if beverage_share_delta is None
                    else f"{beverage_share_delta:+.1f} pts vs comparison"
                ),
            )

        with metric_col_3:
            st.metric(
                "Top 5 Share",
                f"{top_5_share:.1f}%",
                help="High concentration means the business depends on a small number of actual POS categories.",
            )

        with metric_col_4:
            st.metric(
                "Mix Quality Score",
                f"{quality_score:.0f}/100",
                quality_label,
            )

        if quality_severity == "success":
            st.success(f"**{quality_label} mix quality** — {quality_message}")
        elif quality_severity == "warning":
            st.warning(f"**{quality_label} mix quality** — {quality_message}")
        else:
            st.error(f"**{quality_label} mix quality** — {quality_message}")

        insight_messages: list[str] = []

        if top_category_share >= 25:
            insight_messages.append(
                f"{top_category} contributes {top_category_share:.1f}% of actual category sales. Protect availability, consistency and margin for this category."
            )

        if top_5_share >= 65:
            insight_messages.append(
                f"Top 5 actual categories contribute {top_5_share:.1f}% of category sales. This is a concentration risk if one category underperforms."
            )

        if beverage_share_delta is not None and beverage_share_delta <= -3:
            insight_messages.append(
                f"Beverage share is down {abs(beverage_share_delta):.1f} pts versus comparison. This may be hurting APC and contribution."
            )

        if beverage_share < 15:
            insight_messages.append(
                f"Beverage share is only {beverage_share:.1f}%. Review drinks attachment, upsell scripts and menu visibility."
            )

        if premium_share < 35:
            insight_messages.append(
                f"Premium signal categories are only {premium_share:.1f}% of actual category sales. Check whether high-value items are contributing enough."
            )

        if not declining_major_categories.empty:
            weak_names = ", ".join(
                declining_major_categories["category"].head(5).astype(str).tolist()
            )
            insight_messages.append(
                f"Declining important actual categories detected: {weak_names}. Check availability, pricing, guest preference shift or service execution."
            )

        if category_coverage_pct < 70:
            insight_messages.append(
                f"Category data covers only {category_coverage_pct:.1f}% of net sales. Use mix conclusions carefully."
            )

        if not insight_messages:
            insight_messages.append(
                "No major category quality issue detected from concentration, beverage share or comparison movement."
            )

        st.markdown("#### Owner Insights")
        for message in insight_messages[:5]:
            st.caption(f"- {message}")

        display_df = merged_df.copy()

        display_df["Sales"] = display_df["amount"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )

        display_df["Share"] = display_df["share_pct"].apply(
            lambda value: f"{float(value):.1f}%"
        )

        display_df["Growth vs Comparison"] = display_df["growth_pct"].apply(
            lambda value: "N/A" if pd.isna(value) else f"{float(value):+.1f}%"
        )

        display_df["Share Change"] = display_df["share_change_pts"].apply(
            lambda value: f"{float(value):+.1f} pts"
        )

        display_df["Qty"] = display_df["qty"].apply(
            lambda value: f"{int(value):,}"
        )

        display_df["Category Type"] = display_df.apply(
            lambda row: (
                "Beverage"
                if bool(row["is_beverage"])
                else "Premium signal"
                if bool(row["is_premium_signal"])
                else "Food / Other"
            ),
            axis=1,
        )

        display_df = display_df.rename(
            columns={
                "category": "Actual Category",
            }
        )

        st.markdown("#### Actual Category Movement")
        st.dataframe(
            display_df[
                [
                    "Actual Category",
                    "Category Type",
                    "Sales",
                    "Share",
                    "Growth vs Comparison",
                    "Share Change",
                    "Qty",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        with st.expander("How category quality is calculated", expanded=False):
            st.caption(
                "- This section uses actual POS category names from `get_category_sales_for_date_range()`."
            )
            st.caption(
                "- Beverage Share is derived from actual category names containing terms such as liquor, beer, wine, cocktail, mocktail, coffee, tea, juice, soft, drink, beverage or water."
            )
            st.caption(
                "- Premium signal categories are derived from actual category names containing terms such as meat, beef, pork, seafood, grill, steak, platter, special, chef, wine, cocktail or liquor."
            )
            st.caption(
                "- Top 5 Share checks whether sales are too dependent on a small number of actual POS categories."
            )
            st.caption(
                "- Growth vs Comparison compares actual category sales against the selected comparison period."
            )
            st.caption(
                "- Category totals may not perfectly match net sales because taxes, service charge, discounts, mapping and report-source differences can affect totals."
            )
            
def _style_achievement(val) -> str:
    """Pandas Styler.map function: color an Achievement % cell by band."""
    if pd.isna(val):
        return ""
    if val >= 100:
        return (
            f"background-color: {ui_theme.ACHIEVEMENT_HIGH_BG}; "
            f"color: {ui_theme.ACHIEVEMENT_HIGH_TEXT}"
        )
    if val >= 70:
        return (
            f"background-color: {ui_theme.ACHIEVEMENT_MED_BG}; "
            f"color: {ui_theme.ACHIEVEMENT_MED_TEXT}"
        )
    return (
        f"background-color: {ui_theme.ACHIEVEMENT_LOW_BG}; color: {ui_theme.ACHIEVEMENT_LOW_TEXT}"
    )


def _fmt_rupee_short(amount: float) -> str:
    """Format a rupee amount as a short label: ₹1.3k, ₹130k, ₹1.3L.

    Uses 1 decimal place for clarity (e.g., ₹1.3L not ₹1.27L).
    """
    abs_amt = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_amt >= 1_00_000:
        lakhs = abs_amt / 1_00_000
        return f"{sign}₹{lakhs:.1f}L"
    elif abs_amt >= 1_000:
        k = abs_amt / 1_000
        return f"{sign}₹{k:.1f}k"
    else:
        return f"{sign}₹{abs_amt:.0f}"


def _fmt_rupee_hover(values: list, name: str = "%{x|%b %d}") -> dict:
    """Build customdata + hovertemplate for ₹ formatting on a Plotly trace.

    Hover shows: "Sales: ₹1.3L" or "Forecast: ₹73k".
    """
    formatted = [_fmt_rupee_short(float(v)) for v in values]
    return {
        "customdata": formatted,
        "hovertemplate": name + ": %{customdata}<extra></extra>",
    }


def _fmt_int_hover(values: list, name: str = "%{x|%b %d}") -> dict:
    """Build hovertemplate for integer values (covers, counts).

    Hover shows: "Covers: 72".
    """
    formatted = [f"{int(v)}" for v in values]
    return {
        "customdata": formatted,
        "hovertemplate": name + ": %{customdata}<extra></extra>",
    }


def _rupee_yaxis() -> dict:
    """Y-axis config with k/L shorthand labels."""
    return dict(
        tickprefix="₹",
        ticksuffix="",
        tickformat=",d",
    )


def _make_rupee_ticks(min_val: float, max_val: float) -> tuple:
    """Generate nice tick values and text for a rupee y-axis range.

    Returns (tickvals, ticktext) for Plotly.
    Examples:
      0-200k  → [0, 50000, 100000, 150000, 200000], ['₹0', '₹50k', ...]
      0-3L    → [0, 100000, 200000, 300000], ['₹0', '₹1L', ...]
    """
    range_val = max_val - min_val
    if range_val <= 0:
        return ([0], ["₹0"])

    # Choose step size
    if max_val <= 1_00_000:
        step = 10_000

        def fmt_fn(v: int) -> str:
            return f"₹{v / 1_000:.0f}k"

    elif max_val <= 5_00_000:
        step = 50_000

        def fmt_fn(v: int) -> str:
            return f"₹{v / 1_000:.0f}k"

    else:
        step = 1_00_000

        def fmt_fn(v: int) -> str:
            return f"₹{v / 1_00_000:.1f}L"

    start = 0
    tickvals = list(range(start, int(max_val) + 1, step))
    ticktext = [fmt_fn(v) for v in tickvals]
    return (tickvals, ticktext)


def _chart_summary(text: str) -> None:
    """Render a screen-reader-friendly text summary of a chart's key insight."""
    st.caption(text)


def _daily_table_column_config() -> dict:
    return {
        "date": st.column_config.TextColumn("Date"),
        "covers": st.column_config.TextColumn("Covers"),
        "net_total": st.column_config.TextColumn("Net Sales (₹)"),
        "target": st.column_config.TextColumn("Target (₹)"),
        "pct_target": st.column_config.TextColumn("Achievement"),
    }


def _forecast_reliability_label(points: int) -> str:
    if points >= 21:
        return "High"
    if points >= 10:
        return "Medium"
    return "Low"


def _split_covers_weekpart(driver_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = driver_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["covers"] = pd.to_numeric(work["covers"], errors="coerce").fillna(0.0)
    work = work[work["date"].notna()].copy()
    work["weekday_name"] = work["date"].dt.day_name()
    weekday_df = work[work["weekday_name"].isin(_WEEKDAY_DAYS)].copy()
    weekend_df = work[work["weekday_name"].isin(_WEEKEND_DAYS)].copy()
    return weekday_df, weekend_df


def _build_weekpart_insight(driver_df: pd.DataFrame) -> dict[str, object]:
    weekday_df, weekend_df = _split_covers_weekpart(driver_df)
    weekday_count = int(len(weekday_df))
    weekend_count = int(len(weekend_df))

    if weekday_count == 0 or weekend_count == 0:
        return {
            "status": "insufficient",
            "weekday_count": weekday_count,
            "weekend_count": weekend_count,
            "weekday_avg": 0.0,
            "weekend_avg": 0.0,
            "delta_pct": None,
            "delta_abs": None,
            "commentary": "Insufficient data for comparison",
            "caution": None,
        }

    weekday_avg = float(weekday_df["covers"].mean())
    weekend_avg = float(weekend_df["covers"].mean())
    delta_abs = weekend_avg - weekday_avg
    delta_pct = None if weekday_avg <= 0 else (delta_abs / weekday_avg) * 100.0

    if delta_pct is None:
        commentary = "Weekday average is zero; comparing with absolute covers difference only."
    elif delta_pct >= 3:
        commentary = (
            f"Weekend-led pattern: covers are up {delta_pct:.1f}% vs weekdays, "
            "indicating stronger late-week demand."
        )
    elif delta_pct <= -3:
        commentary = (
            f"Weekday-led pattern: weekend covers are down {abs(delta_pct):.1f}% vs "
            "weekdays; review Friday-Sunday conversion/visibility."
        )
    else:
        commentary = "Balanced pattern: weekday and weekend covers are largely stable."

    caution = (
        "Low sample size; interpret trend carefully."
        if min(weekday_count, weekend_count) < 2
        else None
    )

    return {
        "status": "ok",
        "weekday_count": weekday_count,
        "weekend_count": weekend_count,
        "weekday_avg": weekday_avg,
        "weekend_avg": weekend_avg,
        "delta_pct": delta_pct,
        "delta_abs": delta_abs,
        "commentary": commentary,
        "caution": caution,
    }


def _render_weekpart_insight(insight: dict[str, object]) -> None:
    if insight.get("status") != "ok":
        st.caption("Insufficient data for comparison")
        return

    weekday_avg = float(insight["weekday_avg"])
    weekend_avg = float(insight["weekend_avg"])
    delta_pct = insight.get("delta_pct")
    delta_label = f"{delta_pct:+.1f}%" if isinstance(delta_pct, (float, int)) else "N/A"
    st.caption(
        "Avg Weekday (Mon-Thu): {:,.1f} | Avg Weekend (Fri-Sun): {:,.1f} | Delta: {}".format(
            weekday_avg,
            weekend_avg,
            delta_label,
        )
    )
    st.caption(str(insight.get("commentary") or ""))
    caution = insight.get("caution")
    if caution:
        st.caption(str(caution))


def _build_weekly_weekend_lift(driver_df: pd.DataFrame) -> pd.DataFrame:
    work = driver_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["covers"] = pd.to_numeric(work["covers"], errors="coerce").fillna(0.0)
    work = work[work["date"].notna()].copy()
    if work.empty:
        return pd.DataFrame()

    work["weekday_name"] = work["date"].dt.day_name()
    work["week_start"] = work["date"] - pd.to_timedelta(work["date"].dt.weekday, unit="D")

    rows: list[dict[str, object]] = []
    for week_start, wk in work.groupby("week_start"):
        weekday = wk[wk["weekday_name"].isin(_WEEKDAY_DAYS)]
        weekend = wk[wk["weekday_name"].isin(_WEEKEND_DAYS)]
        if weekday.empty or weekend.empty:
            continue
        weekday_avg = float(weekday["covers"].mean())
        weekend_avg = float(weekend["covers"].mean())
        if weekday_avg <= 0:
            continue
        lift_pct = ((weekend_avg / weekday_avg) - 1.0) * 100.0
        rows.append(
            {
                "week_start": week_start,
                "weekday_avg": weekday_avg,
                "weekend_avg": weekend_avg,
                "lift_pct": lift_pct,
            }
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values("week_start").reset_index(drop=True)
    return out


def _weekly_lift_commentary(lift_df: pd.DataFrame) -> str:
    if lift_df.empty or len(lift_df) < 2:
        return "Need at least 2 full weeks to comment on weekend lift trend."
    recent = float(lift_df.iloc[-1]["lift_pct"])
    prior = float(lift_df.iloc[-2]["lift_pct"])
    delta = recent - prior
    if delta >= 3:
        return f"Weekend lift is improving week-over-week (+{delta:.1f} pts)."
    if delta <= -3:
        return f"Weekend lift is softening week-over-week ({delta:.1f} pts)."
    return "Weekend lift is broadly stable week-over-week."


def _build_weekly_covers_trend(driver_df: pd.DataFrame) -> pd.DataFrame:
    work = driver_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["covers"] = pd.to_numeric(work["covers"], errors="coerce").fillna(0.0)
    work = work[work["date"].notna()].copy()
    if work.empty:
        return pd.DataFrame()

    work["week_start"] = work["date"] - pd.to_timedelta(work["date"].dt.weekday, unit="D")
    weekly = (
        work.groupby("week_start")["covers"]
        .agg(total_covers="sum", days_count="count")
        .reset_index()
        .sort_values("week_start")
    )
    weekly["avg_daily_covers"] = weekly["total_covers"] / weekly["days_count"]
    return weekly


def _weekly_covers_commentary(weekly_df: pd.DataFrame) -> str:
    if weekly_df.empty or len(weekly_df) < 2:
        return "Need at least 2 weeks to comment on week-over-week trend."

    recent = float(weekly_df.iloc[-1]["avg_daily_covers"])
    prior = float(weekly_df.iloc[-2]["avg_daily_covers"])
    if prior <= 0:
        return "Previous week average covers are zero; week-over-week change is not available."

    pct = ((recent - prior) / prior) * 100.0
    if pct >= 3:
        return f"Week-over-week trend is increasing: avg daily covers are up {pct:.1f}%."
    if pct <= -3:
        return f"Week-over-week trend is decreasing: avg daily covers are down {abs(pct):.1f}%."
    return "Week-over-week trend is stable: avg daily covers are broadly flat."

def render_sales_movement_waterfall(
    current_df: pd.DataFrame,
    prior_df: pd.DataFrame,
) -> None:
    """Render sales movement waterfall between current and prior period."""
    if current_df.empty or prior_df.empty:
        return

    required_columns = {"net_total", "covers"}
    if not required_columns.issubset(set(current_df.columns)):
        return
    if not required_columns.issubset(set(prior_df.columns)):
        return

    current_sales = float(
        pd.to_numeric(current_df["net_total"], errors="coerce").fillna(0).sum()
    )
    current_covers = float(
        pd.to_numeric(current_df["covers"], errors="coerce").fillna(0).sum()
    )

    prior_sales = float(
        pd.to_numeric(prior_df["net_total"], errors="coerce").fillna(0).sum()
    )
    prior_covers = float(
        pd.to_numeric(prior_df["covers"], errors="coerce").fillna(0).sum()
    )

    if prior_sales <= 0 or prior_covers <= 0 or current_covers <= 0:
        return

    prior_apc = prior_sales / prior_covers
    current_apc = current_sales / current_covers

    cover_effect = (current_covers - prior_covers) * prior_apc
    apc_effect = current_covers * (current_apc - prior_apc)

    total_movement = current_sales - prior_sales
    explained_movement = cover_effect + apc_effect
    residual_effect = total_movement - explained_movement

    with st.container(border=True):
        st.markdown("#### Sales Movement Breakdown")
        st.caption(
            "Explains whether sales changed because of guest count movement or APC movement."
        )

        fig_waterfall = go.Figure(
            go.Waterfall(
                name="Sales Movement",
                orientation="v",
                measure=[
                    "absolute",
                    "relative",
                    "relative",
                    "relative",
                    "total",
                ],
                x=[
                    "Prior Sales",
                    "Cover Effect",
                    "APC Effect",
                    "Other / Rounding",
                    "Current Sales",
                ],
                y=[
                    prior_sales,
                    cover_effect,
                    apc_effect,
                    residual_effect,
                    current_sales,
                ],
                connector={"line": {"width": 1}},
                hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
            )
        )

        fig_waterfall.update_layout(
            title="Prior Period to Current Period Sales Movement",
            yaxis_title="Sales ₹",
            height=360,
            margin=dict(l=0, r=0, t=50, b=40),
            showlegend=False,
        )

        st.plotly_chart(fig_waterfall, width="stretch")

        movement_summary = pd.DataFrame(
            [
                {
                    "Driver": "Prior Sales",
                    "Impact": utils.format_currency(prior_sales),
                },
                {
                    "Driver": "Cover Effect",
                    "Impact": utils.format_currency(cover_effect),
                },
                {
                    "Driver": "APC Effect",
                    "Impact": utils.format_currency(apc_effect),
                },
                {
                    "Driver": "Other / Rounding",
                    "Impact": utils.format_currency(residual_effect),
                },
                {
                    "Driver": "Current Sales",
                    "Impact": utils.format_currency(current_sales),
                },
            ]
        )

        with st.expander("View movement explanation"):
            st.dataframe(movement_summary, width="stretch", hide_index=True)

            if cover_effect > 0 and apc_effect > 0:
                st.success(
                    "Sales improved because both covers and APC moved positively."
                )
            elif cover_effect > 0 and apc_effect < 0:
                st.warning(
                    "Covers improved, but APC declined. This points to an upselling or menu-mix issue."
                )
            elif cover_effect < 0 and apc_effect > 0:
                st.warning(
                    "APC improved, but covers declined. This points to a traffic or demand issue."
                )
            elif cover_effect < 0 and apc_effect < 0:
                st.error(
                    "Both covers and APC declined. This needs demand recovery and ticket-size improvement."
                )

def _render_forecast_anomaly_inputs(variance_table: pd.DataFrame) -> None:
    """Render manual cause inputs for forecast anomaly days.

    These labels are stored in session_state for now and can be exported as CSV.
    Later, this can be persisted to the database and used as ML training labels.
    """
    if variance_table.empty:
        return

    cause_options = [
        "Not labelled",
        "Corporate booking / large party",
        "Private event",
        "Holiday / festival",
        "Local event",
        "Weather / rain",
        "Staffing issue",
        "Stockout",
        "Menu availability issue",
        "Service issue",
        "Aggregator / Zomato activity",
        "Marketing / promotion",
        "Data issue",
        "Unexpected walk-ins",
        "Low reservations",
        "Other",
    ]

    if "forecast_anomaly_labels" not in st.session_state:
        st.session_state.forecast_anomaly_labels = {}

    st.markdown("#### Manual Cause Labels")
    st.caption(
        "Label the likely cause of each forecast anomaly. These labels can later become training data for the ML model."
    )

    export_rows: list[dict[str, object]] = []

    for _, row in variance_table.iterrows():
        anomaly_date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
        default_key = f"{anomaly_date}_{str(row.get('weekday', ''))}"
        saved = st.session_state.forecast_anomaly_labels.get(default_key, {})

        with st.container(border=True):
            st.markdown(
                f"**{pd.Timestamp(row['date']).strftime('%d %b %Y')} · {row.get('weekday', '')}**"
            )

            st.caption(
                "Actual: {} | Forecast: {} | Variance: {} ({})".format(
                    utils.format_rupee_short(float(row.get("actual_sales", 0) or 0)),
                    utils.format_rupee_short(float(row.get("forecast_sales", 0) or 0)),
                    utils.format_rupee_short(float(row.get("variance", 0) or 0)),
                    (
                        "N/A"
                        if pd.isna(row.get("variance_pct"))
                        else f"{float(row.get('variance_pct')):+.1f}%"
                    ),
                )
            )

            st.caption(
                f"System-detected factor: {row.get('likely_factors', 'No factor detected')}"
            )

            selected_cause = st.selectbox(
                "Manual cause",
                options=cause_options,
                index=(
                    cause_options.index(saved.get("cause"))
                    if saved.get("cause") in cause_options
                    else 0
                ),
                key=f"forecast_anomaly_cause_{default_key}",
            )

            note = st.text_area(
                "Owner note",
                value=str(saved.get("note", "")),
                placeholder="Example: Large corporate table, rain affected lunch, stockout of key dish, Zomato campaign active, etc.",
                key=f"forecast_anomaly_note_{default_key}",
                height=80,
            )

            st.session_state.forecast_anomaly_labels[default_key] = {
                "date": anomaly_date,
                "weekday": str(row.get("weekday", "")),
                "actual_sales": float(row.get("actual_sales", 0) or 0),
                "forecast_sales": float(row.get("forecast_sales", 0) or 0),
                "variance": float(row.get("variance", 0) or 0),
                "variance_pct": (
                    None
                    if pd.isna(row.get("variance_pct"))
                    else float(row.get("variance_pct"))
                ),
                "actual_covers": float(row.get("actual_covers", 0) or 0),
                "actual_apc": float(row.get("actual_apc", 0) or 0),
                "outcome": str(row.get("outcome", "")),
                "system_detected_factors": str(row.get("likely_factors", "")),
                "manual_cause": selected_cause,
                "owner_note": note,
            }

            export_rows.append(st.session_state.forecast_anomaly_labels[default_key])

    labelled_df = pd.DataFrame(export_rows)

    if not labelled_df.empty:
        st.download_button(
            label="Download anomaly labels CSV",
            data=labelled_df.to_csv(index=False).encode("utf-8"),
            file_name="forecast_anomaly_labels.csv",
            mime="text/csv",
            key="download_forecast_anomaly_labels",
        )

def _forecast_quality_grade(
    accuracy: float | None,
    within_range_pct: float,
    bias_pct: float,
    tested_days: int,
) -> tuple[str, str, str]:
    """Convert backtest metrics into an owner-friendly forecast quality grade."""
    if accuracy is None or tested_days < 7:
        return (
            "Insufficient",
            "warning",
            "Not enough tested days to judge forecast quality confidently.",
        )

    abs_bias = abs(float(bias_pct))

    if accuracy >= 85 and within_range_pct >= 70 and abs_bias <= 8:
        return (
            "Strong",
            "success",
            "Forecast performance is strong enough for directional planning.",
        )

    if accuracy >= 75 and within_range_pct >= 60 and abs_bias <= 15:
        return (
            "Usable",
            "info",
            "Forecast is usable for owner decisions, but should be checked against context.",
        )

    if accuracy >= 65 and within_range_pct >= 45:
        return (
            "Watch",
            "warning",
            "Forecast has moderate error. Use it as a warning signal, not a firm target.",
        )

    return (
        "Weak",
        "error",
        "Forecast accuracy is weak for this period. Investigate variance drivers before relying on it.",
    )


def _render_forecast_quality_dashboard(
    result_df: pd.DataFrame,
    accuracy: float | None,
    within_range_pct: float,
    bias_pct: float,
) -> None:
    """Render a compact forecast quality dashboard from backtest results."""
    if result_df.empty:
        return

    quality_label, quality_severity, quality_message = _forecast_quality_grade(
        accuracy=accuracy,
        within_range_pct=within_range_pct,
        bias_pct=bias_pct,
        tested_days=len(result_df),
    )

    work_df = result_df.copy()

    work_df["abs_variance"] = pd.to_numeric(
        work_df["variance"],
        errors="coerce",
    ).abs()

    work_df["abs_pct_error"] = work_df.apply(
        lambda row: (
            abs(float(row["actual_sales"]) - float(row["forecast_sales"]))
            / float(row["actual_sales"])
            * 100
        )
        if float(row.get("actual_sales", 0) or 0) > 0
        and float(row.get("forecast_sales", 0) or 0) > 0
        else None,
        axis=1,
    )

    valid_error_df = work_df[work_df["abs_pct_error"].notna()].copy()

    hardest_weekday = "N/A"
    hardest_weekday_error = None

    if not valid_error_df.empty:
        weekday_errors = (
            valid_error_df.groupby("weekday", as_index=False)["abs_pct_error"]
            .mean()
            .sort_values("abs_pct_error", ascending=False)
        )

        if not weekday_errors.empty:
            hardest_weekday = str(weekday_errors.iloc[0]["weekday"])
            hardest_weekday_error = float(weekday_errors.iloc[0]["abs_pct_error"])

    # Error trend compares recent tested days against earlier tested days.
    error_trend_label = "N/A"
    error_trend_detail = "Need more tested days to compare recent forecast error."

    if len(valid_error_df) >= 10:
        recent_n = min(7, len(valid_error_df) // 2)
        recent_error = float(valid_error_df.tail(recent_n)["abs_pct_error"].mean())
        prior_error = float(valid_error_df.iloc[:-recent_n]["abs_pct_error"].mean())

        if prior_error > 0:
            error_delta = recent_error - prior_error

            if error_delta <= -3:
                error_trend_label = "Improving"
                error_trend_detail = (
                    f"Recent absolute error is down {abs(error_delta):.1f} pts "
                    "versus earlier tested days."
                )
            elif error_delta >= 3:
                error_trend_label = "Worsening"
                error_trend_detail = (
                    f"Recent absolute error is up {error_delta:.1f} pts "
                    "versus earlier tested days."
                )
            else:
                error_trend_label = "Stable"
                error_trend_detail = (
                    "Recent forecast error is broadly stable versus earlier tested days."
                )

    if bias_pct >= 8:
        bias_label = "Optimistic"
        bias_detail = "The model is generally forecasting higher than actual sales."
    elif bias_pct <= -8:
        bias_label = "Conservative"
        bias_detail = "The model is generally forecasting lower than actual sales."
    else:
        bias_label = "Balanced"
        bias_detail = "Forecast bias is within a reasonable range."

    with st.container(border=True):
        st.markdown("#### Forecast Quality Dashboard")
        st.caption(
            "Use this to judge whether the forecast is reliable enough for owner decisions."
        )

        if quality_severity == "success":
            st.success(f"**Forecast Quality: {quality_label}** — {quality_message}")
        elif quality_severity == "info":
            st.info(f"**Forecast Quality: {quality_label}** — {quality_message}")
        elif quality_severity == "warning":
            st.warning(f"**Forecast Quality: {quality_label}** — {quality_message}")
        else:
            st.error(f"**Forecast Quality: {quality_label}** — {quality_message}")

        q_col_1, q_col_2, q_col_3, q_col_4 = st.columns(4)

        with q_col_1:
            st.metric(
                "Hardest Day",
                hardest_weekday,
                (
                    f"{hardest_weekday_error:.1f}% avg error"
                    if hardest_weekday_error is not None
                    else None
                ),
            )

        with q_col_2:
            st.metric(
                "Bias Type",
                bias_label,
                f"{bias_pct:+.1f}%",
                help=bias_detail,
            )

        with q_col_3:
            st.metric(
                "Error Trend",
                error_trend_label,
            )

        with q_col_4:
            st.metric(
                "Range Reliability",
                f"{within_range_pct:.1f}%",
                help="Percentage of tested days where actual sales landed within the forecast range.",
            )

        st.caption(error_trend_detail)

        with st.expander("Forecast quality details by weekday", expanded=False):
            if valid_error_df.empty:
                st.caption("No valid percentage-error rows available.")
            else:
                weekday_quality = (
                    valid_error_df.groupby("weekday", as_index=False)
                    .agg(
                        tested_days=("date", "count"),
                        avg_actual=("actual_sales", "mean"),
                        avg_forecast=("forecast_sales", "mean"),
                        avg_abs_error_pct=("abs_pct_error", "mean"),
                    )
                    .sort_values("avg_abs_error_pct", ascending=False)
                )

                weekday_quality["Avg Actual"] = weekday_quality["avg_actual"].apply(
                    lambda value: utils.format_rupee_short(float(value))
                )
                weekday_quality["Avg Forecast"] = weekday_quality["avg_forecast"].apply(
                    lambda value: utils.format_rupee_short(float(value))
                )
                weekday_quality["Avg Error %"] = weekday_quality["avg_abs_error_pct"].apply(
                    lambda value: f"{float(value):.1f}%"
                )

                weekday_quality = weekday_quality.rename(
                    columns={
                        "weekday": "Weekday",
                        "tested_days": "Tested Days",
                    }
                )

                st.dataframe(
                    weekday_quality[
                        [
                            "Weekday",
                            "Tested Days",
                            "Avg Actual",
                            "Avg Forecast",
                            "Avg Error %",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                )

        with st.expander("Forecast outcome split", expanded=False):
            outcome_df = (
                work_df.groupby("outcome", as_index=False)
                .agg(days=("date", "count"))
                .sort_values("days", ascending=False)
            )

            outcome_df["Share"] = outcome_df["days"].apply(
                lambda value: f"{value / len(work_df) * 100:.1f}%"
                if len(work_df) > 0
                else "0.0%"
            )

            outcome_df = outcome_df.rename(
                columns={
                    "outcome": "Outcome",
                    "days": "Days",
                }
            )

            st.dataframe(
                outcome_df[["Outcome", "Days", "Share"]],
                width="stretch",
                hide_index=True,
            )

def render_forecast_backtest(df: pd.DataFrame) -> None:
    """Render rolling forecast-vs-achieved backtest for historical confidence building."""
    required_columns = {"date", "net_total"}

    if df.empty or not required_columns.issubset(set(df.columns)):
        return

    backtest_df = df.copy()

    backtest_df["date"] = pd.to_datetime(backtest_df["date"], errors="coerce")
    backtest_df = backtest_df[backtest_df["date"].notna()].copy()

    if backtest_df.empty:
        return

    backtest_df["net_total"] = pd.to_numeric(
        backtest_df["net_total"],
        errors="coerce",
    ).fillna(0)

    if "covers" in backtest_df.columns:
        backtest_df["covers"] = pd.to_numeric(
            backtest_df["covers"],
            errors="coerce",
        ).fillna(0)
    else:
        backtest_df["covers"] = 0

    backtest_df = backtest_df.sort_values("date").reset_index(drop=True)
    backtest_df["weekday"] = backtest_df["date"].dt.day_name()

    if len(backtest_df) < 10:
        return

    min_train_days = 14 if len(backtest_df) >= 21 else 7
    max_train_days = 35

    rows: list[dict[str, object]] = []

    for idx in range(min_train_days, len(backtest_df)):
        actual_row = backtest_df.iloc[idx]
        train_start_idx = max(0, idx - max_train_days)
        train_df = backtest_df.iloc[train_start_idx:idx].copy()

        if len(train_df) < 3:
            continue

        forecast = linear_forecast(
            train_df["date"],
            train_df["net_total"].tolist(),
            forecast_days=1,
        )

        if not forecast:
            continue

        forecast_point = forecast[0]

        actual_sales = float(actual_row["net_total"])
        forecast_sales = float(forecast_point.get("value", 0) or 0)
        lower_bound = float(forecast_point.get("lower", 0) or 0)
        upper_bound = float(forecast_point.get("upper", 0) or 0)

        variance = actual_sales - forecast_sales
        variance_pct = (
            variance / forecast_sales * 100
            if forecast_sales > 0
            else None
        )

        actual_covers = float(actual_row["covers"])
        train_avg_covers = float(train_df["covers"].mean()) if "covers" in train_df.columns else 0.0

        train_total_sales = float(train_df["net_total"].sum())
        train_total_covers = float(train_df["covers"].sum()) if "covers" in train_df.columns else 0.0
        train_apc = train_total_sales / train_total_covers if train_total_covers > 0 else 0.0
        actual_apc = actual_sales / actual_covers if actual_covers > 0 else 0.0

        weekday_name = str(actual_row["weekday"])
        same_weekday_df = train_df[train_df["weekday"] == weekday_name]
        same_weekday_avg = (
            float(same_weekday_df["net_total"].mean())
            if len(same_weekday_df) >= 2
            else None
        )

        variance_factors: list[str] = []

        if train_avg_covers > 0 and actual_covers > 0:
            covers_delta_pct = ((actual_covers - train_avg_covers) / train_avg_covers) * 100

            if covers_delta_pct >= 10:
                variance_factors.append(
                    f"Covers were {covers_delta_pct:+.1f}% above recent average."
                )
            elif covers_delta_pct <= -10:
                variance_factors.append(
                    f"Covers were {covers_delta_pct:+.1f}% below recent average."
                )

        if train_apc > 0 and actual_apc > 0:
            apc_delta_pct = ((actual_apc - train_apc) / train_apc) * 100

            if apc_delta_pct >= 8:
                variance_factors.append(
                    f"APC was {apc_delta_pct:+.1f}% above recent average."
                )
            elif apc_delta_pct <= -8:
                variance_factors.append(
                    f"APC was {apc_delta_pct:+.1f}% below recent average."
                )

        if same_weekday_avg is not None and same_weekday_avg > 0:
            weekday_delta_pct = ((actual_sales - same_weekday_avg) / same_weekday_avg) * 100

            if weekday_delta_pct >= 12:
                variance_factors.append(
                    f"{weekday_name} performed {weekday_delta_pct:+.1f}% above recent same-weekday average."
                )
            elif weekday_delta_pct <= -12:
                variance_factors.append(
                    f"{weekday_name} performed {weekday_delta_pct:+.1f}% below recent same-weekday average."
                )

        if forecast_sales > 0 and upper_bound > lower_bound:
            band_width_pct = ((upper_bound - lower_bound) / forecast_sales) * 100

            if band_width_pct >= 60:
                variance_factors.append(
                    "Forecast range was wide, indicating high sales volatility."
                )

        if not variance_factors:
            variance_factors.append(
                "Variance appears to be normal daily volatility or a factor not visible in sales/covers data."
            )

        if actual_sales > upper_bound:
            outcome = "Over achieved"
        elif actual_sales < lower_bound:
            outcome = "Under achieved"
        else:
            outcome = "Within forecast range"

        rows.append(
            {
                "date": actual_row["date"],
                "weekday": weekday_name,
                "actual_sales": actual_sales,
                "forecast_sales": forecast_sales,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "variance": variance,
                "variance_pct": variance_pct,
                "actual_covers": actual_covers,
                "actual_apc": actual_apc,
                "outcome": outcome,
                "likely_factors": " ".join(variance_factors),
            }
        )

    if not rows:
        return

    result_df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    actual_total = float(result_df["actual_sales"].sum())
    forecast_total = float(result_df["forecast_sales"].sum())
    total_variance = actual_total - forecast_total

    valid_pct_rows = result_df[
        (result_df["actual_sales"] > 0)
        & (result_df["forecast_sales"] > 0)
    ].copy()

    if valid_pct_rows.empty:
        mape = None
    else:
        mape = float(
            (
                (valid_pct_rows["actual_sales"] - valid_pct_rows["forecast_sales"]).abs()
                / valid_pct_rows["actual_sales"]
            ).mean()
            * 100
        )

    accuracy = max(0.0, 100.0 - mape) if mape is not None else None

    within_range_pct = float(
        (result_df["outcome"] == "Within forecast range").mean() * 100
    )

    if actual_total > 0:
        bias_pct = ((forecast_total - actual_total) / actual_total) * 100
    else:
        bias_pct = 0.0

    with st.expander("Forecast backtest: forecast vs achieved", expanded=False):
        st.caption(
            "This tests the forecast method against days that already happened. "
            "For each tested day, the model only uses earlier days in the selected period, "
            "then compares the forecast against actual sales."
        )

        metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)

        with metric_col_1:
            st.metric(
                "Tested Days",
                f"{len(result_df):,}",
            )

        with metric_col_2:
            st.metric(
                "Backtest Accuracy",
                f"{accuracy:.1f}%" if accuracy is not None else "N/A",
                help="Calculated as 100% minus mean absolute percentage error. Higher is better.",
            )

        with metric_col_3:
            st.metric(
                "Range Hit Rate",
                f"{within_range_pct:.1f}%",
                help="Percentage of tested days where actual sales fell inside the forecast range.",
            )

        with metric_col_4:
            st.metric(
                "Forecast Bias",
                f"{bias_pct:+.1f}%",
                help="Positive means the model over-forecasted overall. Negative means it under-forecasted.",
            )

        _render_forecast_quality_dashboard(
            result_df=result_df,
            accuracy=accuracy,
            within_range_pct=within_range_pct,
            bias_pct=bias_pct,
        )

        fig_backtest = go.Figure()

        fig_backtest.add_trace(
            go.Scatter(
                x=result_df["date"],
                y=result_df["upper_bound"],
                mode="lines",
                name="Upper Range",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )

        fig_backtest.add_trace(
            go.Scatter(
                x=result_df["date"],
                y=result_df["lower_bound"],
                mode="lines",
                name="Forecast Range",
                fill="tonexty",
                line=dict(width=0),
                fillcolor=_hex_to_rgba(ui_theme.BRAND_INFO, 0.18),
                hoverinfo="skip",
            )
        )

        fig_backtest.add_trace(
            go.Scatter(
                x=result_df["date"],
                y=result_df["actual_sales"],
                mode="lines+markers",
                name="Actual Sales",
                line=dict(color=ui_theme.BRAND_PRIMARY, width=3),
                marker=dict(size=5),
                hovertemplate="Actual: ₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
            )
        )

        fig_backtest.add_trace(
            go.Scatter(
                x=result_df["date"],
                y=result_df["forecast_sales"],
                mode="lines+markers",
                name="Forecast",
                line=dict(color=ui_theme.BRAND_WARN, width=2, dash="dash"),
                marker=dict(size=4),
                hovertemplate="Forecast: ₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
            )
        )

        fig_backtest.update_layout(
            title="Rolling Forecast Backtest",
            xaxis_title="Date",
            yaxis_title="Sales ₹",
            height=360,
            hovermode="x unified",
            margin=dict(l=0, r=0, t=50, b=40),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                xanchor="center",
                x=0.5,
            ),
        )

        st.plotly_chart(fig_backtest, width="stretch")

        st.markdown("#### Largest Variance Days")

        variance_table = result_df.copy()
        variance_table["abs_variance"] = variance_table["variance"].abs()
        variance_table = variance_table.sort_values("abs_variance", ascending=False).head(7)

        display_df = variance_table.copy()

        display_df["Date"] = display_df["date"].dt.strftime("%d %b %Y")
        display_df["Actual"] = display_df["actual_sales"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )
        display_df["Forecast"] = display_df["forecast_sales"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )
        display_df["Variance"] = display_df["variance"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )
        display_df["Variance %"] = display_df["variance_pct"].apply(
            lambda value: "N/A" if pd.isna(value) else f"{float(value):+.1f}%"
        )
        display_df["Covers"] = display_df["actual_covers"].apply(
            lambda value: f"{int(value):,}"
        )
        display_df["APC"] = display_df["actual_apc"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )

        display_df = display_df.rename(
            columns={
                "weekday": "Day",
                "outcome": "Outcome",
                "likely_factors": "Likely Variance Factors",
            }
        )

        st.dataframe(
            display_df[
                [
                    "Date",
                    "Day",
                    "Actual",
                    "Forecast",
                    "Variance",
                    "Variance %",
                    "Covers",
                    "APC",
                    "Outcome",
                    "Likely Variance Factors",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        st.caption(
            "Variance factors are directional, not causal proof. "
            "They are inferred from sales, covers, APC, weekday pattern and forecast range."
        )

        with st.expander("Add manual causes for anomaly days", expanded=False):
            _render_forecast_anomaly_inputs(variance_table)

def render_forecast_command_center(
    df: pd.DataFrame,
    prior_df: pd.DataFrame,
    analysis_period: str,
    start_date: date,
    end_date: date,
    prior_start: date | None,
    prior_end: date | None,
    monthly_target: float,
    total_sales: float,
    avg_daily: float,
    total_covers: int,
    days_with_data: int,
    prior_total: float | None,
    prior_covers: int | None,
    prior_avg: float | None,
) -> None:
    """Render forecast-first executive block with actionable cards."""
    if df.empty:
        return

    dates = pd.to_datetime(df["date"])
    values = pd.to_numeric(df["net_total"], errors="coerce").fillna(0).tolist()
    selected_days = max(1, (end_date - start_date).days + 1)
    forecast_days = calculate_forecast_days(
        analysis_period,
        data_points=len(values),
        selected_range_days=selected_days,
    )
    forecast = linear_forecast(dates, values, forecast_days=forecast_days)
    forecast_total = total_sales + sum(f["value"] for f in (forecast or []))
    reliability = _forecast_reliability_label(len(values))

    action_cards = _build_action_cards(
        current_df=df,
        prior_df=prior_df,
        monthly_target=monthly_target,
        forecast_total=forecast_total if forecast else 0.0,
    )

    forecast_value = utils.format_rupee_short(forecast_total) if forecast else "N/A"
    target_gap = (
        utils.format_rupee_short(max(0.0, monthly_target - forecast_total))
        if monthly_target > 0 and forecast
        else "N/A"
    )
    cov_delta = None
    if prior_covers is not None and prior_covers > 0:
        cov_growth = utils.calculate_growth(total_covers, prior_covers)
        cov_delta = f"{cov_growth['percentage']:+.1f}%"

    apc = total_sales / total_covers if total_covers > 0 else 0.0
    prior_apc = (
        (prior_total / prior_covers)
        if prior_total is not None and prior_covers is not None and prior_covers > 0
        else None
    )
    apc_delta = None
    if prior_apc and prior_apc > 0:
        apc_delta = f"{((apc - prior_apc) / prior_apc) * 100:+.1f}%"

    metrics = [
        KpiMetric(
            label="Net Sales",
            value=utils.format_rupee_short(total_sales),
            delta=utils.format_delta(total_sales, prior_total) if prior_total else None,
        ),
        KpiMetric(
            label="Forecast Close",
            value=forecast_value,
            delta=f"Reliability: {reliability}",
        ),
        KpiMetric(
            label="Target Gap",
            value=target_gap,
            delta=(
                "On track"
                if monthly_target > 0 and forecast and forecast_total >= monthly_target
                else "Behind pace"
                if monthly_target > 0 and forecast
                else None
            ),
        ),
        KpiMetric(
            label="Covers",
            value=f"{total_covers:,}",
            delta=f"{cov_delta or 'N/A'} vs prior",
        ),
        KpiMetric(
            label="APC",
            value=utils.format_currency(apc),
            delta=f"{apc_delta or 'N/A'} vs prior",
        ),
    ]
    kpi_row(metrics, columns=5)

    left_col, right_col = st.columns([2, 1])
    with left_col:
        chart_df = df.copy()
        chart_df["date"] = pd.to_datetime(chart_df["date"], errors="coerce")
        chart_df = chart_df[chart_df["date"].notna()].sort_values("date")

        chart_df["net_total"] = pd.to_numeric(
            chart_df["net_total"], errors="coerce"
        ).fillna(0)

        if "target" in chart_df.columns:
            chart_df["target"] = pd.to_numeric(
                chart_df["target"], errors="coerce"
            ).fillna(0)
        else:
            chart_df["target"] = 0

        chart_df["cumulative_sales"] = chart_df["net_total"].cumsum()
        chart_df["cumulative_target"] = chart_df["target"].cumsum()

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=chart_df["date"],
                y=chart_df["cumulative_sales"],
                mode="lines+markers",
                name="Actual Sales",
                line=dict(color=ui_theme.BRAND_PRIMARY, width=3),
                marker=dict(size=5),
                hovertemplate="Actual: ₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=chart_df["date"],
                y=chart_df["cumulative_target"],
                mode="lines",
                name="Target Pace",
                line=dict(color=ui_theme.BRAND_WARN, width=2, dash="dash"),
                hovertemplate="Target Pace: ₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
            )
        )

        if forecast:
            last_actual_date = chart_df["date"].max()
            last_actual_value = float(chart_df["cumulative_sales"].iloc[-1])

            f_dates = [f["date"] for f in forecast]
            f_daily_values = [float(f["value"]) for f in forecast]

            cumulative_forecast = []
            running_total = last_actual_value
            for value in f_daily_values:
                running_total += value
                cumulative_forecast.append(running_total)

            fig.add_trace(
                go.Scatter(
                    x=[last_actual_date] + f_dates,
                    y=[last_actual_value] + cumulative_forecast,
                    mode="lines",
                    name="Forecast Close",
                    line=dict(color=ui_theme.BRAND_SUCCESS, width=3, dash="dot"),
                    hovertemplate="Forecast: ₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
                )
            )

        fig.update_layout(
            title="Cumulative Sales vs Target Pace",
            xaxis_title="Date",
            yaxis_title="Sales ₹",
            hovermode="x unified",
            height=ui_theme.CHART_HEIGHT,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.22,
                xanchor="center",
                x=0.5,
            ),
        )

        st.plotly_chart(fig, width="stretch")

        forecast_explanation = build_forecast_explanation(values, forecast)

        if forecast_explanation.get("available"):
            with st.expander("Forecast explanation", expanded=False):
                st.markdown(
                    f"**Model:** {forecast_explanation['model_label']}"
                )

                explanation_col_1, explanation_col_2, explanation_col_3 = st.columns(3)

                with explanation_col_1:
                    st.metric(
                        "Forecast Confidence",
                        forecast_explanation["confidence"],
                    )

                with explanation_col_2:
                    st.metric(
                        "Forecast Days",
                        f"{forecast_explanation['forecast_days']}",
                    )

                with explanation_col_3:
                    st.metric(
                        "Volatility",
                        f"{forecast_explanation['volatility_pct'] * 100:.1f}%",
                    )

                st.caption(
                    "This is a transparent statistical forecast, not a machine-learning model. "
                    "It blends recent sales momentum, smoothing and weekday behaviour."
                )

                st.markdown("**What is driving the forecast**")
                for driver in forecast_explanation["drivers"]:
                    st.caption(f"- {driver}")

                st.markdown("**Key forecast inputs**")
                st.caption(
                    f"- Overall average: {utils.format_rupee_short(forecast_explanation['overall_avg'])}"
                )
                st.caption(
                    f"- Recent 7-day average: {utils.format_rupee_short(forecast_explanation['recent_7_avg'])}"
                )
                st.caption(
                    f"- Recent 14-day average: {utils.format_rupee_short(forecast_explanation['recent_14_avg'])}"
                )
                st.caption(
                    f"- Base forecast per day: {utils.format_rupee_short(forecast_explanation['base_forecast'])}"
                )
                st.caption(
                    f"- Weekday coverage: {forecast_explanation['weekday_coverage']} day type(s)"
                )

                if forecast_explanation["reliability_reasons"]:
                    st.markdown("**Confidence reasons**")
                    for reason in forecast_explanation["reliability_reasons"]:
                        st.caption(f"- {reason}")

                if forecast_explanation["cautions"]:
                    st.markdown("**Cautions**")
                    for caution in forecast_explanation["cautions"]:
                        st.warning(caution)
                        
        render_forecast_backtest(chart_df)

        if prior_start and prior_end:
            st.caption(
                "Comparison period: {} to {}.".format(
                    prior_start.strftime("%d %b %Y"),
                    prior_end.strftime("%d %b %Y"),
                )
            )

    with right_col:
        st.markdown("### Recommended Actions")

        visible_cards = action_cards[:2]
        hidden_cards = action_cards[2:]

        for card in visible_cards:
            body = (
                f"**{card['title']}**\n\n"
                f"{card['reason']}\n\n"
                f"**Action:** {card['action']}\n\n"
                f"{card['metric']}"
            )

            tone = card["severity"]
            if tone == "high":
                st.error(body)
            elif tone == "medium":
                st.warning(body)
            else:
                st.info(body)

        if hidden_cards:
            with st.expander("More actions", expanded=False):
                for card in hidden_cards:
                    body = (
                        f"**{card['title']}**\n\n"
                        f"{card['reason']}\n\n"
                        f"**Action:** {card['action']}\n\n"
                        f"{card['metric']}"
                    )

                    tone = card["severity"]
                    if tone == "high":
                        st.error(body)
                    elif tone == "medium":
                        st.warning(body)
                    else:
                        st.info(body)

    render_sales_movement_waterfall(df, prior_df)

def render_category_pareto(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
) -> None:
    """Render category Pareto chart for Mix layer."""
    category_rows = database.get_category_sales_for_date_range(
        report_loc_ids,
        start_str,
        end_str,
    )

    if not category_rows:
        st.info("No category sales available for Pareto analysis.")
        return

    pareto_df = pd.DataFrame(category_rows)

    if pareto_df.empty:
        st.info("No category sales available for Pareto analysis.")
        return

    if "category" not in pareto_df.columns or "amount" not in pareto_df.columns:
        st.warning("Category Pareto could not be rendered because category or amount data is missing.")
        return

    pareto_df["amount"] = pd.to_numeric(
        pareto_df["amount"],
        errors="coerce",
    ).fillna(0)

    pareto_df = pareto_df[pareto_df["amount"] > 0].copy()

    if pareto_df.empty:
        st.info("No positive category sales available for Pareto analysis.")
        return

    pareto_df = (
        pareto_df.groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )

    pareto_df["cumulative_sales"] = pareto_df["amount"].cumsum()
    total_sales = float(pareto_df["amount"].sum())
    pareto_df["cumulative_pct"] = pareto_df["cumulative_sales"] / total_sales * 100

    with st.container(border=True):
        st.markdown("#### Category Pareto")
        st.caption(
            "Bars show category sales. The line shows cumulative contribution, helping identify the few categories driving most revenue."
        )

        fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])

        fig_pareto.add_trace(
            go.Bar(
                x=pareto_df["category"],
                y=pareto_df["amount"],
                name="Category Sales",
                marker_color=ui_theme.BRAND_PRIMARY,
                hovertemplate="%{x}<br>Sales: ₹%{y:,.0f}<extra></extra>",
            ),
            secondary_y=False,
        )

        fig_pareto.add_trace(
            go.Scatter(
                x=pareto_df["category"],
                y=pareto_df["cumulative_pct"],
                name="Cumulative %",
                mode="lines+markers",
                line=dict(color=ui_theme.BRAND_WARN, width=3),
                marker=dict(size=6),
                hovertemplate="%{x}<br>Cumulative: %{y:.1f}%<extra></extra>",
            ),
            secondary_y=True,
        )

        fig_pareto.update_layout(
            title="Category Pareto",
            height=380,
            margin=dict(l=0, r=0, t=50, b=90),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.35,
                xanchor="center",
                x=0.5,
            ),
            xaxis=dict(tickangle=-35),
        )

        fig_pareto.update_yaxes(title_text="Sales ₹", secondary_y=False)
        fig_pareto.update_yaxes(
            title_text="Cumulative %",
            range=[0, 105],
            secondary_y=True,
        )

        st.plotly_chart(fig_pareto, width="stretch")

        with st.expander("View category Pareto data"):
            display_df = pareto_df.copy()
            display_df["Sales"] = display_df["amount"].apply(
                lambda val: utils.format_currency(float(val))
            )
            display_df["Cumulative %"] = display_df["cumulative_pct"].apply(
                lambda val: f"{val:.1f}%"
            )
            display_df = display_df[["category", "Sales", "Cumulative %"]]
            display_df = display_df.rename(columns={"category": "Category"})
            st.dataframe(display_df, width="stretch", hide_index=True)

def render_outlet_leaderboard(
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> None:
    """Render outlet-level performance leaderboard."""
    if not multi_analytics or df_raw.empty or "Outlet" not in df_raw.columns:
        return

    required_columns = {"Outlet", "net_total", "covers"}
    if not required_columns.issubset(set(df_raw.columns)):
        return

    outlet_df = df_raw.copy()

    outlet_df["net_total"] = pd.to_numeric(
        outlet_df["net_total"],
        errors="coerce",
    ).fillna(0)

    outlet_df["covers"] = pd.to_numeric(
        outlet_df["covers"],
        errors="coerce",
    ).fillna(0)

    if "target" in outlet_df.columns:
        outlet_df["target"] = pd.to_numeric(
            outlet_df["target"],
            errors="coerce",
        ).fillna(0)
    else:
        outlet_df["target"] = 0

    outlet_summary = (
        outlet_df.groupby("Outlet", as_index=False)
        .agg(
            net_total=("net_total", "sum"),
            covers=("covers", "sum"),
            target=("target", "sum"),
        )
        .sort_values("net_total", ascending=False)
    )

    if outlet_summary.empty:
        return

    outlet_summary["apc"] = outlet_summary.apply(
        lambda row: row["net_total"] / row["covers"] if row["covers"] > 0 else 0,
        axis=1,
    )

    outlet_summary["target_pct"] = outlet_summary.apply(
        lambda row: row["net_total"] / row["target"] * 100
        if row["target"] > 0
        else 0,
        axis=1,
    )

    outlet_summary["status"] = outlet_summary["target_pct"].apply(
        lambda value: "On Track"
        if value >= 100
        else "Watch"
        if value >= 70
        else "At Risk"
    )

    colors = [
        ui_theme.BRAND_SUCCESS
        if value >= 100
        else ui_theme.BRAND_WARN
        if value >= 70
        else "#EF4444"
        for value in outlet_summary["target_pct"]
    ]

    with st.container(border=True):
        st.markdown("#### Outlet Leaderboard")
        st.caption(
            "Compare outlets by sales, covers, APC and target achievement for the selected period."
        )

        fig_outlet = go.Figure()

        fig_outlet.add_trace(
            go.Bar(
                x=outlet_summary["Outlet"],
                y=outlet_summary["net_total"],
                marker_color=colors,
                name="Net Sales",
                hovertemplate=(
                    "%{x}<br>"
                    "Sales: ₹%{y:,.0f}<br>"
                    "<extra></extra>"
                ),
            )
        )

        fig_outlet.update_layout(
            title="Outlet Sales Ranking",
            xaxis_title="Outlet",
            yaxis_title="Net Sales ₹",
            height=320,
            margin=dict(l=0, r=0, t=50, b=60),
            showlegend=False,
        )

        st.plotly_chart(fig_outlet, width="stretch")

        display_df = outlet_summary.copy()
        display_df["Sales"] = display_df["net_total"].apply(
            lambda value: utils.format_currency(float(value))
        )
        display_df["Covers"] = display_df["covers"].apply(
            lambda value: f"{int(value):,}"
        )
        display_df["APC"] = display_df["apc"].apply(
            lambda value: utils.format_currency(float(value))
        )
        display_df["Target"] = display_df["target"].apply(
            lambda value: utils.format_currency(float(value))
        )
        display_df["Target %"] = display_df["target_pct"].apply(
            lambda value: f"{value:.1f}%"
        )

        display_df = display_df[
            [
                "Outlet",
                "Sales",
                "Covers",
                "APC",
                "Target",
                "Target %",
                "status",
            ]
        ]

        display_df = display_df.rename(
            columns={
                "status": "Status",
            }
        )

        st.dataframe(display_df, width="stretch", hide_index=True)

def render_driver_analysis(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> None:
    """Render focused traffic and ticket-size diagnostics."""
    if df.empty:
        st.caption("No driver data for this period.")
        return

    st.markdown("### Traffic & Ticket Drivers")
    st.caption("Use this layer to separate guest-count movement from ticket-size movement.")

    # 1. Visible by default: outlet leaderboard
    render_outlet_leaderboard(df_raw, multi_analytics)

    # 2. Build daily driver dataset
    if multi_analytics and not df_raw.empty:
        driver_df = (
            df_raw.groupby("date")[["covers", "net_total"]]
            .sum()
            .reset_index()
            .sort_values("date")
        )
    else:
        driver_df = df[["date", "covers", "net_total"]].copy().sort_values("date")

    driver_df["date"] = pd.to_datetime(driver_df["date"], errors="coerce")
    driver_df = driver_df[driver_df["date"].notna()].copy()

    driver_df["covers"] = pd.to_numeric(
        driver_df["covers"],
        errors="coerce",
    ).fillna(0)

    driver_df["net_total"] = pd.to_numeric(
        driver_df["net_total"],
        errors="coerce",
    ).fillna(0)

    driver_df["apc"] = driver_df.apply(
        lambda row: row["net_total"] / row["covers"] if row["covers"] > 0 else 0,
        axis=1,
    )

    if driver_df.empty:
        st.info("No valid driver rows available.")
        return

    # 3. Visible by default: Covers vs APC Matrix
    with st.container(border=True):
        st.markdown("#### Covers vs APC Matrix")
        st.caption(
            "Each point is a day. This shows whether sales are driven by footfall, ticket size, or both."
        )

        scatter_df = driver_df.copy()
        scatter_df["weekday"] = scatter_df["date"].dt.day_name()

        fig_scatter = px.scatter(
            scatter_df,
            x="covers",
            y="apc",
            size="net_total",
            color="weekday",
            hover_data={
                "date": True,
                "covers": ":,.0f",
                "apc": ":,.0f",
                "net_total": ":,.0f",
                "weekday": True,
            },
            labels={
                "covers": "Covers",
                "apc": "APC ₹",
                "net_total": "Net Sales ₹",
                "weekday": "Weekday",
            },
            title="Covers vs APC",
        )

        avg_covers = float(scatter_df["covers"].mean())
        avg_apc = float(scatter_df["apc"].mean())
        max_covers = float(scatter_df["covers"].max())
        max_apc = float(scatter_df["apc"].max())

        if avg_covers > 0:
            fig_scatter.add_vline(
                x=avg_covers,
                line_width=1,
                line_dash="dash",
                line_color=ui_theme.CHART_BAR_MUTED,
                annotation_text=f"Avg Covers: {avg_covers:.0f}",
                annotation_position="top",
            )

        if avg_apc > 0:
            fig_scatter.add_hline(
                y=avg_apc,
                line_width=1,
                line_dash="dash",
                line_color=ui_theme.CHART_BAR_MUTED,
                annotation_text=f"Avg APC: {utils.format_currency(avg_apc)}",
                annotation_position="right",
            )

        if max_covers > 0 and max_apc > 0:
            fig_scatter.add_annotation(
                x=max_covers,
                y=max_apc,
                text="Best Days<br>High Covers + High APC",
                showarrow=False,
                xanchor="right",
                yanchor="top",
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor=ui_theme.BORDER_SUBTLE,
                borderwidth=1,
                font=dict(size=11),
            )

            fig_scatter.add_annotation(
                x=avg_covers * 0.55,
                y=max_apc,
                text="Premium but Low Traffic",
                showarrow=False,
                xanchor="left",
                yanchor="top",
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor=ui_theme.BORDER_SUBTLE,
                borderwidth=1,
                font=dict(size=11),
            )

            fig_scatter.add_annotation(
                x=max_covers,
                y=avg_apc * 0.55,
                text="Busy but Low Spend<br>Upsell Opportunity",
                showarrow=False,
                xanchor="right",
                yanchor="bottom",
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor=ui_theme.BORDER_SUBTLE,
                borderwidth=1,
                font=dict(size=11),
            )

            fig_scatter.add_annotation(
                x=avg_covers * 0.55,
                y=avg_apc * 0.55,
                text="Weak Days",
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor=ui_theme.BORDER_SUBTLE,
                borderwidth=1,
                font=dict(size=11),
            )

        fig_scatter.update_layout(
            height=360,
            margin=dict(l=0, r=0, t=50, b=0),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.35,
                xanchor="center",
                x=0.5,
            ),
        )

        st.plotly_chart(fig_scatter, width="stretch")

    # 4. Collapsed: trend diagnostics
    with st.expander("Trend details: Covers and APC over time", expanded=False):
        covers_col, apc_col = st.columns(2)

        with covers_col:
            with st.container(border=True):
                st.markdown("#### Covers Trend")

                fig_covers = go.Figure(
                    go.Scatter(
                        x=driver_df["date"],
                        y=driver_df["covers"],
                        mode="lines+markers",
                        name="Covers",
                        line=dict(color=ui_theme.BRAND_SUCCESS, width=2),
                        marker=dict(size=4),
                        hovertemplate="%{y:,.0f} covers<br>%{x|%a, %d %b}<extra></extra>",
                    )
                )

                covers_values = driver_df["covers"].tolist()
                if len(covers_values) >= 7:
                    ma_values = moving_average(covers_values, window=7)
                    ma_series = pd.Series(ma_values)
                    ma_valid = ma_series[pd.notna(ma_series)]

                    if not ma_valid.empty:
                        fig_covers.add_trace(
                            go.Scatter(
                                x=driver_df["date"][pd.notna(ma_series)],
                                y=ma_valid.tolist(),
                                mode="lines",
                                name="7-day Avg",
                                line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                                hovertemplate=(
                                    "%{y:,.0f} covers (7-day avg)<br>"
                                    "%{x|%a, %d %b}<extra></extra>"
                                ),
                            )
                        )

                fig_covers.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Covers",
                    height=320,
                    hovermode="x unified",
                    xaxis=dict(tickformat="%a %d %b"),
                )

                st.plotly_chart(fig_covers, width="stretch")

                weekly_df = _build_weekly_covers_trend(driver_df[["date", "covers"]])
                if weekly_df.empty:
                    st.caption("Need valid date/cover rows to compute weekly trend.")
                else:
                    st.caption(_weekly_covers_commentary(weekly_df))

        with apc_col:
            with st.container(border=True):
                st.markdown("#### APC Trend")

                fig_apc = go.Figure(
                    go.Scatter(
                        x=driver_df["date"],
                        y=driver_df["apc"],
                        mode="lines+markers",
                        name="APC",
                        line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                        marker=dict(size=4),
                        hovertemplate="₹%{y:,.0f} APC<br>%{x|%d %b}<extra></extra>",
                    )
                )

                avg_apc = float(driver_df["apc"].mean()) if not driver_df.empty else 0.0
                if avg_apc > 0:
                    fig_apc.add_hline(
                        y=avg_apc,
                        line_dash="dash",
                        line_color=ui_theme.CHART_BAR_MUTED,
                        annotation_text=f"Avg {utils.format_currency(avg_apc)}",
                    )

                fig_apc.update_layout(
                    xaxis_title="Date",
                    yaxis_title="APC ₹",
                    height=320,
                    hovermode="x unified",
                )

                st.plotly_chart(fig_apc, width="stretch")

    # 5. Collapsed: daily driver table
    with st.expander("Daily driver data table", expanded=False):
        table = driver_df.rename(
            columns={
                "date": "Date",
                "covers": "Covers",
                "net_total": "Net Sales ₹",
                "apc": "APC ₹",
            }
        ).copy()

        table["Date"] = table["Date"].dt.strftime("%d %b %Y")
        table["Net Sales ₹"] = table["Net Sales ₹"].apply(
            lambda value: utils.format_currency(float(value))
        )
        table["APC ₹"] = table["APC ₹"].apply(
            lambda value: utils.format_currency(float(value))
        )
        table["Covers"] = table["Covers"].apply(lambda value: f"{int(value):,}")

        st.dataframe(table, width="stretch", hide_index=True)

def render_weekday_heatmap(df: pd.DataFrame) -> None:
    """Render week-by-week weekday heatmap for Mix layer."""
    if df.empty:
        st.info("No data available for weekday heatmap.")
        return

    required_columns = {"date", "net_total", "covers"}
    if not required_columns.issubset(set(df.columns)):
        st.warning("Weekday heatmap could not be rendered because date, net_total, or covers data is missing.")
        return

    heatmap_df = df.copy()

    heatmap_df["date"] = pd.to_datetime(heatmap_df["date"], errors="coerce")
    heatmap_df = heatmap_df[heatmap_df["date"].notna()].copy()

    if heatmap_df.empty:
        st.info("No valid dated rows available for weekday heatmap.")
        return

    heatmap_df["net_total"] = pd.to_numeric(
        heatmap_df["net_total"],
        errors="coerce",
    ).fillna(0)

    heatmap_df["covers"] = pd.to_numeric(
        heatmap_df["covers"],
        errors="coerce",
    ).fillna(0)

    if "target" in heatmap_df.columns:
        heatmap_df["target"] = pd.to_numeric(
            heatmap_df["target"],
            errors="coerce",
        ).fillna(0)
    else:
        heatmap_df["target"] = 0

    heatmap_df["pct_target"] = heatmap_df.apply(
        lambda row: row["net_total"] / row["target"] * 100
        if row["target"] > 0
        else 0,
        axis=1,
    )

    heatmap_df["weekday"] = heatmap_df["date"].dt.day_name()
    heatmap_df["week_start"] = heatmap_df["date"] - pd.to_timedelta(
        heatmap_df["date"].dt.weekday,
        unit="D",
    )
    heatmap_df["week_label"] = heatmap_df["week_start"].dt.strftime("Week of %d %b")

    with st.container(border=True):
        st.markdown("#### Weekday Heatmap")
        st.caption(
            "Shows how performance changes across weeks and weekdays. Use this to spot weak days, weekend dependency, and demand patterns."
        )

        selected_heatmap_metric = st.segmented_control(
            "Heatmap Metric",
            options=[
                "Net Sales",
                "Covers",
                "Target %",
            ],
            default="Net Sales",
            key="analytics_weekday_heatmap_metric",
        )

        if selected_heatmap_metric == "Net Sales":
            value_col = "net_total"
            aggfunc = "sum"
            color_label = "Net Sales ₹"
        elif selected_heatmap_metric == "Covers":
            value_col = "covers"
            aggfunc = "sum"
            color_label = "Covers"
        else:
            value_col = "pct_target"
            aggfunc = "mean"
            color_label = "Target %"

        weekday_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        pivot = heatmap_df.pivot_table(
            index="week_label",
            columns="weekday",
            values=value_col,
            aggfunc=aggfunc,
            fill_value=0,
        )

        pivot = pivot.reindex(
            columns=[day for day in weekday_order if day in pivot.columns]
        )

        week_order = (
            heatmap_df[["week_start", "week_label"]]
            .drop_duplicates()
            .sort_values("week_start")["week_label"]
            .tolist()
        )
        pivot = pivot.reindex(index=week_order)

        if selected_heatmap_metric == "Net Sales":
            text_values = pivot.map(
                lambda value: utils.format_currency(float(value))
            )
        elif selected_heatmap_metric == "Covers":
            text_values = pivot.map(lambda value: f"{int(value):,}")
        else:
            text_values = pivot.map(lambda value: f"{float(value):.1f}%")

        fig_heatmap = go.Figure(
            data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns,
                y=pivot.index,
                text=text_values.values,
                texttemplate="%{text}",
                colorscale="Blues",
                colorbar=dict(title=color_label),
                hovertemplate=(
                    "Week: %{y}<br>"
                    "Day: %{x}<br>"
                    f"{color_label}: %{{text}}"
                    "<extra></extra>"
                ),
            )
        )

        fig_heatmap.update_layout(
            title=f"Weekday Heatmap - {selected_heatmap_metric}",
            height=360,
            margin=dict(l=0, r=0, t=50, b=40),
            xaxis_title="Day of Week",
            yaxis_title="Week",
        )

        st.plotly_chart(fig_heatmap, width="stretch")

def render_weekday_summary_table(df: pd.DataFrame) -> None:
    """Render weekday-level sales, covers, APC and target achievement summary."""
    if df.empty:
        return

    required_columns = {"date", "net_total", "covers"}
    if not required_columns.issubset(set(df.columns)):
        return

    weekday_df = df.copy()

    weekday_df["date"] = pd.to_datetime(weekday_df["date"], errors="coerce")
    weekday_df = weekday_df[weekday_df["date"].notna()].copy()

    if weekday_df.empty:
        return

    weekday_df["net_total"] = pd.to_numeric(
        weekday_df["net_total"],
        errors="coerce",
    ).fillna(0)

    weekday_df["covers"] = pd.to_numeric(
        weekday_df["covers"],
        errors="coerce",
    ).fillna(0)

    if "target" in weekday_df.columns:
        weekday_df["target"] = pd.to_numeric(
            weekday_df["target"],
            errors="coerce",
        ).fillna(0)
    else:
        weekday_df["target"] = 0

    weekday_df["weekday"] = weekday_df["date"].dt.day_name()

    weekday_summary = (
        weekday_df.groupby("weekday", as_index=False)
        .agg(
            sales=("net_total", "sum"),
            covers=("covers", "sum"),
            target=("target", "sum"),
            days=("date", "count"),
        )
    )

    weekday_summary["apc"] = weekday_summary.apply(
        lambda row: row["sales"] / row["covers"] if row["covers"] > 0 else 0,
        axis=1,
    )

    weekday_summary["target_pct"] = weekday_summary.apply(
        lambda row: row["sales"] / row["target"] * 100
        if row["target"] > 0
        else 0,
        axis=1,
    )

    weekday_summary["avg_sales_per_day"] = weekday_summary.apply(
        lambda row: row["sales"] / row["days"] if row["days"] > 0 else 0,
        axis=1,
    )

    weekday_summary["status"] = weekday_summary["target_pct"].apply(
        lambda value: "Strong"
        if value >= 100
        else "Watch"
        if value >= 70
        else "Weak"
    )

    day_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    weekday_summary["weekday"] = pd.Categorical(
        weekday_summary["weekday"],
        categories=day_order,
        ordered=True,
    )

    weekday_summary = weekday_summary.sort_values("weekday")

    display_df = weekday_summary.copy()
    display_df["Sales"] = display_df["sales"].apply(
        lambda value: utils.format_rupee_short(float(value))
    )
    display_df["Avg Sales / Day"] = display_df["avg_sales_per_day"].apply(
        lambda value: utils.format_rupee_short(float(value))
    )
    display_df["Covers"] = display_df["covers"].apply(
        lambda value: f"{int(value):,}"
    )
    display_df["APC"] = display_df["apc"].apply(
        lambda value: utils.format_rupee_short(float(value))
    )
    display_df["Target %"] = display_df["target_pct"].apply(
        lambda value: f"{value:.1f}%"
    )

    display_df = display_df.rename(
        columns={
            "weekday": "Day",
            "days": "Days",
            "status": "Status",
        }
    )

    display_df = display_df[
        [
            "Day",
            "Days",
            "Sales",
            "Avg Sales / Day",
            "Covers",
            "APC",
            "Target %",
            "Status",
        ]
    ]

    with st.container(border=True):
        st.markdown("#### Weekday Summary")
        st.caption(
            "Use this table to compare weekday performance and identify whether weak days are driven by covers, APC, or both."
        )

        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
        )

def render_mix_snapshot(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
    df: pd.DataFrame,
    start_date: date,
) -> None:
    """Render focused mix and timing diagnostics without redundant charts."""
    if df.empty:
        st.caption("No mix or timing data for this period.")
        return

    st.markdown("### Mix & Timing")
    st.caption(
        "Use this layer to understand category concentration and weekday demand patterns."
    )

    render_category_pareto(report_loc_ids, start_str, end_str)

    render_weekday_heatmap(df)

    render_weekday_summary_table(df)
    

def render_target_pace_snapshot(df: pd.DataFrame) -> None:
    """Render selected-period target pace snapshot."""
    if df.empty:
        return

    required_columns = {"date", "net_total", "target"}
    if not required_columns.issubset(set(df.columns)):
        return

    pace_df = df.copy()

    pace_df["date"] = pd.to_datetime(pace_df["date"], errors="coerce")
    pace_df = pace_df[pace_df["date"].notna()].copy()

    if pace_df.empty:
        return

    pace_df["net_total"] = pd.to_numeric(
        pace_df["net_total"],
        errors="coerce",
    ).fillna(0)

    pace_df["target"] = pd.to_numeric(
        pace_df["target"],
        errors="coerce",
    ).fillna(0)

    total_sales = float(pace_df["net_total"].sum())
    total_target = float(pace_df["target"].sum())
    days_count = int(len(pace_df))
    days_with_sales = int(len(pace_df[pace_df["net_total"] > 0]))

    achievement_pct = (total_sales / total_target * 100) if total_target > 0 else 0
    variance = total_sales - total_target
    avg_daily_sales = total_sales / days_with_sales if days_with_sales > 0 else 0
    required_daily_sales = total_target / days_count if days_count > 0 else 0

    status_delta = (
        "Ahead of target"
        if variance >= 0
        else f"Behind by {utils.format_rupee_short(abs(variance))}"
    )

    with st.container(border=True):
        st.markdown("#### Target Pace Snapshot")
        st.caption(
            "Quick summary of sales performance against the selected period target."
        )

        metrics = [
            KpiMetric(
                label="Selected Period Sales",
                value=utils.format_rupee_short(total_sales),
                delta=status_delta,
            ),
            KpiMetric(
                label="Selected Period Target",
                value=utils.format_rupee_short(total_target),
                delta=f"{days_count} days in view",
            ),
            KpiMetric(
                label="Achievement",
                value=f"{achievement_pct:.1f}%",
                delta="Target progress",
            ),
            KpiMetric(
                label="Avg Daily Sales",
                value=utils.format_rupee_short(avg_daily_sales),
                delta=f"{days_with_sales} sales days",
            ),
            KpiMetric(
                label="Required Daily Sales",
                value=utils.format_rupee_short(required_daily_sales),
                delta="To match target pace",
            ),
        ]

        kpi_row(metrics, columns=5)

def render_daily_target_variance(df: pd.DataFrame) -> None:
    """Render daily sales variance against target."""
    if df.empty:
        st.info("No daily data available for target variance.")
        return

    variance_df = df.copy()

    required_columns = {"date", "net_total", "target"}
    if not required_columns.issubset(set(variance_df.columns)):
        st.warning("Daily target variance could not be rendered because date, net_total, or target data is missing.")
        return

    variance_df["date"] = pd.to_datetime(variance_df["date"], errors="coerce")
    variance_df = variance_df[variance_df["date"].notna()].copy()

    variance_df["net_total"] = pd.to_numeric(
        variance_df["net_total"],
        errors="coerce",
    ).fillna(0)

    variance_df["target"] = pd.to_numeric(
        variance_df["target"],
        errors="coerce",
    ).fillna(0)

    variance_df = variance_df.sort_values("date")
    variance_df["variance"] = variance_df["net_total"] - variance_df["target"]

    if variance_df.empty:
        st.info("No valid daily rows available for target variance.")
        return

    colors = [
        ui_theme.BRAND_SUCCESS if value >= 0 else ui_theme.BRAND_ERROR
        for value in variance_df["variance"]
    ]

    with st.container(border=True):
        st.markdown("#### Daily Target Variance")
        st.caption(
            "Green bars beat target. Red bars missed target. This helps identify which exact days created the target gap."
        )

        fig_variance = go.Figure()

        fig_variance.add_trace(
            go.Bar(
                x=variance_df["date"],
                y=variance_df["variance"],
                name="Variance vs Target",
                marker_color=colors,
                hovertemplate=(
                    "%{x|%d %b}<br>"
                    "Variance: ₹%{y:,.0f}<extra></extra>"
                ),
            )
        )

        fig_variance.add_hline(
            y=0,
            line_width=1,
            line_dash="dash",
            line_color=ui_theme.CHART_BAR_MUTED,
        )

        fig_variance.update_layout(
            title="Daily Variance vs Target",
            xaxis_title="Date",
            yaxis_title="Variance ₹",
            height=340,
            margin=dict(l=0, r=0, t=50, b=40),
            showlegend=False,
        )

        st.plotly_chart(fig_variance, width="stretch")

        with st.expander("View daily target variance data"):
            display_df = variance_df.copy()
            display_df["Date"] = display_df["date"].dt.strftime("%d %b %Y")
            display_df["Net Sales"] = display_df["net_total"].apply(
                lambda val: utils.format_currency(float(val))
            )
            display_df["Target"] = display_df["target"].apply(
                lambda val: utils.format_currency(float(val))
            )
            display_df["Variance"] = display_df["variance"].apply(
                lambda val: utils.format_currency(float(val))
            )

            display_df = display_df[
                [
                    "Date",
                    "Net Sales",
                    "Target",
                    "Variance",
                ]
            ]

            st.dataframe(display_df, width="stretch", hide_index=True)

def render_top_bottom_target_days(df: pd.DataFrame) -> None:
    """Render best and worst days versus target."""
    if df.empty:
        return

    required_columns = {"date", "net_total", "target"}
    if not required_columns.issubset(set(df.columns)):
        return

    days_df = df.copy()

    days_df["date"] = pd.to_datetime(days_df["date"], errors="coerce")
    days_df = days_df[days_df["date"].notna()].copy()

    if days_df.empty:
        return

    days_df["net_total"] = pd.to_numeric(
        days_df["net_total"],
        errors="coerce",
    ).fillna(0)

    days_df["target"] = pd.to_numeric(
        days_df["target"],
        errors="coerce",
    ).fillna(0)

    days_df["variance"] = days_df["net_total"] - days_df["target"]
    days_df["achievement_pct"] = days_df.apply(
        lambda row: row["net_total"] / row["target"] * 100
        if row["target"] > 0
        else 0,
        axis=1,
    )

    days_df = days_df.sort_values("variance", ascending=False)

    top_days = days_df.head(5).copy()
    bottom_days = days_df.tail(5).sort_values("variance", ascending=True).copy()

    def _format_target_days_table(table_df: pd.DataFrame) -> pd.DataFrame:
        display_df = table_df.copy()
        display_df["Date"] = display_df["date"].dt.strftime("%d %b %Y")
        display_df["Net Sales"] = display_df["net_total"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )
        display_df["Target"] = display_df["target"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )
        display_df["Variance"] = display_df["variance"].apply(
            lambda value: utils.format_rupee_short(float(value))
        )
        display_df["Achievement"] = display_df["achievement_pct"].apply(
            lambda value: f"{value:.1f}%"
        )

        return display_df[
            [
                "Date",
                "Net Sales",
                "Target",
                "Variance",
                "Achievement",
            ]
        ]

    with st.container(border=True):
        st.markdown("#### Best & Worst Target Days")
        st.caption(
            "Quickly identify which days contributed most positively or negatively to target achievement."
        )

        top_col, bottom_col = st.columns(2)

        with top_col:
            st.markdown("##### Top 5 Days")
            st.dataframe(
                _format_target_days_table(top_days),
                width="stretch",
                hide_index=True,
            )

        with bottom_col:
            st.markdown("##### Bottom 5 Days")
            st.dataframe(
                _format_target_days_table(bottom_days),
                width="stretch",
                hide_index=True,
            )

def render_target_snapshot(
    report_loc_ids: list[int],
    start_date: date,
    df: pd.DataFrame,
) -> None:
    """Render focused target and daily diagnostics without redundant views."""
    if df.empty:
        st.caption("No target data for this period.")
        return

    st.markdown("### Targets & Daily")
    st.caption(
        "Use this layer to understand target achievement and identify which days created the gap."
    )

    render_target_pace_snapshot(df)

    render_daily_target_variance(df)

    with st.expander("Best & worst target days", expanded=False):
        render_top_bottom_target_days(df)

    with st.expander("Daily target table", expanded=False):
        daily_view = build_daily_view_table(
            df=df,
            df_raw=pd.DataFrame(),
            multi_analytics=False,
            numeric=False,
        )

        if daily_view.empty:
            st.info("No daily target rows available.")
        else:
            st.dataframe(
                daily_view,
                width="stretch",
                hide_index=True,
            )


def render_overview(
    analysis_period: str,
    start_date: date,
    total_sales: float,
    avg_daily: float,
    total_covers: int,
    days_with_data: int,
    prior_total: float | None,
    prior_covers: int | None,
    prior_avg: float | None,
) -> None:
    st.markdown("### Period Summary")
    with st.container(border=True):
        show_projection = analysis_period in {"This Month", "MTD"}

        def _delta_str(current, prior):
            if prior is None or prior == 0:
                return None
            return utils.format_delta(current, prior)

        cov_delta = None
        if prior_covers is not None and prior_covers > 0:
            g = utils.calculate_growth(total_covers, prior_covers)
            sign = "+" if g["change"] >= 0 else ""
            cov_delta = (
                f"{sign}{int(g['change']):,} ({sign}{utils.format_percent(g['percentage'])})"
            )

        metrics = [
            KpiMetric(
                label="Total Sales",
                value=utils.format_rupee_short(total_sales),
                delta=_delta_str(total_sales, prior_total),
            ),
            KpiMetric(
                label="Total Covers",
                value=f"{total_covers:,}",
                delta=cov_delta,
            ),
            KpiMetric(
                label="Avg Daily Sales",
                value=utils.format_rupee_short(avg_daily),
                delta=_delta_str(avg_daily, prior_avg),
            ),
            KpiMetric(
                label="Days with Data",
                value=str(days_with_data),
            ),
        ]

        if show_projection:
            days_in_mo = utils.get_days_in_month(start_date.year, start_date.month)
            projected = utils.calculate_projected_sales(
                total_sales,
                days_with_data,
                days_in_mo,
            )
            metrics.append(
                KpiMetric(
                    label="Projected Month-End",
                    value=utils.format_rupee_short(projected),
                    help="Based on current run rate extrapolated to end of month.",
                )
            )

        kpi_row(metrics)


def render_sales_performance(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    analysis_period: str = "",
) -> None:
    show_ma_and_forecast = _period_supports_trend_analysis(analysis_period, len(df))
    forecast = None

    st.markdown("### Sales Performance")
    with st.container(border=True):
        col_chart1, col_chart2 = st.columns(2)

        # ── Daily Sales Trend ──────────────────────────────────
        with col_chart1:
            st.markdown("### Daily Sales Trend")
            if multi_analytics and not df_raw.empty:
                fig_line = go.Figure()
                for outlet_name in df_raw["Outlet"].unique():
                    odf = df_raw[df_raw["Outlet"] == outlet_name].sort_values("date")
                    hover = _fmt_rupee_hover(odf["net_total"].tolist(), outlet_name)
                    fig_line.add_trace(
                        go.Scatter(
                            x=pd.to_datetime(odf["date"]),
                            y=odf["net_total"].tolist(),
                            mode="lines+markers",
                            name=outlet_name,
                            marker=dict(size=4),
                            **hover,
                        )
                    )
                # Add 7-day MA per outlet as dashed lines
                if show_ma_and_forecast:
                    outlet_colors = {
                        trace.name: trace.line.color if hasattr(trace.line, "color") else None
                        for trace in fig_line.data
                    }
                    for outlet_name in df_raw["Outlet"].unique():
                        outlet_df = df_raw[df_raw["Outlet"] == outlet_name].sort_values("date")
                        outlet_values = outlet_df["net_total"].tolist()
                        outlet_dates = pd.to_datetime(outlet_df["date"])

                        ma_vals = moving_average(outlet_values, window=7)
                        ma_series = pd.Series(ma_vals)
                        ma_mask = pd.notna(ma_series).values
                        ma_valid = ma_series[ma_mask]
                        if not ma_valid.empty:
                            ma_color = outlet_colors.get(outlet_name, ui_theme.CHART_MA_ACCENT)
                            fig_line.add_trace(
                                go.Scatter(
                                    x=outlet_dates[ma_mask],
                                    y=ma_valid.tolist(),
                                    mode="lines",
                                    name=f"{outlet_name} 7-day Avg",
                                    line=dict(color=ma_color, width=2, dash="dash"),
                                    opacity=0.7,
                                    showlegend=False,
                                )
                            )

                        forecast_days = calculate_forecast_days(analysis_period, len(outlet_values))
                        forecast = linear_forecast(
                            outlet_dates,
                            outlet_values,
                            forecast_days=forecast_days,
                        )
                        if forecast:
                            f_dates = [f["date"] for f in forecast]
                            f_values = [f["value"] for f in forecast]
                            f_upper = [f["upper"] for f in forecast]
                            f_lower = [f["lower"] for f in forecast]

                            # Forecast line per outlet (overlay)
                            hover_fc = _fmt_rupee_hover(f_values, "Forecast")
                            fig_line.add_trace(
                                go.Scatter(
                                    x=f_dates,
                                    y=f_values,
                                    mode="lines",
                                    name=f"{outlet_name} Forecast",
                                    line=dict(color=ui_theme.BRAND_WARN, width=2, dash="dash"),
                                    opacity=0.8,
                                    showlegend=False,
                                    **hover_fc,
                                )
                            )

                            # Forecast confidence band per outlet
                            fig_line.add_trace(
                                go.Scatter(
                                    x=f_dates + f_dates[::-1],
                                    y=f_upper + f_lower[::-1],
                                    fill="toself",
                                    fillcolor=_hex_to_rgba(ui_theme.BRAND_WARN, 0.25),
                                    line=dict(color="rgba(0,0,0,0)"),
                                    name="Forecast Range",
                                    showlegend=False,
                                    hoverinfo="skip",
                                )
                            )
            else:
                dates = pd.to_datetime(df["date"])
                values = df["net_total"].tolist()

                fig_line = go.Figure()

                # Actual sales area
                hover_sales = _fmt_rupee_hover(values, "Sales")
                fig_line.add_trace(
                    go.Scatter(
                        x=dates,
                        y=values,
                        mode="lines+markers",
                        name="Daily Sales",
                        fill="tozeroy",
                        fillcolor=_hex_to_rgba(ui_theme.BRAND_PRIMARY, 0.15),
                        line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                        marker=dict(size=4),
                        **hover_sales,
                    )
                )

                # 7-day moving average (only for longer periods)
                if show_ma_and_forecast:
                    ma_values = moving_average(values, window=7)
                    ma_series = pd.Series(ma_values)
                    ma_mask = pd.notna(ma_series).values
                    ma_valid = ma_series[ma_mask]
                    if not ma_valid.empty:
                        fig_line.add_trace(
                            go.Scatter(
                                x=dates[ma_mask],
                                y=ma_valid.tolist(),
                                mode="lines",
                                name="7-day Avg",
                                line=dict(
                                    color=ui_theme.CHART_MA_ACCENT,
                                    width=2,
                                    dash="dash",
                                ),
                                opacity=0.7,
                            )
                        )

                    # Forecast
                    forecast_days = calculate_forecast_days(analysis_period, len(values))
                    forecast = linear_forecast(dates, values, forecast_days=forecast_days)
                    if forecast:
                        f_dates = [f["date"] for f in forecast]
                        f_values = [f["value"] for f in forecast]
                        f_upper = [f["upper"] for f in forecast]
                        f_lower = [f["lower"] for f in forecast]

                        # Forecast line
                        hover_fc = _fmt_rupee_hover(f_values, "Forecast")
                        fig_line.add_trace(
                            go.Scatter(
                                x=f_dates,
                                y=f_values,
                                mode="lines",
                                name="Forecast",
                                line=dict(color=ui_theme.BRAND_WARN, width=2, dash="dash"),
                                opacity=0.8,
                                **hover_fc,
                            )
                        )

                        # Forecast band
                        fig_line.add_trace(
                            go.Scatter(
                                x=f_dates + f_dates[::-1],
                                y=f_upper + f_lower[::-1],
                                fill="toself",
                                fillcolor=_hex_to_rgba(ui_theme.BRAND_WARN, 0.25),
                                line=dict(color="rgba(0,0,0,0)"),
                                name="Forecast Range",
                                showlegend=False,
                                hoverinfo="skip",
                            )
                        )

                # Compute y-axis range for nice tick labels (only in single-outlet mode)
                all_vals = values[:]
                if forecast:
                    all_vals = values + [f["value"] for f in forecast]
                y_min, y_max = 0, max(all_vals) * 1.1 if all_vals else 200_000
                tickvals, ticktext = _make_rupee_ticks(y_min, y_max)

                fig_line.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Net Sales (₹)",
                    hovermode="x unified",
                    height=ui_theme.CHART_HEIGHT,
                    xaxis=dict(tickformat="%b %d"),
                    yaxis=dict(
                        tickprefix="₹",
                        tickvals=tickvals,
                        ticktext=ticktext,
                    ),
                )

            if multi_analytics and not df_raw.empty:
                fig_line.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Net Sales (₹)",
                    hovermode="x unified",
                    height=ui_theme.CHART_HEIGHT,
                    xaxis=dict(tickformat="%b %d"),
                )
            st.plotly_chart(fig_line, width="stretch")

            # Screen reader summary
            if not multi_analytics and values:
                _chart_summary(
                    "Daily sales range from {} to {} across {} days.".format(
                        utils.format_rupee_short(min(values)),
                        utils.format_rupee_short(max(values)),
                        len(values),
                    )
                )

        # ── Covers Trend ───────────────────────────────────────
        with col_chart2:
            st.markdown("### Covers Trend")
            if multi_analytics and not df_raw.empty:
                fig_covers = go.Figure()
                for outlet_name in df_raw["Outlet"].unique():
                    outlet_df = df_raw[df_raw["Outlet"] == outlet_name].sort_values("date")
                    outlet_dates = pd.to_datetime(outlet_df["date"])
                    outlet_covers = outlet_df["covers"].tolist()

                    hover_cov = _fmt_int_hover(outlet_covers, outlet_name)
                    fig_covers.add_trace(
                        go.Bar(
                            x=outlet_dates,
                            y=outlet_covers,
                            name=outlet_name,
                            **hover_cov,
                        )
                    )

                    if show_ma_and_forecast:
                        forecast_days = calculate_forecast_days(analysis_period, len(outlet_covers))
                        forecast = linear_forecast(
                            outlet_dates,
                            outlet_covers,
                            forecast_days=forecast_days,
                        )
                        if forecast:
                            f_dates = [f["date"] for f in forecast]
                            f_values = [max(0, f["value"]) for f in forecast]
                            f_upper = [f["upper"] for f in forecast]
                            f_lower = [f["lower"] for f in forecast]

                            hover_cov_fc = _fmt_int_hover(f_values, "Forecast")
                            fig_covers.add_trace(
                                go.Scatter(
                                    x=f_dates,
                                    y=f_values,
                                    mode="lines",
                                    name=f"{outlet_name} Forecast",
                                    line=dict(
                                        color=ui_theme.BRAND_INFO,
                                        width=2,
                                        dash="dash",
                                    ),
                                    opacity=0.6,
                                    showlegend=False,
                                    **hover_cov_fc,
                                )
                            )
                            fig_covers.add_trace(
                                go.Scatter(
                                    x=f_dates + f_dates[::-1],
                                    y=f_upper + f_lower[::-1],
                                    fill="toself",
                                    fillcolor=_hex_to_rgba(ui_theme.BRAND_INFO, 0.25),
                                    line=dict(color="rgba(0,0,0,0)"),
                                    name="Forecast Range",
                                    showlegend=False,
                                    hoverinfo="skip",
                                )
                            )
            else:
                dates = pd.to_datetime(df["date"])
                covers = df["covers"].tolist()

                fig_covers = go.Figure()

                # Actual covers area
                hover_cov = _fmt_int_hover(covers, "Covers")
                fig_covers.add_trace(
                    go.Scatter(
                        x=dates,
                        y=covers,
                        mode="lines+markers",
                        name="Covers",
                        fill="tozeroy",
                        fillcolor=_hex_to_rgba(ui_theme.BRAND_SUCCESS, 0.15),
                        line=dict(color=ui_theme.BRAND_SUCCESS, width=2),
                        marker=dict(size=4),
                        **hover_cov,
                    )
                )

                # Forecast area (only for longer periods)
                if show_ma_and_forecast:
                    forecast_days = calculate_forecast_days(analysis_period, len(covers))
                    forecast = linear_forecast(dates, covers, forecast_days=forecast_days)
                    if forecast:
                        f_dates = [f["date"] for f in forecast]
                        f_values = [max(0, f["value"]) for f in forecast]
                        hover_cov_fc = _fmt_int_hover(f_values, "Forecast")
                        fig_covers.add_trace(
                            go.Scatter(
                                x=f_dates,
                                y=f_values,
                                mode="lines",
                                name="Forecast",
                                fill="tozeroy",
                                fillcolor=_hex_to_rgba(ui_theme.BRAND_INFO, 0.15),
                                line=dict(color=ui_theme.BRAND_INFO, width=2, dash="dash"),
                                opacity=0.6,
                                **hover_cov_fc,
                            )
                        )

            fig_covers.update_layout(
                xaxis_title="Date",
                yaxis_title="Covers",
                hovermode="x unified",
                height=ui_theme.CHART_HEIGHT,
                barmode="group",
                xaxis=dict(tickformat="%b %d"),
            )
            st.plotly_chart(fig_covers, width="stretch")

            # Screen reader summary
            if not multi_analytics and covers:
                _chart_summary(
                    "Daily covers range from {:,} to {:,} with an average of {:,}.".format(
                        min(covers),
                        max(covers),
                        sum(covers) // len(covers),
                    )
                )

        # ── APC Trend ──────────────────────────────────────────
        st.markdown("### Average Per Cover (APC) Trend")
        apc_df = df[df["apc"] > 0].copy() if "apc" in df.columns else pd.DataFrame()
        if not apc_df.empty:
            fig_apc = px.line(
                apc_df,
                x="date",
                y="apc",
                markers=True,
                title="APC over time",
            )
            fig_apc.update_traces(line_color=ui_theme.BRAND_PRIMARY)
            avg_apc = float(apc_df["apc"].mean())
            fig_apc.add_hline(
                y=avg_apc,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Avg {utils.format_currency(avg_apc)}",
                annotation_position="top right",
            )
            fig_apc.update_layout(
                xaxis_title="Date",
                yaxis_title="APC (₹)",
                yaxis=dict(rangemode="tozero"),
                hovermode="x unified",
                height=ui_theme.CHART_HEIGHT,
                xaxis=dict(tickformat="%b %d"),
            )
            st.plotly_chart(fig_apc, width="stretch")
            _chart_summary(
                "Average per cover is {} across {} days with data.".format(
                    utils.format_currency(avg_apc),
                    len(apc_df),
                )
            )
        else:
            st.caption("No APC data for this period.")

        # ── Sales Performance drill-down table ───────────────────
        with st.container(border=True):
            st.caption("Sales performance table")
            if multi_analytics and not df_raw.empty:
                _sales_tbl = df_raw[["date", "Outlet", "net_total", "covers"]].copy()
            else:
                _sales_tbl = df[["date", "net_total", "covers"]].copy()
            if "apc" in df.columns:
                if multi_analytics and not df_raw.empty:
                    _sales_tbl["apc"] = _sales_tbl.apply(
                        lambda r: r["net_total"] / r["covers"] if r["covers"] > 0 else 0,
                        axis=1,
                    )
                else:
                    _sales_tbl["apc"] = df["apc"]
            else:
                _sales_tbl["apc"] = _sales_tbl.apply(
                    lambda r: r["net_total"] / r["covers"] if r["covers"] > 0 else 0,
                    axis=1,
                )
            _sales_tbl = _sales_tbl.rename(
                columns={
                    "date": "Date",
                    "net_total": "Net Sales (₹)",
                    "covers": "Covers",
                    "apc": "APC (₹)",
                }
            )
            if "Outlet" in _sales_tbl.columns:
                _sales_tbl = _sales_tbl.sort_values(["Date", "Outlet"])
            else:
                _sales_tbl = _sales_tbl.sort_values("Date")
            _sales_tbl["Net Sales (₹)"] = _sales_tbl["Net Sales (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            _sales_tbl["APC (₹)"] = _sales_tbl["APC (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            _sales_tbl["Covers"] = _sales_tbl["Covers"].apply(lambda x: f"{int(x):,}")
            st.dataframe(_sales_tbl, width="stretch", hide_index=True)


def render_revenue_breakdown(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
    df: pd.DataFrame,
    start_date: date,
) -> None:
    # ── Category Mix ───────────────────────────────────────────
    st.markdown("### Category Mix")
    cat_data = database.get_category_sales_for_date_range(report_loc_ids, start_str, end_str)
    if cat_data:
        cat_df = pd.DataFrame(cat_data)
        total_cat = float(cat_df["amount"].sum())

        # Group categories <2% into "Other"
        cat_df["pct"] = cat_df["amount"] / total_cat * 100 if total_cat > 0 else 0
        small_cats = cat_df[cat_df["pct"] < 2]
        large_cats = cat_df[cat_df["pct"] >= 2].copy()
        if not small_cats.empty:
            other_amount = float(small_cats["amount"].sum())
            other_qty = int(small_cats["qty"].sum())
            other_row = pd.DataFrame(
                [
                    {
                        "category": "Other",
                        "amount": other_amount,
                        "qty": other_qty,
                        "pct": other_amount / total_cat * 100 if total_cat > 0 else 0,
                    }
                ]
            )
            chart_df = pd.concat([large_cats, other_row], ignore_index=True)
        else:
            chart_df = large_cats.copy()

        fig_cat = go.Figure(
            go.Treemap(
                labels=chart_df["category"].tolist(),
                values=chart_df["amount"].tolist(),
                parents=[""] * len(chart_df),
                marker=dict(
                    colors=[
                        ui_theme.CHART_COLORWAY[i % len(ui_theme.CHART_COLORWAY)]
                        for i in range(len(chart_df))
                    ]
                ),
                textinfo="label+percent entry",
            )
        )
        fig_cat.update_layout(
            title=f"Category revenue mix (Total: {utils.format_rupee_short(total_cat)})",
            height=400,
        )

        st.plotly_chart(fig_cat, width="stretch")

        # Full category breakdown table
        _cat_table = cat_df[["category", "amount"]].copy()
        _cat_table["% of Total"] = _cat_table["amount"].apply(
            lambda x: f"{x / total_cat * 100:.1f}%" if total_cat > 0 else "0%"
        )
        _cat_table["amount"] = _cat_table["amount"].apply(lambda x: utils.format_currency(float(x)))
        _cat_table = _cat_table.rename(columns={"category": "Category", "amount": "Amount"})
        with st.container(border=True):
            st.caption("Category data")
            st.dataframe(_cat_table, width="stretch", hide_index=True)
    else:
        st.caption("No category data for this period.")

    # ── Weekday Analysis ───────────────────────────────────────
    # Only meaningful for periods spanning at least 7 days
    if len(df) >= 7:
        st.markdown("### Weekday Analysis")
        wd_df = df[df["net_total"] > 0].copy()
        wd_df["weekday"] = wd_df["date"].apply(utils.get_weekday_name)
        wd_agg = (
            wd_df.groupby("weekday")["net_total"]
            .mean()
            .reset_index()
            .rename(columns={"net_total": "avg_sales"})
        )
        day_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        wd_agg["weekday"] = pd.Categorical(wd_agg["weekday"], categories=day_order, ordered=True)
        wd_agg = wd_agg.sort_values("weekday")
        monthly_tgt = scope.sum_location_monthly_targets(report_loc_ids)
        if monthly_tgt > 0 and len(report_loc_ids) == 1:
            recent = database.get_recent_summaries(report_loc_ids[0], weeks=8)
            weekday_mix = utils.compute_weekday_mix(recent)
            day_targets = utils.compute_day_targets(monthly_tgt, weekday_mix)
            daily_tgt = sum(day_targets.values()) / len(day_targets)
        else:
            days_in_mo = utils.get_days_in_month(start_date.year, start_date.month)
            daily_tgt = monthly_tgt / days_in_mo if monthly_tgt > 0 else 0

        if wd_agg.empty:
            st.caption("No positive-sales days available for weekday analysis.")
            return

        # Best/worst day identification for conditional coloring
        best_idx = wd_agg["avg_sales"].idxmax()
        worst_idx = wd_agg["avg_sales"].idxmin()
        wd_colors = []
        for i in range(len(wd_agg)):
            if i == best_idx:
                wd_colors.append(ui_theme.CHART_POSITIVE)
            elif i == worst_idx:
                wd_colors.append(ui_theme.CHART_NEGATIVE)
            else:
                wd_colors.append(ui_theme.CHART_NEUTRAL)

        wd_patterns = [
            "✓" if v >= daily_tgt else "⚠" if v >= daily_tgt * 0.8 else "✗"
            for v in wd_agg["avg_sales"]
        ]
        fig_wd = px.bar(
            wd_agg,
            x="weekday",
            y="avg_sales",
            title="Average net sales by day of week",
            text=wd_patterns,
        )
        fig_wd.update_traces(
            marker_color=wd_colors,
            textposition="outside",
            textfont=dict(size=14, color=ui_theme.TEXT_PRIMARY),
        )
        if daily_tgt > 0:
            fig_wd.add_hline(
                y=daily_tgt,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Daily target {utils.format_rupee_short(daily_tgt)}",
                annotation_position="top right",
            )

        # Best/worst day annotations
        best_day = wd_agg.loc[best_idx, "weekday"]
        best_val = wd_agg.loc[best_idx, "avg_sales"]
        worst_day = wd_agg.loc[worst_idx, "weekday"]
        worst_val = wd_agg.loc[worst_idx, "avg_sales"]
        fig_wd.add_annotation(
            x=best_day,
            y=best_val,
            text=f"Best: {best_day}",
            showarrow=True,
            arrowhead=2,
            bgcolor=ui_theme.BRAND_SUCCESS,
            font_color="white",
        )
        fig_wd.add_annotation(
            x=worst_day,
            y=worst_val,
            text=f"Worst: {worst_day}",
            showarrow=True,
            arrowhead=2,
            bgcolor=ui_theme.BRAND_ERROR,
            font_color="white",
        )

        fig_wd.update_layout(
            xaxis_title="",
            yaxis_title="Avg Net Sales (₹)",
            height=ui_theme.CHART_HEIGHT,
        )
        st.plotly_chart(fig_wd, width="stretch")
        _chart_summary(
            "Best day is {} (avg {}) and worst is {} (avg {}).".format(
                best_day,
                utils.format_rupee_short(best_val),
                worst_day,
                utils.format_rupee_short(worst_val),
            )
        )

        # Weekday drill-down table
        with st.container(border=True):
            st.caption("Weekday data")
            wd_covers = (
                wd_df.groupby("weekday")["covers"]
                .mean()
                .reset_index()
                .rename(columns={"covers": "avg_covers"})
            )
            wd_count = (
                wd_df.groupby("weekday")["net_total"]
                .count()
                .reset_index()
                .rename(columns={"net_total": "count_days"})
            )
            wd_table = wd_agg.merge(wd_covers, on="weekday", how="left").merge(
                wd_count, on="weekday", how="left"
            )
            wd_table["weekday"] = pd.Categorical(
                wd_table["weekday"], categories=day_order, ordered=True
            )
            wd_table = wd_table.sort_values("weekday")
            wd_table = wd_table.rename(
                columns={
                    "weekday": "Day of Week",
                    "avg_sales": "Avg Net Sales (₹)",
                    "avg_covers": "Avg Covers",
                    "count_days": "Count of Days",
                }
            )
            wd_table["Avg Net Sales (₹)"] = wd_table["Avg Net Sales (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            wd_table["Avg Covers"] = wd_table["Avg Covers"].apply(lambda x: f"{float(x):.0f}")
            st.dataframe(
                wd_table[["Day of Week", "Avg Net Sales (₹)", "Avg Covers", "Count of Days"]],
                width="stretch",
                hide_index=True,
            )
    else:
        st.caption("Need at least 7 days of data for weekday analysis.")


def render_target_and_daily(
    report_loc_ids: list[int],
    start_date: date,
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    analysis_period: str = "",
) -> None:
    monthly_target = scope.sum_location_monthly_targets(report_loc_ids)
    is_monthly_period = analysis_period in {"This Month", "Last Month", "Custom"}
    if monthly_target > 0 and is_monthly_period:
        st.markdown("### Target Achievement")
        days_in_month = utils.get_days_in_month(start_date.year, start_date.month)

        weekday_mix: dict = {}
        day_targets: dict = {}
        if len(report_loc_ids) == 1:
            recent = database.get_recent_summaries(report_loc_ids[0], weeks=8)
            weekday_mix = utils.compute_weekday_mix(recent)
            day_targets = utils.compute_day_targets(monthly_target, weekday_mix)

        fig_target = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=["Daily Achievement %", "Cumulative vs Target"],
            specs=[[{"type": "bar"}, {"type": "scatter"}]],
        )

        target_df = df.copy()
        if day_targets:
            target_df["day_target"] = target_df["date"].apply(
                lambda d: utils.get_target_for_date(day_targets, str(d))
            )
            target_df["achievement"] = target_df.apply(
                lambda r: r["net_total"] / r["day_target"] * 100 if r["day_target"] > 0 else 0,
                axis=1,
            )
        else:
            daily_target = monthly_target / days_in_month
            target_df["achievement"] = (
                target_df["net_total"] / daily_target * 100 if daily_target > 0 else 0
            )
        colors = [
            ui_theme.BRAND_SUCCESS
            if x >= 100
            else ui_theme.BRAND_WARN
            if x >= 80
            else ui_theme.BRAND_ERROR
            for x in target_df["achievement"]
        ]
        fig_target.add_trace(
            go.Bar(
                x=target_df["date"],
                y=target_df["achievement"],
                marker_color=colors,
                name="Achievement %",
            ),
            row=1,
            col=1,
        )

        df_sorted = target_df.sort_values("date")
        df_sorted["cumulative"] = df_sorted["net_total"].cumsum()
        target_line = [monthly_target * (i / len(df_sorted)) for i in range(1, len(df_sorted) + 1)]

        # Determine fill color based on on-track status
        actual_last = df_sorted["cumulative"].iloc[-1]
        target_last = target_line[-1]
        fill_color = (
            _hex_to_rgba(ui_theme.BRAND_SUCCESS, 0.2)
            if actual_last >= target_last
            else _hex_to_rgba(ui_theme.BRAND_ERROR, 0.2)
        )

        fig_target.add_trace(
            go.Scatter(
                x=df_sorted["date"],
                y=df_sorted["cumulative"],
                mode="lines+markers",
                name="Actual",
                fill="tozeroy",
                fillcolor=fill_color,
            ),
            row=1,
            col=2,
        )
        fig_target.add_trace(
            go.Scatter(
                x=df_sorted["date"],
                y=target_line,
                mode="lines",
                name="Target",
                line=dict(dash="dash", color="gray"),
            ),
            row=1,
            col=2,
        )

        # Projected month-end extension
        last_date = pd.Timestamp(df_sorted["date"].iloc[-1])
        month_end = pd.Timestamp(start_date.replace(day=days_in_month))
        if last_date < month_end and len(df_sorted) >= 3:
            cum_values = df_sorted["cumulative"].tolist()
            cum_dates = pd.to_datetime(df_sorted["date"])
            forecast = linear_forecast(cum_dates, cum_values, forecast_days=5)
            if forecast:
                f_dates = [f["date"] for f in forecast if f["date"] <= month_end]
                f_values = [f["value"] for f in forecast if f["date"] <= month_end]
                if f_dates:
                    fig_target.add_trace(
                        go.Scatter(
                            x=f_dates,
                            y=f_values,
                            mode="lines",
                            name="Projected",
                            line=dict(dash="dot", color=ui_theme.BRAND_PRIMARY),
                            opacity=0.6,
                        ),
                        row=1,
                        col=2,
                    )

        fig_target.update_layout(height=ui_theme.CHART_HEIGHT, showlegend=True)
        st.plotly_chart(fig_target, width="stretch")

        # On-track / Behind badge
        if actual_last >= target_last:
            st.success(
                "✅ **On track** — "
                f"{utils.format_rupee_short(actual_last - target_last)} "
                "ahead of target pace"
            )
        else:
            st.error(
                "⚠️ **Behind by "
                f"{utils.format_rupee_short(target_last - actual_last)}"
                "** — below target pace"
            )

        _chart_summary(
            "Cumulative sales are {} vs target pace of {}.".format(
                utils.format_rupee_short(actual_last),
                utils.format_rupee_short(target_last),
            )
        )

        # Target achievement drill-down table
        with st.container(border=True):
            st.caption("Target achievement data")
            _cols_needed = {"target", "pct_target"}
            _has_target_cols = (
                multi_analytics and not df_raw.empty and _cols_needed.issubset(df_raw.columns)
            )

            if _has_target_cols:
                _tgt_tbl = df_raw[["date", "Outlet", "net_total", "target", "pct_target"]].copy()
                _tgt_tbl["pct_target"] = _tgt_tbl["pct_target"].apply(
                    lambda x: f"{float(x or 0):.2f}%"
                )
            else:
                _target_col = "day_target" if "day_target" in target_df.columns else None
                _cols = ["date", "net_total"]
                if _target_col:
                    _cols.extend([_target_col, "achievement"])
                else:
                    _cols.append("achievement")
                _tgt_tbl = target_df[_cols].copy()
                _tgt_tbl["achievement"] = _tgt_tbl["achievement"].apply(
                    lambda x: f"{float(x or 0):.2f}%"
                )
                if _target_col:
                    _tgt_tbl = _tgt_tbl.rename(columns={_target_col: "target"})
                _tgt_tbl = _tgt_tbl.rename(columns={"achievement": "pct_target"})

            _rename_cols = {
                "date": "Date",
                "net_total": "Net Sales (₹)",
                "pct_target": "Achievement",
            }
            if "target" in _tgt_tbl.columns:
                _rename_cols["target"] = "Target (₹)"
            _tgt_tbl = _tgt_tbl.rename(columns=_rename_cols)
            _tgt_tbl["Net Sales (₹)"] = _tgt_tbl["Net Sales (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            if "Target (₹)" in _tgt_tbl.columns:
                _tgt_tbl["Target (₹)"] = _tgt_tbl["Target (₹)"].apply(
                    lambda x: utils.format_currency(float(x))
                )
            st.dataframe(_tgt_tbl, width="stretch", hide_index=True)

        st.markdown("### Daily Data")
        dv = build_daily_view_table(df, df_raw, multi_analytics, numeric=True)

        dv_display = dv.copy()
        _is_multi_table = "Outlet" in dv_display.columns
        rename_map = {
            "date": "Date",
            "covers": "Covers",
            "net_total": "Net Sales (₹)",
            "target": "Target (₹)",
            "pct_target": "Achievement %",
        }
        if _is_multi_table:
            rename_map["Outlet"] = "Outlet"
        dv_display = dv_display.rename(columns=rename_map)

        styler = dv_display.style.map(_style_achievement, subset=["Achievement %"]).format(
            {
                "Covers": "{:,.0f}",
                "Net Sales (₹)": lambda x: utils.format_indian_currency(float(x)),
                "Target (₹)": lambda x: utils.format_indian_currency(float(x)),
                "Achievement %": "{:.2f}%",
            },
            na_rep="",
        )
        # Bold the total row
        _total_row_idx_multi = len(dv_display) - 1
        styler = styler.set_properties(
            subset=pd.IndexSlice[_total_row_idx_multi, :],
            **{"font-weight": "bold"},
        )
        st.dataframe(styler, width="stretch", hide_index=True)
    else:
        daily_view = build_daily_view_table(df, pd.DataFrame(), multi_analytics=False, numeric=True)

        dv_display = daily_view.rename(
            columns={
                "date": "Date",
                "covers": "Covers",
                "net_total": "Net Sales (₹)",
                "target": "Target (₹)",
                "pct_target": "Achievement %",
            }
        )
        styler = dv_display.style.map(_style_achievement, subset=["Achievement %"]).format(
            {
                "Covers": "{:,.0f}",
                "Net Sales (₹)": lambda x: utils.format_indian_currency(float(x)),
                "Target (₹)": lambda x: utils.format_indian_currency(float(x)),
                "Achievement %": "{:.2f}%",
            },
            na_rep="",
        )
        _total_row_idx = len(dv_display) - 1
        styler = styler.set_properties(
            subset=pd.IndexSlice[_total_row_idx, :],
            **{"font-weight": "bold"},
        )
        st.dataframe(styler, width="stretch", hide_index=True)


def render_payment_reconciliation(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
) -> None:
    """Render payment summary, Zomato Pay economics, risks, and reconciliation downloads."""
    from io import BytesIO

    import database_analytics

    st.markdown("### Payment Reconciliation")
    st.caption(
        "Use this layer to reconcile payment settlements, identify provider concentration, and review Zomato Pay economics."
    )

    data = database_analytics.get_payment_provider_breakdown(
        report_loc_ids,
        start_str,
        end_str,
    )

    if not data:
        st.caption("No payment data for this period.")
        return

    recon_df = pd.DataFrame(data)

    if recon_df.empty or "gross_amount" not in recon_df.columns:
        st.caption("No usable payment data for this period.")
        return

    recon_df["gross_amount"] = pd.to_numeric(
        recon_df["gross_amount"],
        errors="coerce",
    ).fillna(0)

    total_gross = float(recon_df["gross_amount"].sum())

    if "txn_count" in recon_df.columns:
        recon_df["txn_count"] = pd.to_numeric(
            recon_df["txn_count"],
            errors="coerce",
        ).fillna(0)
    else:
        recon_df["txn_count"] = 0

    has_txn_count = recon_df["txn_count"].sum() > 0

    recon_df["% of Total"] = recon_df["gross_amount"].apply(
        lambda value: f"{value / total_gross * 100:.1f}%" if total_gross > 0 else "0.0%"
    )

    provider_count = int(recon_df["provider"].nunique()) if "provider" in recon_df.columns else 0
    top_provider = "N/A"
    top_provider_share = 0.0

    if "provider" in recon_df.columns and total_gross > 0:
        provider_summary = (
            recon_df.groupby("provider", as_index=False)["gross_amount"]
            .sum()
            .sort_values("gross_amount", ascending=False)
        )

        if not provider_summary.empty:
            top_provider = str(provider_summary.iloc[0]["provider"])
            top_provider_share = float(provider_summary.iloc[0]["gross_amount"] / total_gross * 100)

    summary_metrics = [
        KpiMetric(
            label="Total Gross",
            value=utils.format_currency(total_gross),
        ),
        KpiMetric(
            label="Payment Providers",
            value=f"{provider_count:,}",
        ),
        KpiMetric(
            label="Top Provider",
            value=top_provider,
            delta=f"{top_provider_share:.1f}% of gross" if top_provider_share > 0 else None,
        ),
    ]

    if has_txn_count:
        summary_metrics.append(
            KpiMetric(
                label="Total Bills",
                value=f"{int(recon_df['txn_count'].sum()):,}",
            )
        )

    kpi_row(summary_metrics, columns=min(len(summary_metrics), 4))

    display_df = recon_df.copy()
    display_df = display_df.rename(columns={"provider": "Provider"})

    display_df["Gross Amount ₹"] = display_df["gross_amount"].apply(
        lambda value: utils.format_currency(float(value))
    )

    cols_to_show = ["Provider", "Gross Amount ₹", "% of Total"]

    if has_txn_count:
        display_df["Bills"] = display_df["txn_count"].apply(lambda value: f"{int(value):,}")
        cols_to_show = ["Provider", "Bills", "Gross Amount ₹", "% of Total"]

    with st.container(border=True):
        st.markdown("#### Payment Summary")
        st.caption(
            "Provider-level payment view for checking settlement concentration and reconciling against payment statements."
        )
        st.dataframe(
            display_df[cols_to_show],
            width="stretch",
            hide_index=True,
        )

    zomato_pay_sales = 0.0
    if "provider" in recon_df.columns:
        zomato_pay_sales = float(
            recon_df[
                recon_df["provider"]
                .astype(str)
                .str.contains("zomato", case=False, na=False)
            ]["gross_amount"].sum()
        )

    render_zomato_economics(zomato_pay_sales)

    with st.expander("Exceptions / Risks", expanded=False):
        risk_messages = []

        if total_gross <= 0:
            risk_messages.append("Total payment gross is zero for the selected period.")

        if provider_count <= 1:
            risk_messages.append(
                "Only one payment provider is visible. Check whether payment labels are being grouped too broadly."
            )

        if top_provider_share >= 80:
            risk_messages.append(
                f"{top_provider} contributes {top_provider_share:.1f}% of payment gross. Verify this concentration against settlement reports."
            )

        if has_txn_count and (recon_df["txn_count"] <= 0).any():
            risk_messages.append(
                "One or more payment providers have zero bills. Check whether bill counts are missing or incorrectly mapped."
            )

        if zomato_pay_sales <= 0:
            risk_messages.append(
                "No Zomato Pay sales are visible in this period. This is fine if Zomato Pay was inactive, but verify if it should have been active."
            )

        if not risk_messages:
            st.success("No major payment reconciliation risk detected from the available payment summary.")

        for message in risk_messages:
            st.warning(message)

    with st.expander("Full payment table and downloads", expanded=False):
        export_df = recon_df[["provider", "txn_count", "gross_amount", "% of Total"]].copy()
        export_df = export_df.rename(
            columns={
                "provider": "Provider",
                "txn_count": "Bill Count",
                "gross_amount": "Gross Amount",
            }
        )

        table_df = export_df.copy()
        table_df["Gross Amount"] = table_df["Gross Amount"].apply(
            lambda value: utils.format_currency(float(value))
        )
        table_df["Bill Count"] = table_df["Bill Count"].apply(
            lambda value: f"{int(value):,}"
        )

        st.dataframe(table_df, width="stretch", hide_index=True)

        download_col_1, download_col_2 = st.columns(2)

        with download_col_1:
            csv_bytes = export_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download CSV",
                data=csv_bytes,
                file_name=f"payment_recon_{start_str}_{end_str}.csv",
                mime="text/csv",
                key="recon_csv_btn",
            )

        with download_col_2:
            excel_buf = BytesIO()
            with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
                export_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Payment Reconciliation",
                )
            excel_buf.seek(0)

            st.download_button(
                label="Download Excel",
                data=excel_buf.getvalue(),
                file_name=f"payment_recon_{start_str}_{end_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="recon_excel_btn",
            )
def render_zomato_economics(zomato_pay_sales: float) -> None:
    """Render manual Zomato Pay incrementality economics for the selected period."""
    st.markdown("### Zomato Economics")

    if zomato_pay_sales <= 0:
        st.caption("No Zomato Pay sales in this period.")
        return

    st.caption(
        "Owner decision model: estimate how much Zomato Pay sales were truly incremental, "
        "then check whether the contribution after food/direct variable costs covers the Zomato Pay fee."
    )

    with st.container(border=True):
        input_cols = st.columns(4)

        with input_cols[0]:
            fee_pct = st.number_input(
                "Zomato fee %",
                min_value=0.0,
                max_value=100.0,
                value=5.9,
                step=0.1,
                key="zomato_fee_pct",
                help="The commission or fee charged on Zomato Pay sales for this period.",
            )

        with input_cols[1]:
            contribution_margin_pct = st.number_input(
                "Incremental contribution margin %",
                min_value=0.0,
                max_value=100.0,
                value=60.0,
                step=1.0,
                key="zomato_contribution_margin_pct",
                help=(
                    "Money retained from estimated extra Zomato-driven sales after food and direct "
                    "variable costs, before rent, fixed salaries, and other existing fixed costs. "
                    "Example: if food cost is 33%, a conservative contribution margin may be around 55–60%."
                ),
            )

        with input_cols[2]:
            incremental_sales_pct = st.number_input(
                "Assumed incremental sales %",
                min_value=0.0,
                max_value=100.0,
                value=15.0,
                step=1.0,
                key="zomato_incremental_sales_pct",
                help=(
                    "The percentage of Zomato Pay sales that you believe were truly extra sales "
                    "because of Zomato. Example: 15% means you assume 15% of Zomato Pay sales "
                    "would not have happened without Zomato."
                ),
            )

        with input_cols[3]:
            target_coverage_ratio = st.number_input(
                "Target coverage ratio",
                min_value=0.0,
                value=1.5,
                step=0.1,
                key="zomato_target_coverage_ratio",
                help=(
                    "1.0x means break-even. 1.5x means the incremental contribution should be "
                    "50% higher than the Zomato Pay fee."
                ),
            )

        incremental_sales = zomato_pay_sales * incremental_sales_pct / 100

        economics = build_zomato_economics(
            zomato_pay_sales=zomato_pay_sales,
            fee_pct=fee_pct,
            contribution_margin_pct=contribution_margin_pct,
            incremental_sales=incremental_sales,
            target_coverage_ratio=target_coverage_ratio,
        )

        coverage = classify_platform_cost_coverage(economics["coverage_ratio"])

        st.caption(
            f"Current assumption: {incremental_sales_pct:.1f}% of "
            f"{utils.format_rupee_short(economics['zomato_pay_sales'] or 0)} Zomato Pay sales "
            f"= {utils.format_rupee_short(economics['incremental_sales'] or 0)} estimated incremental sales."
        )

        kpi_row(
            [
                KpiMetric(
                    label="Zomato Pay Sales",
                    value=utils.format_rupee_short(economics["zomato_pay_sales"] or 0),
                ),
                KpiMetric(
                    label=f"Zomato Pay Fee Cost @ {fee_pct:.1f}%",
                    value=utils.format_rupee_short(economics["platform_cost"] or 0),
                ),
                KpiMetric(
                    label="Estimated Incremental Sales",
                    value=utils.format_rupee_short(economics["incremental_sales"] or 0),
                ),
                KpiMetric(
                    label="Incremental Contribution",
                    value=utils.format_rupee_short(economics["incremental_contribution"] or 0),
                ),
                KpiMetric(
                    label="Coverage Ratio",
                    value=_format_ratio(economics["coverage_ratio"]),
                ),
            ]
        )

        break_even_sales = economics["break_even_incremental_sales"] or 0
        target_sales = economics["target_incremental_sales"] or 0

        break_even_pct = (
            break_even_sales / zomato_pay_sales * 100
            if zomato_pay_sales > 0
            else 0
        )

        target_pct = (
            target_sales / zomato_pay_sales * 100
            if zomato_pay_sales > 0
            else 0
        )

        decision_label = "Healthy channel" if coverage["label"] == "Healthy" else coverage["label"]

        decision_text = (
            f"**{decision_label}**  \n"
            f"{coverage['message']}  \n\n"
            f"Break-even incremental sales needed: "
            f"{utils.format_rupee_short(break_even_sales)} "
            f"({break_even_pct:.1f}% of Zomato Pay sales)  \n"
            f"Sales needed for {target_coverage_ratio:.1f}x target: "
            f"{utils.format_rupee_short(target_sales)} "
            f"({target_pct:.1f}% of Zomato Pay sales)  \n"
            f"Current estimate: "
            f"{utils.format_rupee_short(economics['incremental_sales'] or 0)} "
            f"({incremental_sales_pct:.1f}% of Zomato Pay sales)"
        )

        if coverage["severity"] == "success":
            st.success(decision_text)
        elif coverage["severity"] == "warning":
            st.warning(decision_text)
        elif coverage["severity"] == "error":
            st.error(decision_text)
        else:
            st.info(decision_text)

        sensitivity_pcts = sorted(
            set([5.0, 10.0, 15.0, 25.0, 35.0, 50.0, round(incremental_sales_pct, 1)])
        )

        sensitivity_rows = []

        for pct in sensitivity_pcts:
            assumed_sales = zomato_pay_sales * pct / 100

            assumed = build_zomato_economics(
                zomato_pay_sales=zomato_pay_sales,
                fee_pct=fee_pct,
                contribution_margin_pct=contribution_margin_pct,
                incremental_sales=assumed_sales,
                target_coverage_ratio=target_coverage_ratio,
            )

            assumed_coverage = classify_platform_cost_coverage(assumed["coverage_ratio"])

            sensitivity_rows.append(
                {
                    "Incremental Assumption": f"{pct:g}% of Zomato Pay",
                    "Incremental Sales": utils.format_rupee_short(assumed_sales),
                    f"Contribution @ {contribution_margin_pct:.0f}%": utils.format_rupee_short(
                        assumed["incremental_contribution"] or 0
                    ),
                    "Coverage Ratio": _format_ratio(assumed["coverage_ratio"]),
                    "Decision": assumed_coverage["label"],
                }
            )

        st.dataframe(
            pd.DataFrame(sensitivity_rows),
            width="stretch",
            hide_index=True,
        )
