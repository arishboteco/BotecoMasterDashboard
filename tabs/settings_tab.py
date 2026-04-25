"""Settings tab — Account info, outlet CRUD, user CRUD, data export."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

import config
import database
import utils
from auth import is_admin
from tabs import TabContext
from components.navigation import date_range_nav
from components.forms import confirm_dialog
from components import page_header


def render(ctx: TabContext) -> None:
    """Render the Settings tab UI for admins and account display."""
    page_header(
        title="Settings and Administration",
        subtitle="Manage outlets, user access, targets, exports, and maintenance controls.",
        context="Admin controls",
    )

    # ── Account info (all users) ──────────────────────────────────
    with st.container(border=True):
        st.markdown("### Your Account")
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            st.markdown(f"**Username:** {st.session_state.username}")
        with ac2:
            st.markdown(f"**Role:** {st.session_state.user_role.title()}")
        with ac3:
            st.markdown(f"**Home location:** {st.session_state.location_name}")

    if not is_admin():
        st.info(
            "Contact an admin to change your password, role, or location assignment."
        )
        st.stop()

    # ─────────────────────────────────────────────────────────────
    # ADMIN-ONLY SECTIONS BELOW
    # ─────────────────────────────────────────────────────────────

    st.markdown('<div class="ux-panel-title">Outlet administration</div>', unsafe_allow_html=True)

    # ── Location settings ─────────────────────────────────────────
    st.markdown("### Outlet Settings")
    sort_locs = sorted(ctx.all_locs, key=lambda x: x["name"]) if ctx.all_locs else []
    if sort_locs:
        name_by_id = {loc["id"]: loc["name"] for loc in sort_locs}
        settings_location_id = st.selectbox(
            "Edit settings for outlet",
            options=[loc["id"] for loc in sort_locs],
            format_func=lambda i: name_by_id[i],
            key="settings_which_location",
        )
        location_settings = database.get_location_settings(settings_location_id)

        with st.form("location_settings_form"):
            lf1, lf2, lf3 = st.columns(3)
            with lf1:
                new_name = st.text_input(
                    "Location Name",
                    value=(
                        location_settings.get("name", "") if location_settings else ""
                    ),
                )
            with lf2:
                new_target = st.number_input(
                    "Monthly Target (₹)",
                    min_value=0,
                    value=int(
                        location_settings.get(
                            "target_monthly_sales", config.MONTHLY_TARGET
                        )
                        if location_settings
                        else config.MONTHLY_TARGET
                    ),
                    step=100000,
                    help="Enter in rupees — e.g. 5000000 for ₹50,00,000",
                )
            with lf3:
                seat_default = 0
                if location_settings and location_settings.get("seat_count"):
                    seat_default = int(location_settings["seat_count"])
                new_seats = st.number_input(
                    "Seat count (for turns)",
                    min_value=0,
                    value=seat_default,
                    step=1,
                    help="Covers ÷ seats = turns. Leave 0 to use covers ÷ 100.",
                )
            if st.form_submit_button("Save outlet settings"):
                database.update_location_settings(
                    int(settings_location_id),
                    {
                        "name": new_name,
                        "target_monthly_sales": new_target,
                        "seat_count": int(new_seats) if new_seats > 0 else None,
                    },
                )
                st.success("Outlet settings saved.")
                st.rerun()

    # Add new location
    with st.expander("Add new outlet", expanded=False):
        with st.form("new_location_form"):
            nl1, nl2, nl3 = st.columns(3)
            with nl1:
                nl_name = st.text_input(
                    "Outlet name", placeholder="e.g. Boteco - Koramangala"
                )
            with nl2:
                nl_target = st.number_input(
                    "Monthly target (₹)",
                    min_value=0,
                    value=config.MONTHLY_TARGET,
                    step=100000,
                    help="Enter in rupees — e.g. 5000000 for ₹50,00,000",
                )
            with nl3:
                nl_seats = st.number_input(
                    "Seat count",
                    min_value=0,
                    value=0,
                    step=1,
                )
            if st.form_submit_button("Create outlet"):
                ok, msg = database.create_location(
                    nl_name,
                    nl_target,
                    int(nl_seats) if nl_seats > 0 else None,
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # Delete location
    with st.expander("Delete outlet", expanded=False):
        st.caption(
            "An outlet can only be deleted if it has no saved data. "
            "Remove all daily data from the Upload tab first."
        )
        if ctx.all_locs:
            del_loc_opts = {loc["id"]: loc["name"] for loc in sort_locs}
            del_loc_id = st.selectbox(
                "Select outlet to delete",
                options=list(del_loc_opts.keys()),
                format_func=lambda i: del_loc_opts[i],
                key="del_loc_select",
            )
            if "_outlet_delete_result" in st.session_state:
                ok, msg = st.session_state.pop("_outlet_delete_result")
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            if st.button("Delete outlet", key="del_loc_btn", type="secondary"):
                st.session_state["_pending_loc_delete"] = del_loc_id

            def _do_delete_outlet(_id=st.session_state.get("_pending_loc_delete")):
                ok, msg = database.delete_location(_id)
                st.session_state.pop("_pending_loc_delete", None)
                st.session_state["_outlet_delete_result"] = (ok, msg)
                st.rerun()

            confirm_dialog(
                message=(
                    f"**Confirm:** permanently delete outlet "
                    f"**{del_loc_opts.get(st.session_state.get('_pending_loc_delete'), '')}**?"
                ),
                confirm_key="_pending_loc_delete",
                on_confirm=_do_delete_outlet,
                confirm_label="Yes, delete outlet",
            )

    st.markdown('<div class="ux-panel-title">User access management</div>', unsafe_allow_html=True)

    # ── User management ───────────────────────────────────────────
    st.markdown("### User Management")

    all_users = database.get_all_users()
    if all_users:
        users_df = pd.DataFrame(all_users)
        display_cols = [
            "username",
            "role",
            "location_name",
            "email",
            "created_at",
        ]
        display_cols = [c for c in display_cols if c in users_df.columns]
        st.dataframe(
            users_df[display_cols].rename(
                columns={
                    "username": "Username",
                    "role": "Role",
                    "location_name": "Location",
                    "email": "Email",
                    "created_at": "Created",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    # Create user
    with st.expander("Create new user", expanded=False):
        with st.form("create_user_form"):
            cu1, cu2 = st.columns(2)
            with cu1:
                cu_username = st.text_input("Username")
                cu_password = st.text_input("Password", type="password")
                cu_confirm = st.text_input("Confirm password", type="password")
            with cu2:
                cu_role = st.selectbox("Role", ["manager", "admin"])
                cu_loc_opts = {loc["id"]: loc["name"] for loc in (ctx.all_locs or [])}
                cu_loc_opts[0] = "— none —"
                cu_loc = st.selectbox(
                    "Home location",
                    options=[0] + [loc["id"] for loc in (ctx.all_locs or [])],
                    format_func=lambda i: cu_loc_opts.get(i, str(i)),
                )
                cu_email = st.text_input("Email (optional)")
            if st.form_submit_button("Create user"):
                if cu_password != cu_confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = database.create_user(
                        cu_username,
                        cu_password,
                        cu_role,
                        int(cu_loc) if cu_loc else None,
                        cu_email,
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # Edit user
    with st.expander("Edit user (role / location / password)", expanded=False):
        if all_users:
            eu_opts = {u["id"]: u["username"] for u in all_users}
            eu_id = st.selectbox(
                "Select user to edit",
                options=list(eu_opts.keys()),
                format_func=lambda i: eu_opts[i],
                key="edit_user_select",
            )
            eu = next((u for u in all_users if u["id"] == eu_id), None)
            if eu:
                with st.form("edit_user_form"):
                    eu1, eu2 = st.columns(2)
                    with eu1:
                        eu_role = st.selectbox(
                            "Role",
                            ["manager", "admin"],
                            index=0 if eu.get("role") == "manager" else 1,
                        )
                        eu_loc_opts = {
                            loc["id"]: loc["name"] for loc in (ctx.all_locs or [])
                        }
                        eu_loc_opts[0] = "— none —"
                        eu_loc_ids = [0] + [loc["id"] for loc in (ctx.all_locs or [])]
                        cur_loc = eu.get("location_id") or 0
                        try:
                            cur_idx = eu_loc_ids.index(cur_loc)
                        except ValueError:
                            cur_idx = 0
                        eu_loc = st.selectbox(
                            "Home location",
                            options=eu_loc_ids,
                            index=cur_idx,
                            format_func=lambda i: eu_loc_opts.get(i, str(i)),
                        )
                        eu_email = st.text_input("Email", value=eu.get("email") or "")
                    with eu2:
                        eu_newpw = st.text_input(
                            "New password (leave blank to keep current)",
                            type="password",
                        )
                        eu_confirmpw = st.text_input(
                            "Confirm new password", type="password"
                        )
                    if st.form_submit_button("Save user changes"):
                        if eu_newpw and eu_newpw != eu_confirmpw:
                            st.error("Passwords do not match.")
                        else:
                            ok, msg = database.update_user(
                                eu_id,
                                role=eu_role,
                                location_id=int(eu_loc) if eu_loc else None,
                                email=eu_email,
                                new_password=eu_newpw if eu_newpw else None,
                            )
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

    # Delete user
    with st.expander("Delete user", expanded=False):
        if all_users:
            du_opts = {u["id"]: u["username"] for u in all_users}
            du_id = st.selectbox(
                "Select user to delete",
                options=list(du_opts.keys()),
                format_func=lambda i: du_opts[i],
                key="del_user_select",
            )
            if "_user_delete_result" in st.session_state:
                ok, msg = st.session_state.pop("_user_delete_result")
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            if st.button("Delete user", key="del_user_btn", type="secondary"):
                st.session_state["_pending_user_delete"] = du_id

            _current_user = st.session_state.username

            def _do_delete_user(
                _id=st.session_state.get("_pending_user_delete"),
                _actor=_current_user,
            ):
                ok, msg = database.delete_user(_id, _actor)
                st.session_state.pop("_pending_user_delete", None)
                st.session_state["_user_delete_result"] = (ok, msg)
                st.rerun()

            confirm_dialog(
                message=(
                    f"**Confirm:** permanently delete user "
                    f"**{du_opts.get(st.session_state.get('_pending_user_delete'), '')}**?"
                ),
                confirm_key="_pending_user_delete",
                on_confirm=_do_delete_user,
                confirm_label="Yes, delete user",
            )

    st.markdown('<div class="ux-panel-title">Data export and maintenance</div>', unsafe_allow_html=True)

    # ── Data export ───────────────────────────────────────────────
    st.markdown("### Data Export")
    st.caption(
        "Download all saved daily summaries as CSV or Excel. "
        "Use the filters to narrow the export."
    )

    exp_c1, exp_c2 = st.columns([1, 2])
    with exp_c1:
        exp_loc_opts = {"all": "All outlets"}
        exp_loc_opts.update(
            {str(loc["id"]): loc["name"] for loc in (ctx.all_locs or [])}
        )
        exp_loc = st.selectbox(
            "Outlet",
            options=list(exp_loc_opts.keys()),
            format_func=lambda k: exp_loc_opts[k],
            key="export_outlet",
        )
    with exp_c2:
        exp_start, exp_end = date_range_nav(
            session_key_start="export_start",
            session_key_end="export_end",
            label_start="From date",
            label_end="To date",
        )

    exp_loc_ids = [int(exp_loc)] if exp_loc != "all" else None

    exp_rows = database.get_all_summaries_for_export(
        location_ids=exp_loc_ids,
        start_date=exp_start.strftime("%Y-%m-%d"),
        end_date=exp_end.strftime("%Y-%m-%d"),
    )

    if exp_rows:
        exp_df = pd.DataFrame(exp_rows)
        st.caption(f"{len(exp_df):,} days across the selected range.")

        # CSV download
        csv_bytes = exp_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Download CSV ({len(exp_df):,} rows)",
            data=csv_bytes,
            file_name=f"boteco_export_{exp_start}_{exp_end}.csv",
            mime="text/csv",
            key="export_csv_btn",
        )

        # Excel download
        excel_buf = BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            exp_df.to_excel(writer, index=False, sheet_name="Daily Summaries")
        excel_buf.seek(0)
        st.download_button(
            label=f"Download Excel ({len(exp_df):,} rows)",
            data=excel_buf.getvalue(),
            file_name=f"boteco_export_{exp_start}_{exp_end}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="export_excel_btn",
        )

        with st.expander("Preview (first 10 rows)", expanded=False):
            st.dataframe(exp_df.head(10), width="stretch", hide_index=True)
    else:
        st.caption("No data found for the selected filters.")

    st.markdown('<div class="ux-panel-title">Danger zone</div>', unsafe_allow_html=True)

    # ── Wipe All Data ─────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("### Wipe All Data")
        st.caption(
            "Permanently deletes ALL daily summaries, categories, services, items, and upload history. "
            "Outlets and users are preserved. **This action cannot be undone.**"
        )
        wipe_confirm = st.checkbox(
            "I understand this will permanently delete ALL operational data",
            key="wipe_all_confirm",
        )
        if st.button(
            "Wipe All Data",
            type="secondary",
            disabled=not wipe_confirm,
            key="wipe_all_btn",
        ):
            counts, errors = database.wipe_all_data()
            st.cache_data.clear()
            total = sum(counts.values())
            if errors:
                st.warning("Some issues occurred during wipe:")
                for err in errors:
                    st.write(f"- {err}")
            st.session_state["wipe_result"] = {
                "total": total,
                "counts": counts,
                "errors": errors,
            }
            st.rerun()

        if "wipe_result" in st.session_state:
            result = st.session_state.pop("wipe_result")
            total = result["total"]
            counts = result["counts"]
            errors = result["errors"]
            if total > 0:
                st.success(f"Wiped **{total:,}** records across {len(counts)} tables:")
                for table, count in counts.items():
                    if count > 0:
                        st.write(f"- `{table}`: {count:,} records deleted")
            else:
                st.error("Wipe completed but no records were deleted.")
            if errors:
                for err in errors:
                    st.warning(f"- {err}")

    st.divider()

    # ── Quick outlet stats ────────────────────────────────────────
    with st.expander("Quick stats (all outlets)", expanded=False):
        locs_for_stats = sorted(database.get_all_locations(), key=lambda x: x["name"])
        for i, loc in enumerate(locs_for_stats):
            st.write(f"**{loc['name']}**")
            st.write(
                f"- Monthly target: {utils.format_currency(loc.get('target_monthly_sales', 0))}"
                f"  |  Seats: {loc.get('seat_count') or '—'}"
            )
            if i < len(locs_for_stats) - 1:
                st.divider()
