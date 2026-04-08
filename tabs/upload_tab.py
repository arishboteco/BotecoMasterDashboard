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
from database_reads import clear_location_cache
from auth import is_admin
from tabs import TabContext

logger = logging.getLogger("boteco")


def render(ctx: TabContext) -> None:
    """Render the Upload tab UI and handle import logic."""
    st.header("Upload POS Data")

    st.caption(
        "Drop **any** Petpooja exports below — the system auto-detects file types "
        "and routes data to the correct outlet automatically."
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
            "2. **Auto-route** data to the correct outlet using the Restaurant column\n"
            "3. **Skip** redundant files (Group Wise, All Restaurant, Comparison)\n"
            "4. **Merge** data for the same date from multiple files\n\n"
            "Saving for the same **outlet + date** overwrites that day's data."
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
                files_payload,
                ctx.location_id,
            )

            loc_name_map = {loc["id"]: loc["name"] for loc in ctx.all_locs}

            # Show detected outlets
            if upload_result.location_results:
                outlet_names = [
                    loc_name_map.get(lid, str(lid))
                    for lid in upload_result.location_results
                ]
                st.info(f"Auto-detected outlets: **{'**, **'.join(outlet_names)}**")

            # Collect overlaps across all locations
            overlap_rows: list = []
            for lid, days in upload_result.location_results.items():
                for day in days:
                    if day.errors:
                        continue
                    prev_net = database.peek_daily_net_sales(lid, day.date)
                    if prev_net is not None:
                        ovr_name = loc_name_map.get(lid, str(lid))
                        overlap_rows.append((ovr_name, day.date, prev_net))

            must_confirm_replace = len(overlap_rows) > 0
            if overlap_rows:
                lines = "\n".join(
                    f"- **{n}** — **{d}** — saved net sales {utils.format_currency(v)}"
                    for n, d, v in overlap_rows
                )
                st.warning(
                    "These dates already have data and will be **replaced**:\n" + lines
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

                    uploaded_by = st.session_state.get("username") or "user"
                    total_saved = 0
                    total_skipped = 0
                    all_save_messages: list = []

                    for lid, days in upload_result.location_results.items():
                        loc_settings = database.get_location_settings(lid)
                        monthly_tgt = (
                            loc_settings.get(
                                "target_monthly_sales", config.MONTHLY_TARGET
                            )
                            if loc_settings
                            else config.MONTHLY_TARGET
                        )
                        daily_tgt = (
                            loc_settings.get("target_daily_sales", config.DAILY_TARGET)
                            if loc_settings
                            else config.DAILY_TARGET
                        )
                        sc_setting = (
                            loc_settings.get("seat_count") if loc_settings else None
                        )

                        # Build a per-location SmartUploadResult for save function
                        loc_result = smart_upload.SmartUploadResult(
                            files=upload_result.files,
                            days=days,
                            global_notes=[],
                            location_results={lid: days},
                        )
                        saved_days, skipped_validation, save_messages = (
                            smart_upload.save_smart_upload_results(
                                loc_result,
                                lid,
                                uploaded_by,
                                monthly_target=float(monthly_tgt),
                                daily_target=float(daily_tgt),
                                seat_count=(int(sc_setting) if sc_setting else None),
                            )
                        )
                        total_saved += saved_days
                        total_skipped += skipped_validation
                        ovr_name = loc_name_map.get(lid, str(lid))
                        all_save_messages.append(
                            f"**{ovr_name}:** {saved_days} day(s) saved, "
                            f"{skipped_validation} day(s) skipped."
                        )

                    for lid in upload_result.location_results:
                        clear_location_cache(lid)

                    for msg in all_save_messages:
                        st.info(msg)

                    note_count = len(upload_result.global_notes)

                    if total_saved > 0:
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
                            total_saved,
                            total_skipped,
                            note_count,
                        )
                        st.rerun()

    st.markdown("---")
    st.markdown("### Recent Entries")
    history = database.get_upload_history(ctx.location_id, 10)
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
