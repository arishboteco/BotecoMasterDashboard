"""Permission and report-scope helpers for authentication context."""

from typing import List

import streamlit as st

import boteco_logger
import database

logger = boteco_logger.get_logger(__name__)


def is_admin() -> bool:
    """Check if current user is admin."""
    return st.session_state.get("user_role") == "admin"


def is_manager() -> bool:
    """Check if current user is manager or admin."""
    role = st.session_state.get("user_role")
    return role in ["admin", "manager"]


def get_report_location_ids() -> List[int]:
    """Locations included in Daily Report / Analytics for the current scope."""
    locs = database.get_all_locations()
    vs = st.session_state.get("view_scope")
    role = st.session_state.get("user_role")
    lid = st.session_state.get("location_id")
    if is_admin() and vs == "all":
        return [loc["id"] for loc in sorted(locs, key=lambda x: x["name"])]
    if role == "manager" and vs == "all" and lid is None:
        return [loc["id"] for loc in sorted(locs, key=lambda x: x["name"])]
    if vs and str(vs) != "all":
        try:
            return [int(vs)]
        except (TypeError, ValueError) as ex:
            logger.warning(
                "Invalid view_scope in auth.py user=%s view_scope=%s error=%s",
                st.session_state.get("username") or "anonymous",
                vs,
                ex,
            )
    return [int(lid)] if lid is not None else [1]


def get_report_display_name() -> str:
    """Resolve the report display name for the current scope."""
    locs = database.get_all_locations()
    ids = get_report_location_ids()
    if len(ids) > 1:
        return "All locations"
    for loc in locs:
        if loc["id"] == ids[0]:
            return str(loc["name"])
    return st.session_state.get("location_name") or "Boteco"


def get_primary_location_id() -> int:
    """Return a concrete location id for single-location operations."""
    lid = st.session_state.get("location_id")
    if lid is not None:
        return int(lid)

    ids = get_report_location_ids()
    if ids:
        return int(ids[0])
    return 1
