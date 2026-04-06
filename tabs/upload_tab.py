"""Upload tab — POS file upload, detection, import, and data management."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

import config
import database
import file_detector
import smart_upload
import utils
from auth import is_admin
from tabs import TabContext

logger = logging.getLogger("boteco")


def render(ctx: TabContext) -> None:
    """Render the Upload tab UI and handle import logic."""
    st.header("Upload POS Data")

    _imp_nm = (
        ctx.import_location_settings.get("name", "")
        if ctx.import_location_settings
        else ""
    ) or str(ctx.import_loc_id)

    st.caption(
        f"Drop **any** Petpooja exports below — the system auto-detects file types. "
        f"Importing to: **{_imp_nm}**"
    )

    flash = st.session_state.pop("_import_summary_flash", None)
    if flash is not None:
        sd, sk, nc = flash
        st.success(
            f"Last import: **{sd}** day(s) saved, **{sk}** day(s) skipped, "
            f"**{nc}** note(s)."
        )

    with st.expander("How it works", expanded=False, key="how_it_works_expander"):
        st.markdown(
            "**Just drop all your Petpooja downloads at once.** The system will:\n\n"
            "1. **Auto-detect** each file type from its content (not filename)\n"
            "2. **Import** Dynamic Report CSV (primary data) and Item Reports (fallback)\n"
            "3. **Skip** redundant files (Group Wise, All Restaurant, Comparison)\n"
            "4. **Merge** data for the same date from multiple files\n\n"
            "Saving for the same **location + date** overwrites that day's data."
        )

    st.markdown("### Drop your files")
    uploaded_files = st.file_uploader(
        "Petpooja exports (XLSX, XLS, CSV — any report type)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        help=(
            "Drop Item Reports, Dynamic Reports, Timing Reports, Order Summaries, "
            "Flash Reports — anything from Petpooja. The system figures out what each file is."
        ),
        key="smart_upload_files",
        label_visibility="collapsed",
    )

    if not uploaded_files:
        st.markdown(
            '<div class="empty-upload-hint">'
            "No files selected. Download your reports from Petpooja and "
            "drop them all here — any combination works."
            "</div>",
            unsafe_allow_html=True,
        )

    if uploaded_files:
        st.markdown("#### Detected files")
        files_payload = [(f.name, f.getvalue()) for f in uploaded_files]

        importable_count = 0
        for fname, content in files_payload:
            kind, label = file_detector.detect_and_describe(content, fname)
            if file_detector.is_importable(kind):
                st.success(f"\u2705 **{fname}** \u2192 {label}")
                importable_count += 1
            elif file_detector.is_skippable(kind):
                st.caption(f"\u23ed **{fname}** \u2192 {label} (will skip)")
            else:
                st.warning(f"\u2753 **{fname}** \u2192 {label}")

        if importable_count == 0:
            st.error(
                "No importable files detected. Make sure you include a "
                "**Dynamic Report CSV** or **Item Report With Customer/Order Details**."
            )

        if importable_count > 0:
            upload_result = smart_upload.process_smart_upload(
                files_payload, ctx.import_loc_id
            )

            overlap_rows: list = []
            for day in upload_result.days:
                if day.errors:
                    continue
                prev_net = database.peek_daily_net_sales(ctx.import_loc_id, day.date)
                if prev_net is not None:
                    overlap_rows.append((day.date, prev_net))

            must_confirm_replace = len(overlap_rows) > 0
            if overlap_rows:
                lines = "\n".join(
                    f"- **{d}** \u2014 saved net sales {utils.format_currency(n)}"
                    for d, n in overlap_rows
                )
                st.warning(
                    f"These dates already have data for **{_imp_nm}** "
                    f"and will be **replaced**:\n{lines}"
                )

            if must_confirm_replace:
                confirm_replace = st.checkbox(
                    "I understand existing days listed above will be replaced.",
                    key="confirm_replace_smart",
                )
            else:
                confirm_replace = True

            import_blocked = must_confirm_replace and not confirm_replace

            if st.button(
                f"Import {importable_count} file(s) \u2192 save to database",
                type="primary",
                key="smart_import_btn",
                disabled=import_blocked,
            ):
                if must_confirm_replace and not confirm_replace:
                    st.error("Confirm replacement above to import.")
                else:
                    for note in upload_result.global_notes:
                        st.info(note)
                    for fr in upload_result.files:
                        for note in fr.notes:
                            st.caption(note)
                        if fr.error:
                            st.error(f"**{fr.filename}**: {fr.error}")

                    monthly_tgt = (
                        ctx.import_location_settings.get(
                            "target_monthly_sales", config.MONTHLY_TARGET
                        )
                        if ctx.import_location_settings
                        else config.MONTHLY_TARGET
                    )
                    daily_tgt = (
                        ctx.import_location_settings.get(
                            "target_daily_sales", config.DAILY_TARGET
                        )
                        if ctx.import_location_settings
                        else config.DAILY_TARGET
                    )
                    sc_setting = (
                        ctx.import_location_settings.get("seat_count")
                        if ctx.import_location_settings
                        else None
                    )
                    uploaded_by = st.session_state.get("username") or "user"
                    saved_days, skipped_validation, save_messages = (
                        smart_upload.save_smart_upload_results(
                            upload_result,
                            ctx.import_loc_id,
                            uploaded_by,
                            monthly_target=float(monthly_tgt),
                            daily_target=float(daily_tgt),
                            seat_count=(int(sc_setting) if sc_setting else None),
                        )
                    )

                    for msg in save_messages:
                        if msg.startswith("Saved "):
                            st.success(msg)
                        else:
                            st.error(msg)

                    note_count = len(upload_result.global_notes)
                    st.info(
                        f"**Import complete:** {saved_days} day(s) saved, "
                        f"{skipped_validation} day(s) skipped."
                    )

                    if saved_days > 0:
                        most_recent_date = database.get_most_recent_date_with_data(
                            ctx.report_loc_ids
                        )
                        if most_recent_date:
                            latest_date = datetime.strptime(
                                most_recent_date, "%Y-%m-%d"
                            ).date()
                            st.session_state["report_date"] = latest_date
                            st.session_state["report_date_picker"] = latest_date

                        st.session_state["_import_summary_flash"] = (
                            saved_days,
                            skipped_validation,
                            note_count,
                        )
                        st.rerun()

    st.markdown("---")
    st.markdown("### Remove incorrect data")
    st.caption(
        "Deletes the saved summary for one outlet and date (including category and service "
        "breakdown). Upload history is kept for audit."
    )
    if is_admin() and ctx.all_locs:
        _sort_del = sorted(ctx.all_locs, key=lambda x: x["name"])
        _del_name = {loc["id"]: loc["name"] for loc in _sort_del}
        del_col1, del_col2, del_col3 = st.columns([1, 1, 1])
        with del_col1:
            delete_target_loc = st.selectbox(
                "Outlet",
                options=[loc["id"] for loc in _sort_del],
                format_func=lambda i: _del_name[i],
                key="delete_day_outlet",
            )
        with del_col2:
            delete_target_date = st.date_input(
                "Date to remove",
                value=datetime.now().date(),
                key="delete_day_date_pick",
                format="DD/MM/YYYY",
            )
        with del_col3:
            st.write("")
            st.write("")
            del_date_str = delete_target_date.strftime("%Y-%m-%d")
            del_date_display = delete_target_date.strftime("%d %b %Y")
            st.markdown(
                '<style>.stButton > button[key="delete_day_btn"] { '
                "background-color: transparent !important; "
                "color: #dc2626 !important; "
                "border: 1.5px solid #fca5a5 !important; "
                "font-weight: 500 !important; } "
                '.stButton > button[key="delete_day_btn"]:hover { '
                "background-color: #fef2f2 !important; "
                "border-color: #dc2626 !important; "
                "color: #b91c1c !important; } "
                "</style>",
                unsafe_allow_html=True,
            )
            if st.button("\u26a0\ufe0f Delete this day's data", key="delete_day_btn"):
                if delete_target_loc is None:
                    st.error("Select an outlet before deleting data.")
                else:
                    st.session_state["_pending_delete"] = (
                        int(delete_target_loc),
                        del_date_str,
                        del_date_display,
                    )
        pend = st.session_state.get("_pending_delete")
        if pend:
            ploc, pdate, pdate_disp = pend
            pn = _del_name.get(ploc, str(ploc))
            st.warning(
                f"\u26a0\ufe0f **Warning:** This will permanently delete all saved data for "
                f"**{pn}** on **{pdate_disp}**. This action cannot be undone."
            )
            dc1, dc2 = st.columns(2)
            with dc1:
                st.markdown(
                    '<style>.stButton > button[key="delete_confirm_yes"] { '
                    "background-color: #dc2626 !important; "
                    "color: #fff !important; "
                    "border: none !important; } "
                    '.stButton > button[key="delete_confirm_yes"]:hover { '
                    "background-color: #b91c1c !important; } "
                    "</style>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "\u26a0\ufe0f Yes, delete permanently",
                    key="delete_confirm_yes",
                    type="primary",
                ):
                    removed = database.delete_daily_summary_for_location_date(
                        ploc, pdate
                    )
                    st.session_state.pop("_pending_delete", None)
                    if removed:
                        st.success(
                            "Deleted. You can re-import a correct file if needed."
                        )
                    else:
                        st.info("No saved row existed for that outlet and date.")
                    st.rerun()
            with dc2:
                if st.button("Cancel", key="delete_confirm_no"):
                    st.session_state.pop("_pending_delete", None)
                    st.rerun()
    elif is_admin():
        st.caption("No outlets configured.")
    else:
        st.caption("Contact an admin to remove a mistaken import.")

    st.markdown("---")
    st.markdown("### Recent Entries")
    history = database.get_upload_history(ctx.import_loc_id, 10)
    if history:
        hdf = pd.DataFrame(history)
        drop_cols = [c for c in ("id", "location_id") if c in hdf.columns]
        if drop_cols:
            hdf = hdf.drop(columns=drop_cols)
        rename = {
            "date": "Day",
            "filename": "File",
            "file_type": "Type",
            "uploaded_by": "Imported by",
            "uploaded_at": "When",
        }
        hdf = hdf.rename(columns={k: v for k, v in rename.items() if k in hdf.columns})
        if "Day" in hdf.columns:
            hdf["Day"] = hdf["Day"].apply(
                lambda x: (
                    datetime.strptime(x[:10], "%Y-%m-%d").strftime("%d %b %Y")
                    if pd.notna(x)
                    else x
                )
            )
        st.dataframe(hdf, use_container_width=True, hide_index=True)
    else:
        st.caption("No imports yet for this outlet.")
