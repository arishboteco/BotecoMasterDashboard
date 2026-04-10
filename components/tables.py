"""Data table component for consistent dataframe rendering."""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import streamlit as st


def data_table(
    df: pd.DataFrame,
    column_config: Optional[Dict] = None,
    empty_message: str = "No data available.",
    hide_index: bool = True,
    width: str = "stretch",
) -> None:
    """Render a styled data table with empty state handling."""
    if df.empty:
        st.caption(empty_message)
        return

    st.dataframe(
        df,
        width=width,
        hide_index=hide_index,
        column_config=column_config,
    )
