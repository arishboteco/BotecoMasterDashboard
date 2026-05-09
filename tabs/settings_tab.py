"""Settings tab — Account info, outlet CRUD, user CRUD, data export."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

import config
import database
import utils
from auth import is_admin
from components import (
    classed_container,
    divider,
    filter_strip,
    info_banner,
    page_shell,
    primary_action_bar,
    section_title,
)
from components.forms import confirm_dialog
from components.navigation import date_range_nav
from tabs import TabContext


def render(ctx: TabContext) -> None:
    """Render the Settings tab UI for admins and account display."""
    shell = page_shell()

    # ── Account info (all users) ──────────────────────────────────
    with shell.filters:
        st.caption(
            f"Signed in as **{st.session_state.username}** "
            f"· {st.session_state.user_role.title()} "
            f"· {st.session_state.location_name}"
        )

    if not is_admin():
        st.info(
            "Contact an admin to change your password, role, or location assignment."
        )
        st.stop()

    with shell.content:
        # ─────────────────────────────────────────────────────────
        # OUTLETS
        # ─────────────────────────────────────────────────────────
        section_title(
            "Outlets",
            subtitle="Configure targets, seat counts, and manage outlet locations",
            icon="store",
        )

        sort_locs = (
            sorted(ctx.all_locs, key=lambda x: x["name"]) if ctx.all_locs else []
        )

        if sort_locs:
            loc_names = [loc["name"] for loc in sort_locs]
            loc_by_name = {loc["name"]: loc for loc in sort_locs}

            selected_name = st.radio(
                "Outlet",
                options=loc_names,
                horizontal=True,
                key="settings_outlet_radio",
                label_visibility="collapsed",
            )
            selected_loc = loc_by_name[selected_name]
            settings_location_id = selected_loc["id"]
            location_settings = database.get_location_settings(settings_location_id)

            # Current stats
            ms1, ms2, _ = st.columns(3)
            with ms1:
                current_target = (
                    location_settings.get("target_monthly_sales", 0)
                    if location_settings
                    else 0
                )
                st.metric("Monthly target", utils.format_currency(current_target))
            with ms2:
                current_seats = (
                    location_settings.get("seat_count") if location_settings else None
                )
                st.metric("Seat count", current_seats or "—")

            with st.form("location_settings_form"):
                lf1, lf2, lf3 = st.columns(3)
                with lf1:
                    new_name = st.text_input(
                        "Location name",
                        value=(
                            location_settings.get("name", "")
                            if location_settings
                            else ""
                        ),
                    )
                with lf2:
                    new_target = st.number_input(
                        "Monthly target (₹)",
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
                if st.form_submit_button("Save changes", type="primary"):
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

            outlet_add_tab, outlet_del_tab = st.tabs(
                ["Add new outlet", "Delete outlet"]
            )
        else:
            st.caption("No outlets found. Add one below.")
            outlet_add_tab, outlet_del_tab = st.tabs(
                ["Add new outlet", "Delete outlet"]
            )

        with outlet_add_tab:
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
                if st.form_submit_button("Create outlet", type="primary"):
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

        with outlet_del_tab:
            info_banner(
                "An outlet can only be deleted if it has no saved data. "
                "Remove all daily data from the Upload tab first.",
                tone="warning",
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

                def _do_delete_outlet() -> None:
                    _id = st.session_state.get("_pending_loc_delete")
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

        divider()

        # ─────────────────────────────────────────────────────────
        # USER ACCESS MANAGEMENT
        # ─────────────────────────────────────────────────────────
        section_title(
            "User access management",
            subtitle="Create, edit, and remove dashboard users",
            icon="groups",
        )

        all_users = database.get_all_users()
        if all_users:
            users_df = pd.DataFrame(all_users)
            display_cols = ["username", "role", "location_name", "email", "created_at"]
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
        else:
            st.caption("No users found.")

        user_create_tab, user_edit_tab, user_del_tab = st.tabs(
            ["Create user", "Edit user", "Delete user"]
        )

        with user_create_tab:
            info_banner(
                "**Manager** — can view and upload data for their assigned outlet.  "
                "**Admin** — full access to all outlets, users, and settings.",
                tone="info",
            )
            with st.form("create_user_form"):
                cu1, cu2 = st.columns(2)
                with cu1:
                    cu_username = st.text_input("Username")
                    cu_password = st.text_input("Password", type="password")
                    cu_confirm = st.text_input("Confirm password", type="password")
                with cu2:
                    cu_role = st.selectbox("Role", ["manager", "admin"])
                    cu_loc_opts = {
                        loc["id"]: loc["name"] for loc in (ctx.all_locs or [])
                    }
                    cu_loc_opts[0] = "— none —"
                    cu_loc = st.selectbox(
                        "Home location",
                        options=[0] + [loc["id"] for loc in (ctx.all_locs or [])],
                        format_func=lambda i: cu_loc_opts.get(i, str(i)),
                    )
                    cu_email = st.text_input("Email (optional)")
                if st.form_submit_button("Create user", type="primary"):
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

        with user_edit_tab:
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
                                loc["id"]: loc["name"]
                                for loc in (ctx.all_locs or [])
                            }
                            eu_loc_opts[0] = "— none —"
                            eu_loc_ids = [0] + [
                                loc["id"] for loc in (ctx.all_locs or [])
                            ]
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
                            eu_email = st.text_input(
                                "Email", value=eu.get("email") or ""
                            )
                        with eu2:
                            eu_newpw = st.text_input(
                                "New password (leave blank to keep current)",
                                type="password",
                            )
                            eu_confirmpw = st.text_input(
                                "Confirm new password", type="password"
                            )
                        if st.form_submit_button("Save user changes", type="primary"):
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
            else:
                st.caption("No users to edit.")

        with user_del_tab:
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

                def _do_delete_user() -> None:
                    _id = st.session_state.get("_pending_user_delete")
                    ok, msg = database.delete_user(_id, _current_user)
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
            else:
                st.caption("No users to delete.")

        divider()

        # ─────────────────────────────────────────────────────────
        # DATA EXPORT
        # ─────────────────────────────────────────────────────────
        section_title(
            "Data export",
            subtitle="Download saved daily summaries as CSV or Excel",
            icon="download",
        )

        filter_strip("Export filters", "Pick outlet and date range", icon="filter_alt")

        with classed_container(
            "tab-settings-mobile-export-filters", "mobile-layout-stack"
        ):
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

            dl1, dl2 = st.columns(2)
            csv_bytes = exp_df.to_csv(index=False).encode("utf-8")
            with dl1:
                st.download_button(
                    label=f"Download CSV ({len(exp_df):,} rows)",
                    data=csv_bytes,
                    file_name=f"boteco_export_{exp_start}_{exp_end}.csv",
                    mime="text/csv",
                    key="export_csv_btn",
                    use_container_width=True,
                )

            excel_buf = BytesIO()
            with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
                exp_df.to_excel(writer, index=False, sheet_name="Daily Summaries")
            excel_buf.seek(0)
            with dl2:
                st.download_button(
                    label=f"Download Excel ({len(exp_df):,} rows)",
                    data=excel_buf.getvalue(),
                    file_name=f"boteco_export_{exp_start}_{exp_end}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="export_excel_btn",
                    use_container_width=True,
                )

            with st.expander("Preview (first 10 rows)", expanded=False):
                st.dataframe(exp_df.head(10), width="stretch", hide_index=True)
        else:
            st.caption("No data found for the selected filters.")

        divider()

        # ─────────────────────────────────────────────────────────
        # DANGER ZONE
        # ─────────────────────────────────────────────────────────
        section_title("Danger zone", icon="warning")

        with st.container(border=True):
            info_banner(
                "Permanently deletes ALL daily summaries, categories, services, items, "
                "and upload history. Outlets and users are preserved. "
                "**This action cannot be undone.**",
                tone="error",
            )
            wipe_confirm = st.checkbox(
                "I understand this will permanently delete ALL operational data",
                key="wipe_all_confirm",
            )
            with classed_container(
                "tab-settings-mobile-primary-action",
                "mobile-layout-primary-action",
            ):
                wipe_clicked, _ = primary_action_bar(
                    "Wipe All Data",
                    primary_key="wipe_all_btn",
                    primary_disabled=not wipe_confirm,
                )
            if wipe_clicked:
                counts, errors = database.wipe_all_data()
                st.cache_data.clear()
                total = sum(counts.values())
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
                    st.success(
                        f"Wiped **{total:,}** records across {len(counts)} tables:"
                    )
                    for table, count in counts.items():
                        if count > 0:
                            st.write(f"- `{table}`: {count:,} records deleted")
                else:
                    st.error("Wipe completed but no records were deleted.")
                for err in errors:
                    st.warning(f"- {err}")

