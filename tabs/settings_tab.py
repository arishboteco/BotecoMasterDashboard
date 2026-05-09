"""Settings tab — Account info, outlet CRUD, user CRUD."""

from __future__ import annotations

import streamlit as st

import config
import database
import utils
from auth import is_admin
from components import (
    classed_container,
    divider,
    info_banner,
    page_shell,
    primary_action_bar,
    section_title,
)
from components.forms import confirm_dialog
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

            selected_name = st.pills(
                "Outlet",
                options=loc_names,
                selection_mode="single",
                default=loc_names[0],
                key="settings_outlet_pills",
                label_visibility="collapsed",
            )
            if selected_name is None:
                selected_name = loc_names[0]
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
            user_by_name = {u["username"]: u for u in all_users}

            user_options = list(user_by_name.keys())
            selected_username = st.pills(
                "User",
                options=user_options,
                selection_mode="single",
                default=user_options[0],
                key="settings_user_pills",
                label_visibility="collapsed",
            )
            if selected_username is None:
                selected_username = user_options[0]
            eu = user_by_name[selected_username]

            # Current user info
            ui1, ui2, ui3 = st.columns(3)
            with ui1:
                st.metric("Role", eu.get("role", "—").title())
            with ui2:
                st.metric("Location", eu.get("location_name") or "—")
            with ui3:
                st.metric("Email", eu.get("email") or "—")

            # Edit form (always visible, driven by radio selection)
            with st.form("edit_user_form"):
                ef1, ef2, ef3 = st.columns(3)
                with ef1:
                    eu_role = st.selectbox(
                        "Role",
                        ["manager", "admin"],
                        index=0 if eu.get("role") == "manager" else 1,
                    )
                with ef2:
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
                with ef3:
                    eu_email = st.text_input("Email", value=eu.get("email") or "")

                pw1, pw2, _ = st.columns(3)
                with pw1:
                    eu_newpw = st.text_input(
                        "New password",
                        type="password",
                        placeholder="Leave blank to keep current",
                    )
                with pw2:
                    eu_confirmpw = st.text_input("Confirm new password", type="password")

                if st.form_submit_button("Save changes", type="primary"):
                    if eu_newpw and eu_newpw != eu_confirmpw:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = database.update_user(
                            eu["id"],
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

            user_create_tab, user_del_tab = st.tabs(["Create user", "Delete user"])
        else:
            st.caption("No users found.")
            user_create_tab, user_del_tab = st.tabs(["Create user", "Delete user"])

        with user_create_tab:
            info_banner(
                "**Manager** — can view and upload data for their assigned outlet.  "
                "**Admin** — full access to all outlets, users, and settings.",
                tone="info",
            )
            with st.form("create_user_form"):
                cu1, cu2, cu3 = st.columns(3)
                with cu1:
                    cu_username = st.text_input("Username")
                with cu2:
                    cu_role = st.selectbox("Role", ["manager", "admin"])
                with cu3:
                    cu_loc_opts = {
                        loc["id"]: loc["name"] for loc in (ctx.all_locs or [])
                    }
                    cu_loc_opts[0] = "— none —"
                    cu_loc = st.selectbox(
                        "Home location",
                        options=[0] + [loc["id"] for loc in (ctx.all_locs or [])],
                        format_func=lambda i: cu_loc_opts.get(i, str(i)),
                    )
                pw1, pw2, em1 = st.columns(3)
                with pw1:
                    cu_password = st.text_input("Password", type="password")
                with pw2:
                    cu_confirm = st.text_input("Confirm password", type="password")
                with em1:
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

        with user_del_tab:
            if all_users:
                _current_user = st.session_state.username
                _target = user_by_name.get(selected_username) if all_users else None
                if _target and _target["username"] == _current_user:
                    info_banner("You cannot delete your own account.", tone="warning")
                elif _target:
                    info_banner(
                        f"This will permanently delete **{_target['username']}**. "
                        "Select the user via the pills above.",
                        tone="error",
                    )
                    if "_user_delete_result" in st.session_state:
                        ok, msg = st.session_state.pop("_user_delete_result")
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    if st.button("Delete user", key="del_user_btn", type="secondary"):
                        st.session_state["_pending_user_delete"] = _target["id"]

                    def _do_delete_user() -> None:
                        _id = st.session_state.get("_pending_user_delete")
                        ok, msg = database.delete_user(_id, _current_user)
                        st.session_state.pop("_pending_user_delete", None)
                        st.session_state["_user_delete_result"] = (ok, msg)
                        st.rerun()

                    confirm_dialog(
                        message=(
                            f"**Confirm:** permanently delete user "
                            f"**{_target['username']}**?"
                        ),
                        confirm_key="_pending_user_delete",
                        on_confirm=_do_delete_user,
                        confirm_label="Yes, delete user",
                    )
            else:
                st.caption("No users to delete.")

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

