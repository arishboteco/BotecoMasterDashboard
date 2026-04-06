"""Table formatter and builder functions for analytics dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import utils


def format_daily_data_table(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> pd.DataFrame:
    """Build daily data table with formatted columns and totals row.

    Formats currency, covers, and calculates totals row for period summary.

    Args:
        df: Aggregated daily summary
        df_raw: Raw daily data (for multi-outlet view)
        multi_analytics: True if viewing multiple outlets

    Returns:
        Formatted DataFrame ready for st.dataframe()
    """
    if multi_analytics and not df_raw.empty:
        detail = df_raw[
            ["date", "Outlet", "covers", "net_total", "target", "achievement"]
        ].copy()
    else:
        detail = df[["date", "covers", "net_total", "target", "achievement"]].copy()
        detail.insert(1, "Outlet", "Combined")

    # Format columns
    detail["Date"] = pd.to_datetime(detail["date"]).dt.strftime("%d %b %Y")
    detail["Covers"] = detail["covers"].astype(int).astype(str)
    detail["Net Sales"] = detail["net_total"].apply(utils.format_currency)
    detail["Target"] = detail["target"].apply(utils.format_currency)
    detail["Achievement"] = detail["achievement"].round(1).astype(str) + "%"

    # Select display columns
    result = detail[
        ["Date", "Outlet", "Covers", "Net Sales", "Target", "Achievement"]
    ].copy()

    # Add totals row
    total_covers = int(detail["covers"].sum())
    total_sales = detail["net_total"].sum()
    total_target = detail["target"].sum()
    overall_achievement = (
        f"{(total_sales / total_target * 100):.1f}%" if total_target > 0 else "—"
    )

    totals_row = pd.DataFrame(
        {
            "Date": ["TOTAL"],
            "Outlet": [""],
            "Covers": [str(total_covers)],
            "Net Sales": [utils.format_currency(total_sales)],
            "Target": [utils.format_currency(total_target)],
            "Achievement": [overall_achievement],
        }
    )

    result = pd.concat([result, totals_row], ignore_index=True)

    return result


def build_sales_trend_detail(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> pd.DataFrame:
    """Build sales trend drill-down table.

    Args:
        df: Aggregated daily summary
        df_raw: Raw daily data
        multi_analytics: True if multi-outlet

    Returns:
        Formatted DataFrame with Date, Outlet, Net Sales, Covers, APC
    """
    if multi_analytics and not df_raw.empty:
        detail = df_raw[["date", "Outlet", "net_total", "covers", "apc"]].copy()
        detail.columns = ["Date", "Outlet", "Net Sales", "Covers", "APC"]
    else:
        detail = df[["date", "net_total", "covers", "apc"]].copy()
        detail.columns = ["Date", "Net Sales", "Covers", "APC"]

    # Format columns
    detail["Date"] = pd.to_datetime(detail["Date"]).dt.strftime("%Y-%m-%d")
    detail["Net Sales"] = detail["Net Sales"].apply(utils.format_currency)
    detail["Covers"] = detail["Covers"].astype(int).astype(str)
    if "APC" in detail.columns:
        detail["APC"] = detail["APC"].apply(utils.format_currency)

    return detail


def build_apc_detail(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> pd.DataFrame:
    """Build APC trend drill-down table.

    Args:
        df: Aggregated daily summary
        df_raw: Raw daily data
        multi_analytics: True if multi-outlet

    Returns:
        Formatted DataFrame with Date, Outlet (if multi), APC
    """
    if multi_analytics and not df_raw.empty:
        detail = df_raw[["date", "Outlet", "apc"]].copy()
        detail.columns = ["Date", "Outlet", "APC"]
    else:
        detail = df[["date", "apc"]].copy()
        detail.columns = ["Date", "APC"]

    detail["Date"] = pd.to_datetime(detail["Date"]).dt.strftime("%Y-%m-%d")
    detail["APC"] = detail["APC"].apply(utils.format_currency)

    return detail


def build_weekday_detail(df: pd.DataFrame, start_date) -> pd.DataFrame:
    """Build weekday analysis drill-down table.

    Args:
        df: Daily summary data
        start_date: Start date of period (for context)

    Returns:
        Formatted DataFrame with Day, Avg Sales, Avg Covers, Count
    """
    wd_df = df[df["net_total"] > 0].copy()
    wd_df["weekday"] = wd_df["date"].apply(utils.get_weekday_name)

    wd_agg = (
        wd_df.groupby("weekday")
        .agg(
            {
                "net_total": ["mean", "count"],
                "covers": "mean",
            }
        )
        .reset_index()
    )

    wd_agg.columns = ["Day", "Avg Sales", "Count", "Avg Covers"]
    wd_agg = wd_agg[["Day", "Avg Sales", "Avg Covers", "Count"]]

    # Format columns
    wd_agg["Avg Sales"] = wd_agg["Avg Sales"].apply(utils.format_currency)
    wd_agg["Avg Covers"] = wd_agg["Avg Covers"].round(0).astype(int).astype(str)
    wd_agg["Count"] = wd_agg["Count"].astype(int).astype(str)

    # Reorder by day of week
    day_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    wd_agg["Day"] = pd.Categorical(wd_agg["Day"], categories=day_order, ordered=True)
    wd_agg = wd_agg.sort_values("Day")

    return wd_agg


def build_category_detail_table(cat_df: pd.DataFrame) -> pd.DataFrame:
    """Build category breakdown detail table.

    Shows all categories with exact amounts and percentages.

    Args:
        cat_df: DataFrame with 'category' and 'amount' columns

    Returns:
        Formatted DataFrame with Category, Amount, % of Total, plus totals row
    """
    if cat_df.empty:
        return pd.DataFrame()

    cat_df = cat_df.copy()
    total = cat_df["amount"].sum()

    cat_df["Amount (₹)"] = cat_df["amount"].apply(utils.format_currency)
    cat_df["% of Total"] = (cat_df["amount"] / total * 100).round(1).astype(str) + "%"

    result = cat_df[["category", "Amount (₹)", "% of Total"]].copy()
    result.columns = ["Category", "Amount (₹)", "% of Total"]

    # Sort by amount descending
    result = result.sort_values(
        "Amount (₹)",
        key=lambda x: x.str.replace("₹", "").str.replace(",", "").astype(float),
        ascending=False,
    )

    # Add totals row
    totals_row = pd.DataFrame(
        {
            "Category": ["TOTAL"],
            "Amount (₹)": [utils.format_currency(total)],
            "% of Total": ["100.0%"],
        }
    )
    result = pd.concat([result, totals_row], ignore_index=True)

    return result


def build_target_detail(
    df: pd.DataFrame,
    daily_target: float,
) -> pd.DataFrame:
    """Build target achievement drill-down table.

    Args:
        df: Daily summary data with achievement column
        daily_target: Daily target amount

    Returns:
        Formatted DataFrame with Date, Outlet, Net Sales, Target, Achievement %
    """
    detail = df[["date", "net_total", "target", "achievement"]].copy()
    detail.columns = ["Date", "Net Sales", "Target", "Achievement"]

    detail["Date"] = pd.to_datetime(detail["Date"]).dt.strftime("%Y-%m-%d")
    detail["Net Sales"] = detail["Net Sales"].apply(utils.format_currency)
    detail["Target"] = detail["Target"].apply(utils.format_currency)
    detail["Achievement"] = detail["Achievement"].round(1).astype(str) + "%"

    return detail


def get_daily_table_column_config() -> dict:
    """Return Streamlit column config for daily data table.

    Returns:
        Dictionary of column configurations for st.dataframe()
    """
    return {
        "Date": st.column_config.TextColumn("Date", width="medium"),
        "Outlet": st.column_config.TextColumn("Outlet", width="medium"),
        "Covers": st.column_config.TextColumn("Covers", width="small"),
        "Net Sales": st.column_config.TextColumn("Net Sales (₹)", width="medium"),
        "Target": st.column_config.TextColumn("Target (₹)", width="medium"),
        "Achievement": st.column_config.TextColumn("Achievement %", width="small"),
    }
