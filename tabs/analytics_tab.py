"""Analytics tab — Period selector, charts, and daily data table."""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Dict, List

import pandas as pd
import streamlit as st

import cache_manager
import config
import database
import scope
import utils
from components import classed_container, page_shell
from components.feedback import empty_state
from components.navigation import date_range_nav
from tabs import TabContext
from tabs.analytics_logic import resolve_period_window
from tabs.analytics_sections import (
    render_action_tracker,
    render_category_quality_layer,
    render_driver_analysis,
    render_forecast_command_center,
    render_mix_snapshot,
    render_outlet_performance_scorecard,
    render_owner_readout_and_data_confidence,
    render_payment_reconciliation,
    render_required_sales_plan,
    render_sales_movement_waterfall,
    render_sales_quality_layer,
    render_target_snapshot,
)

# In-process cache registered with cache_manager for coordinated invalidation
_RAW_SUMMARY_CACHE: dict = cache_manager.register("analytics_raw")


def clear_analytics_cache() -> None:
    """Clear cached analytics raw summaries."""
    cache_manager.invalidate("analytics_raw")


def _add_target_columns(
    df: pd.DataFrame,
    all_locs: list,
    location_ids: list,
) -> pd.DataFrame:
    """Add target and pct_target columns to a summaries DataFrame.

    Args:
        df: DataFrame with 'location_id', 'date', 'net_total' columns
        all_locs: List of all location dicts from database
        location_ids: List of location IDs being analyzed

    Returns:
        DataFrame with added 'target' and 'pct_target' columns
    """
    if df.empty:
        return df

    df = df.copy()

    loc_settings = {loc["id"]: loc for loc in all_locs}

    loc_monthly_target: dict = {}
    loc_weekday_mix: dict = {}
    loc_day_targets: dict = {}

    for lid in location_ids:
        settings = loc_settings.get(lid, {})
        monthly_target = float(settings.get("target_monthly_sales", 0) or 0)
        if monthly_target <= 0:
            monthly_target = float(config.MONTHLY_TARGET)
        loc_monthly_target[lid] = monthly_target

        recent = database.get_recent_summaries(lid, weeks=8)
        weekday_mix = utils.compute_weekday_mix(recent)
        loc_weekday_mix[lid] = weekday_mix

        day_targets = utils.compute_day_targets(monthly_target, weekday_mix)
        loc_day_targets[lid] = day_targets

    # Vectorized target lookup. Per-row .apply is slow on large date ranges;
    # parse the date column once and join via a (location_id, weekday) key.
    parsed = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
    weekday_names = parsed.dt.weekday.map(
        lambda i: utils.WEEKDAY_NAMES[int(i)] if pd.notna(i) else None
    )
    target_lookup: Dict[tuple, float] = {
        (lid, wd): float(val)
        for lid, day_targets in loc_day_targets.items()
        for wd, val in (day_targets or {}).items()
    }
    keys = list(
        zip(
            df["location_id"].tolist(),
            weekday_names.tolist(),
            strict=False,
        )
    )
    df["target"] = pd.Series(
        [target_lookup.get(k, 0.0) for k in keys], index=df.index
    )

    target = pd.to_numeric(df["target"], errors="coerce").fillna(0.0)
    net = pd.to_numeric(df["net_total"], errors="coerce").fillna(0.0)
    pct = (net.divide(target.where(target > 0)) * 100).fillna(0.0).round(2)
    df["pct_target"] = pct

    return df


def _load_raw_summaries_cached(
    location_ids: List[int], start_str: str, end_str: str
) -> List[Dict]:
    key = (tuple(location_ids or []), start_str, end_str)
    if key in _RAW_SUMMARY_CACHE:
        return _RAW_SUMMARY_CACHE[key]
    if not location_ids:
        raw = []
    else:
        raw = database.get_summaries_for_date_range_multi(
            location_ids, start_str, end_str
        )
    _RAW_SUMMARY_CACHE[key] = raw
    return raw


def _format_comparison_delta(value: float | None) -> str:
    """Format a comparison delta for compact KPI cards."""
    return "N/A" if value is None else f"{value:+.1f}%"


def _html(value: object) -> str:
    """Escape dynamic text for custom Analytics HTML."""
    return escape(str(value), quote=True)


def _delta_tone(value: float | None) -> str:
    """Return a CSS tone suffix for numeric KPI movement."""
    if value is None:
        return "neutral"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _kpi_item_html(
    label: str,
    value: str,
    delta: str | None = None,
    tone: str = "neutral",
) -> str:
    """Build a single KPI tile for the executive KPI summary."""
    delta_html = ""
    if delta:
        delta_html = (
            f'<div class="analytics-kpi-delta analytics-kpi-delta--{_html(tone)}">'
            f"{_html(delta)}</div>"
        )

    return (
        '<div class="analytics-kpi-item">'
        f'<div class="analytics-kpi-label">{_html(label)}</div>'
        f'<div class="analytics-kpi-value">{_html(value)}</div>'
        f"{delta_html}"
        "</div>"
    )


def _kpi_card_html(
    title: str,
    items: list[tuple[str, str, str | None, str]],
    grid_columns: int,
) -> str:
    """Build a grouped KPI dashboard card."""
    items_html = "".join(
        _kpi_item_html(label, value, delta, tone)
        for label, value, delta, tone in items
    )
    safe_grid = 3 if grid_columns == 3 else 2
    return (
        '<div class="analytics-kpi-card">'
        f'<div class="analytics-eyebrow">{_html(title)}</div>'
        f'<div class="analytics-kpi-grid analytics-kpi-grid--{safe_grid}">'
        f"{items_html}"
        "</div>"
        "</div>"
    )


def _render_executive_kpi_summary(
    total_sales: float,
    total_covers: int,
    prior_total: float | None,
    prior_covers: int | None,
    monthly_target: float,
    avg_daily: float,
    df: pd.DataFrame,
    prior_df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> None:
    """Render grouped executive KPIs for the Analytics tab."""
    current_apc = total_sales / total_covers if total_covers > 0 else 0.0
    target_gap = monthly_target - total_sales if monthly_target > 0 else None
    achievement_pct = (
        (total_sales / monthly_target) * 100 if monthly_target > 0 else None
    )

    remaining_days = "N/A"
    if not df.empty and "date" in df.columns:
        parsed_dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if not parsed_dates.empty:
            latest_data_date = parsed_dates.max().date()
            remaining_days = str(max(0, (end_date - latest_data_date).days))

    sales_delta = None
    if prior_total is not None and prior_total > 0:
        sales_delta = ((total_sales - prior_total) / prior_total) * 100

    covers_delta = None
    if prior_covers is not None and prior_covers > 0:
        covers_delta = ((total_covers - prior_covers) / prior_covers) * 100

    prior_apc = None
    if prior_total is not None and prior_covers is not None and prior_covers > 0:
        prior_apc = prior_total / prior_covers

    apc_delta = None
    if prior_apc is not None and prior_apc > 0:
        apc_delta = ((current_apc - prior_apc) / prior_apc) * 100

    target_value = (
        utils.format_rupee_short(monthly_target) if monthly_target > 0 else "N/A"
    )
    achievement_value = (
        f"{achievement_pct:.1f}%" if achievement_pct is not None else "N/A"
    )
    target_gap_value = (
        utils.format_rupee_short(target_gap) if target_gap is not None else "N/A"
    )
    target_gap_delta = None
    target_gap_tone = "neutral"
    if target_gap is not None:
        target_gap_delta = "Ahead" if target_gap <= 0 else "Behind target"
        target_gap_tone = "positive" if target_gap <= 0 else "negative"

    cards_html = "".join(
        [
            _kpi_card_html(
                "Performance Summary",
                [
                    (
                        "Net Sales",
                        utils.format_rupee_short(total_sales),
                        None
                        if sales_delta is None
                        else f"{sales_delta:+.1f}% vs comparison",
                        _delta_tone(sales_delta),
                    ),
                    (
                        "Covers",
                        f"{total_covers:,}",
                        None
                        if covers_delta is None
                        else f"{covers_delta:+.1f}% vs comparison",
                        _delta_tone(covers_delta),
                    ),
                    ("APC", utils.format_currency(current_apc), None, "neutral"),
                ],
                grid_columns=3,
            ),
            _kpi_card_html(
                "Target Progress",
                [
                    ("Target", target_value, None, "neutral"),
                    ("Achievement %", achievement_value, None, "neutral"),
                    ("Target Gap", target_gap_value, target_gap_delta, target_gap_tone),
                    ("Remaining Days", remaining_days, None, "neutral"),
                ],
                grid_columns=2,
            ),
            _kpi_card_html(
                "Sales Quality Snapshot",
                [
                    (
                        "Avg Daily Sales",
                        utils.format_rupee_short(avg_daily),
                        None,
                        "neutral",
                    ),
                    (
                        "Sales vs comparison",
                        _format_comparison_delta(sales_delta),
                        None,
                        _delta_tone(sales_delta),
                    ),
                    (
                        "Covers vs comparison",
                        _format_comparison_delta(covers_delta),
                        None,
                        _delta_tone(covers_delta),
                    ),
                    (
                        "APC vs comparison",
                        _format_comparison_delta(apc_delta),
                        None,
                        _delta_tone(apc_delta),
                    ),
                ],
                grid_columns=2,
            ),
        ]
    )

    st.markdown(
        f'<div class="analytics-kpi-group">{cards_html}</div>',
        unsafe_allow_html=True,
    )


def render(ctx: TabContext) -> None:
    """Render the Analytics tab UI with charts and period analysis."""
    shell = page_shell()

    with shell.filters:
        with classed_container(
            "tab-analytics-mobile-filters",
            "analytics-filter-compact",
            "mobile-layout-stack",
            "mobile-layout-filters",
        ):
            period_col, outlet_col, comparison_col = st.columns([1.2, 2, 2])

            period_options = [
                "7D",
                "30D",
                "MTD",
                "LM",
                "QTD",
                "YTD",
                "Custom",
            ]

            current_period = st.session_state.get("analysis_period", "30D")
            if current_period == "Last Month":
                current_period = "LM"
            if current_period not in period_options:
                current_period = "30D"

            with period_col:
                analysis_period = st.segmented_control(
                    "Time Period",
                    options=period_options,
                    default=current_period,
                    key="analysis_period_selector",
                    label_visibility="collapsed",
                ) or current_period

            st.session_state.analysis_period = analysis_period

            selected_outlet = "All outlets"
            if len(ctx.report_loc_ids) > 1 and ctx.all_locs:
                _loc_options = ["All outlets"] + [
                    loc["name"] for loc in sorted(ctx.all_locs, key=lambda x: x["name"])
                ]

                if "analytics_outlet_scope" not in st.session_state:
                    st.session_state.analytics_outlet_scope = "All outlets"

                _current = st.session_state.get(
                    "analytics_outlet_scope",
                    "All outlets",
                )
                _default_idx = (
                    _loc_options.index(_current)
                    if _current in _loc_options
                    else 0
                )

                with outlet_col:
                    selected_outlet = st.segmented_control(
                        "Select outlet",
                        options=_loc_options,
                        default=_loc_options[_default_idx],
                        key="analytics_outlet_radio",
                        label_visibility="collapsed",
                    ) or _loc_options[_default_idx]

                st.session_state.analytics_outlet_scope = selected_outlet

            comparison_options = [
                "Previous Period",
                "Same Period Last Month",
                "Same Period Last Year",
            ]

            current_comparison = st.session_state.get(
                "analytics_comparison_mode",
                "Previous Period",
            )

            if current_comparison not in comparison_options:
                current_comparison = "Previous Period"

            with comparison_col:
                comparison_mode = st.segmented_control(
                    "Compare",
                    options=comparison_options,
                    default=current_comparison,
                    key="analytics_comparison_mode",
                    label_visibility="collapsed",
                ) or current_comparison

            custom_start = None
            custom_end = None
            if analysis_period == "Custom":
                custom_start, custom_end = date_range_nav(
                    session_key_start="analytics_custom_start",
                    session_key_end="analytics_custom_end",
                    label_start="From",
                    label_end="To",
                )
    start_date, end_date, prior_start, prior_end, _ = resolve_period_window(
        analysis_period,
        custom_start=custom_start,
        custom_end=custom_end,
        comparison_mode=comparison_mode,
    )

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    multi_analytics = len(ctx.report_loc_ids) > 1
    analytics_loc_ids = ctx.report_loc_ids

    if multi_analytics and ctx.all_locs:
        if selected_outlet != "All outlets":
            analytics_loc_ids = []
            for loc in ctx.all_locs:
                if loc["name"] == selected_outlet:
                    analytics_loc_ids = [loc["id"]]
                    break

    raw_summaries = _load_raw_summaries_cached(analytics_loc_ids, start_str, end_str)

    raw_summaries_with_targets = (
        _add_target_columns(
            pd.DataFrame(raw_summaries), ctx.all_locs, analytics_loc_ids
        ).to_dict("records")
        if raw_summaries
        else []
    )

    summaries = scope.merge_summaries_by_date(raw_summaries_with_targets)
    df_raw = pd.DataFrame(raw_summaries) if raw_summaries else pd.DataFrame()
    if multi_analytics and not df_raw.empty:
        loc_names = {loc["id"]: str(loc["name"]) for loc in ctx.all_locs}
        df_raw = df_raw.copy()
        df_raw["Outlet"] = df_raw["location_id"].map(lambda x: loc_names.get(x, str(x)))
        df_raw = _add_target_columns(df_raw, ctx.all_locs, analytics_loc_ids)

    with shell.content:
        if summaries:
            df = pd.DataFrame(summaries)

            # ── Period-over-period comparison data ───────────────────
            prior_summaries = []
            if prior_start and prior_end:
                prior_summaries = database.get_summaries_for_date_range_multi(
                    analytics_loc_ids,
                    prior_start.strftime("%Y-%m-%d"),
                    prior_end.strftime("%Y-%m-%d"),
                )
            prior_df = (
                pd.DataFrame(prior_summaries) if prior_summaries else pd.DataFrame()
            )

            total_sales = float(df["net_total"].sum())
            avg_daily = float(df["net_total"].mean())
            total_covers = int(df["covers"].sum())
            days_with_data = int(len(df[df["net_total"] > 0]))

            prior_total = (
                float(prior_df["net_total"].sum()) if not prior_df.empty else None
            )
            prior_covers = int(prior_df["covers"].sum()) if not prior_df.empty else None
            prior_avg = float(prior_df["net_total"].mean()) if not prior_df.empty else None

            scope_label = (
                "All outlets"
                if multi_analytics and len(analytics_loc_ids) > 1
                else "Single outlet"
            )
            context_items = [
                (
                    f'<span class="context-band-item"><strong>Window:</strong> '
                    f"{start_date.strftime('%d %b')} to {end_date.strftime('%d %b %Y')}</span>"
                ),
                (
                    f'<span class="context-band-item"><strong>Scope:</strong> '
                    f"{scope_label}</span>"
                ),
            ]
            if prior_start and prior_end:
                context_items.append(
                    f'<span class="context-band-item"><strong>Comparison:</strong> '
                    f"{comparison_mode} · "
                    f"{prior_start.strftime('%d %b')} to {prior_end.strftime('%d %b %Y')}</span>"
                )
            st.markdown(
                f'<div class="context-band context-band--muted">{"".join(context_items)}</div>',
                unsafe_allow_html=True,
            )

            monthly_target = scope.sum_location_monthly_targets(analytics_loc_ids)

            _render_executive_kpi_summary(
                total_sales=total_sales,
                total_covers=total_covers,
                prior_total=prior_total,
                prior_covers=prior_covers,
                monthly_target=monthly_target,
                avg_daily=avg_daily,
                df=df,
                prior_df=prior_df,
                start_date=start_date,
                end_date=end_date,
            )

            st.markdown("")

            # ── Row 1: Owner decision row ────────────────────────────
            # Full width keeps the executive readout prominent before diagnostics.
            render_owner_readout_and_data_confidence(
                df=df,
                df_raw=df_raw,
                prior_df=prior_df,
                analysis_period=analysis_period,
                start_date=start_date,
                end_date=end_date,
                monthly_target=monthly_target,
                total_sales=total_sales,
                total_covers=total_covers,
                prior_total=prior_total,
                prior_covers=prior_covers,
                analytics_loc_ids=analytics_loc_ids,
            )

            # ── Row 2: Required plan + forecast command center ───────
            plan_col, forecast_col = st.columns([1, 1])

            with plan_col:
                render_required_sales_plan(
                    df=df,
                    analysis_period=analysis_period,
                    start_date=start_date,
                    end_date=end_date,
                    monthly_target=monthly_target,
                    total_sales=total_sales,
                    total_covers=total_covers,
                    compact=True,
                )

            with forecast_col:
                render_forecast_command_center(
                    df,
                    prior_df,
                    analysis_period,
                    start_date,
                    end_date,
                    prior_start,
                    prior_end,
                    monthly_target,
                    total_sales,
                    avg_daily,
                    total_covers,
                    days_with_data,
                    prior_total,
                    prior_covers,
                    prior_avg,
                    show_kpis=False,
                    show_movement_breakdown=False,
                )

            render_sales_movement_waterfall(df, prior_df)

            # ── Row 3: Diagnostics and deep-dive layers ──────────────
            st.markdown(
                """
                <div class="analytics-section-divider">
                    <div class="analytics-eyebrow">Diagnostic Layers</div>
                    <div class="analytics-card-title">Diagnostic Layers</div>
                    <p class="analytics-card-caption">
                        Use these only when you need to understand why the top KPIs moved.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with classed_container("analytics-diagnostic-scope"):
                diagnostic_tabs = st.tabs(
                    [
                        "Outlet Scorecard",
                        "Sales Quality",
                        "Menu Mix & Timing",
                        "Drivers",
                        "Targets & Daily",
                        "Payments",
                    ]
                )

                with diagnostic_tabs[0]:
                    render_outlet_performance_scorecard(
                        df_raw=df_raw,
                        prior_df=prior_df,
                        analysis_period=analysis_period,
                        start_date=start_date,
                        end_date=end_date,
                        all_locs=ctx.all_locs,
                    )

                with diagnostic_tabs[1]:
                    render_sales_quality_layer(
                        df=df,
                        prior_df=prior_df,
                        total_sales=total_sales,
                        total_covers=total_covers,
                    )

                with diagnostic_tabs[2]:
                    render_category_quality_layer(
                        report_loc_ids=analytics_loc_ids,
                        start_str=start_str,
                        end_str=end_str,
                        prior_start=prior_start,
                        prior_end=prior_end,
                        total_sales=total_sales,
                        prior_total=prior_total,
                    )

                    st.markdown("")

                    render_mix_snapshot(
                        analytics_loc_ids,
                        start_str,
                        end_str,
                        df,
                        start_date,
                    )

                with diagnostic_tabs[3]:
                    render_driver_analysis(
                        df,
                        df_raw,
                        multi_analytics,
                    )

                with diagnostic_tabs[4]:
                    render_target_snapshot(
                        analytics_loc_ids,
                        start_date,
                        df,
                    )

                with diagnostic_tabs[5]:
                    render_payment_reconciliation(
                        analytics_loc_ids,
                        start_str,
                        end_str,
                    )

            st.markdown(
                """
                <div class="analytics-section-divider">
                    <div class="analytics-eyebrow">Operating follow-up</div>
                    <div class="analytics-card-title">Action Tracker</div>
                    <p class="analytics-card-caption">
                        Convert the dashboard insights above into trackable operating actions.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_action_tracker(
                df=df,
                prior_df=prior_df,
                monthly_target=monthly_target,
                total_sales=total_sales,
                total_covers=total_covers,
                analysis_period=analysis_period,
                selected_scope=selected_outlet,
                layout="horizontal",
                show_heading=False,
            )

        else:
            empty_state(
                message="No data available",
                hint=(
                    "This period has no sales data yet. "
                    "Upload POS files from the <strong>Upload</strong> tab "
                    "or select a different time range."
                    "<br><br>"
                    "<strong>Tip:</strong> Try selecting &lsquo;MTD&rsquo; or &lsquo;30D&rsquo; "
                    "to see recent data."
                ),
                icon="insights",
            )
