"""Upload tab — POS file upload, detection, import, covers sync, and data management."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

import config
import customer_report_parser
import database
import file_detector
import pos_parser as parser
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

    with st.expander("How it works", expanded=False):
        st.markdown(
            "**Just drop all your Petpooja downloads at once.** The system will:\n\n"
            "1. **Auto-detect** each file type from its content (not filename)\n"
            "2. **Import** Dynamic Report CSV (primary data), Item Reports (fallback), "
            "Customer Reports (covers), and Timing Reports (meal breakdown)\n"
            "3. **Skip** redundant files (Group Wise, All Restaurant, Comparison)\n"
            "4. **Merge** data for the same date from multiple files\n\n"
            "Saving for the same **location + date** overwrites that day's data."
        )

    # ── Single upload zone for ALL file types ──
    st.markdown("### Drop your files")
    uploaded_files = st.file_uploader(
        "Petpooja exports (XLSX, XLS, CSV — any report type)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        help=(
            "Drop Item Reports, Customer Reports, Timing Reports, Order Summaries, "
            "Flash Reports — anything from Petpooja. The system figures out what each file is."
        ),
        key="smart_upload_files",
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
        # ── Phase 1: Detect and display what we found ──
        st.markdown("#### Detected files")
        files_payload = [(f.name, f.getvalue()) for f in uploaded_files]

        importable_count = 0
        for fname, content in files_payload:
            kind, label = file_detector.detect_and_describe(content, fname)
            if file_detector.is_importable(kind):
                st.success(f"\u2705 **{fname}** \u2192 {label}")
                importable_count += 1
            elif file_detector.is_skippable(kind):
                st.caption(
                    f"\u23ed **{fname}** \u2192 {label} (will skip \u2014 redundant)"
                )
            else:
                st.warning(f"\u2753 **{fname}** \u2192 {label}")

        if importable_count == 0:
            st.error(
                "No importable files detected. Make sure you include a "
                "**Dynamic Report CSV** or **Item Report With Customer/Order Details** — one of these is required as the primary data source."
            )

        # ── Phase 2: Pre-parse to find dates and check overlaps ──
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

            # ── Phase 3: Import button ──
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

                    # Build covers lookup
                    locs_for_cr = database.get_all_locations()
                    cr_path = config.resolve_customer_report_path()
                    cr_lookup: dict = {}
                    cr_notes: list = []
                    if cr_path:
                        cr_lookup, cr_notes = (
                            customer_report_parser.load_lookup_from_path(
                                cr_path, locs_for_cr
                            )
                        )
                    # Customer report detected in the upload batch
                    if upload_result.customer_content is not None:
                        up_lookup, up_notes = (
                            customer_report_parser.build_covers_lookup(
                                upload_result.customer_content, locs_for_cr
                            )
                        )
                        cr_lookup = {**cr_lookup, **up_lookup}
                        cr_notes.extend(up_notes)
                    for note in cr_notes:
                        st.caption(note)

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
                    saved_any = False
                    saved_days = 0
                    skipped_validation = 0

                    for day in upload_result.days:
                        if day.errors:
                            skipped_validation += 1
                            st.error(
                                f"{day.date}: "
                                + " \u00b7 ".join(day.errors)
                                + " \u2014 check that this date has Success rows with "
                                "Sub Total / Final Total in your Item Report."
                            )
                            continue

                        merged = dict(day.merged)
                        merged["covers"] = 0
                        merged["lunch_covers"] = None
                        merged["dinner_covers"] = None
                        merged = customer_report_parser.apply_covers_overlay(
                            merged, ctx.import_loc_id, cr_lookup
                        )
                        merged["target"] = daily_tgt
                        if sc_setting:
                            merged["seat_count"] = int(sc_setting)
                        merged = parser.calculate_derived_metrics(merged)
                        merged.pop("seat_count", None)
                        y_m = [int(x) for x in day.date.split("-")[:2]]
                        mtd = parser.calculate_mtd_metrics(
                            ctx.import_loc_id,
                            monthly_tgt,
                            year=y_m[0],
                            month=y_m[1],
                            as_of_date=day.date,
                        )
                        merged.update(mtd)
                        database.save_daily_summary(ctx.import_loc_id, merged)

                        # Determine primary file type for this day's data
                        primary_kind = "dynamic_report"
                        for fr in upload_result.files:
                            if fr.importable and fr.kind in (
                                "dynamic_report",
                                "item_order_details",
                            ):
                                primary_kind = fr.kind
                                break

                        fnames = ", ".join(
                            fr.filename
                            for fr in upload_result.files
                            if fr.importable and fr.kind != "customer_report"
                        )
                        if len(fnames) > 180:
                            fnames = fnames[:177] + "..."
                        database.save_upload_record(
                            ctx.import_loc_id,
                            day.date,
                            fnames,
                            primary_kind,
                            uploaded_by,
                        )
                        st.success(f"Saved data for {day.date}")
                        saved_any = True
                        saved_days += 1

                    note_count = len(upload_result.global_notes)
                    st.info(
                        f"**Import complete:** {saved_days} day(s) saved, "
                        f"{skipped_validation} day(s) skipped."
                    )

                    if saved_any:
                        st.session_state["_import_summary_flash"] = (
                            saved_days,
                            skipped_validation,
                            note_count,
                        )
                        st.rerun()

    # ── Covers-only sync ──
    st.markdown("---")
    st.markdown("### Sync covers only")
    st.caption(
        "Updates covers on existing saved days from the customer report "
        "without re-importing POS data."
    )
    cr_path_sync = config.resolve_customer_report_path()
    customer_report_upload_sync = st.file_uploader(
        "Customer report for covers (optional XLSX)",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        help="Overrides the configured path for cover counts.",
        key="customer_report_upload_sync",
    )
    # Debug mode toggle for troubleshooting
    debug_covers = st.checkbox(
        "Enable debug logging",
        value=False,
        key="debug_covers_sync",
        help="Show detailed parsing information for troubleshooting",
    )
    if cr_path_sync:
        st.caption(f"Configured customer report path: `{cr_path_sync}`")
    if st.button(
        "Apply covers from customer report",
        key="sync_covers_only",
        help="Updates covers (and lunch/dinner if present) on existing saved days; no POS upload.",
    ):
        locs_for_cr2 = database.get_all_locations()
        cr_lookup2: dict = {}
        notes2: list = []
        if cr_path_sync:
            cr_lookup2, notes2 = customer_report_parser.load_lookup_from_path(
                cr_path_sync, locs_for_cr2, debug=debug_covers
            )
        if customer_report_upload_sync is not None:
            up2, n2 = customer_report_parser.build_covers_lookup(
                customer_report_upload_sync.getvalue(),
                locs_for_cr2,
                debug=debug_covers,
            )
            cr_lookup2 = {**cr_lookup2, **up2}
            notes2.extend(n2)
        updated = 0
        for (lid, d), ent in cr_lookup2.items():
            ok2 = database.update_daily_summary_covers_only(
                lid,
                d,
                int(ent.get("covers") or 0),
                ent.get("lunch_covers"),
                ent.get("dinner_covers"),
            )
            if ok2:
                updated += 1
        for n in notes2:
            st.info(n)
        st.success(f"Updated covers on **{updated}** saved day(s).")
        st.rerun()

    # ── Remove incorrect data ──
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
                value=datetime.now(),
                key="delete_day_date_pick",
            )
        with del_col3:
            st.write("")
            st.write("")
            del_date_str = delete_target_date.strftime("%Y-%m-%d")
            if st.button("Delete this day's data", key="delete_day_btn"):
                st.session_state["_pending_delete"] = (
                    int(delete_target_loc),
                    del_date_str,
                )
        pend = st.session_state.get("_pending_delete")
        if pend:
            ploc, pdate = pend
            pn = _del_name.get(ploc, str(ploc))
            st.error(
                f"**Confirm:** permanently delete saved data for **{pn}** on **{pdate}**?"
            )
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("Yes, delete", key="delete_confirm_yes", type="primary"):
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

    # ── Recent uploads ──
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
        st.dataframe(hdf, use_container_width=True, hide_index=True)
    else:
        st.caption("No imports yet for this outlet.")
