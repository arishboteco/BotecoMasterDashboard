"""Upload tab — POS file upload, detection, import, and data management."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime

import pandas as pd
import streamlit as st

import database
import file_detector
import utils
from components import (
    classed_container,
    divider,
    info_banner,
    page_shell,
    primary_action_bar,
    section_title,
    workflow_progress,
)
from components.footfall_editor import render_footfall_editor
from services import cache_invalidation, upload_service
from services.upload_service import ImportOptions
from tabs import TabContext

logger = logging.getLogger("boteco")


def _files_fingerprint(uploaded_files) -> str:
    """Hash file names + sizes to detect when the file set changes."""
    h = hashlib.md5()
    for f in sorted(uploaded_files, key=lambda x: x.name):
        h.update(f.name.encode())
        h.update(str(f.size).encode())
    return h.hexdigest()


def _render_outlet_completeness(upload_result, loc_name_map: dict) -> None:
    """Show a per-outlet table summarising which report types were detected."""

    all_loc_ids = set(upload_result.location_results.keys())
    cat_loc_ids: set = set()
    cat_by_loc = getattr(upload_result, "category_by_loc", {})
    new_flow_meta = getattr(upload_result, "new_flow_meta", {})
    if cat_by_loc:
        cat_loc_ids = set(cat_by_loc.keys())
    all_loc_ids |= cat_loc_ids

    growth_locs_from_meta: set = set()
    item_locs_from_meta: set = set()
    comp_locs: set = set()
    for meta in new_flow_meta.values():
        loc_id = meta.get("detected_location_id")
        if not loc_id:
            continue
        file_type = str(meta.get("file_type", ""))
        source_report = str(meta.get("source_report", ""))
        if file_type == "growth_report_day_wise":
            growth_locs_from_meta.add(loc_id)
        elif file_type == "item_order_details":
            item_locs_from_meta.add(loc_id)
        if file_type == "order_comp_summary" or source_report == "order_comp_summary":
            comp_locs.add(loc_id)

    all_loc_ids |= growth_locs_from_meta | item_locs_from_meta | comp_locs

    if not all_loc_ids:
        return

    # Build completeness per outlet
    growth_locs: set = set()
    item_locs: set = set(cat_loc_ids)
    for loc_id, day_results in upload_result.location_results.items():
        for dr in day_results:
            if "growth_report_day_wise" in (dr.source_kinds or []):
                growth_locs.add(loc_id)
                break
    growth_locs |= growth_locs_from_meta
    item_locs |= item_locs_from_meta

    lines = []
    for loc_id in sorted(all_loc_ids):
        name = loc_name_map.get(loc_id, f"Outlet {loc_id}")
        growth_ok = "✅ Growth Report" if loc_id in growth_locs else "❌ Growth Report missing"
        item_ok = "✅ Item Report" if loc_id in item_locs else "❌ Item Report missing"
        comp_ok = "✅ Comp Report" if loc_id in comp_locs else "❌ Comp Report missing"
        lines.append(f"**{name}**\n{growth_ok} · {item_ok} · {comp_ok}")

    if lines:
        with st.expander("Outlet completeness", expanded=True):
            for line in lines:
                st.markdown(line)


def _render_file_details(upload_result) -> None:
    """Show per-file details: outlet, period, row count, any errors."""
    new_flow_meta = getattr(upload_result, "new_flow_meta", {})
    if not new_flow_meta:
        return
    rows = []
    for fr in upload_result.files:
        if fr.kind not in {
            "growth_report_day_wise",
            "item_order_details",
            "order_comp_summary",
        }:
            continue
        meta = new_flow_meta.get(fr.filename, {})
        rows.append(
            {
                "File": fr.filename,
                "Type": fr.kind_label[:35],
                "Outlet": meta.get("detected_location_name", "—"),
                "Period": (
                    f"{meta.get('period_start', '?')} → {meta.get('period_end', '?')}"
                    if meta.get("period_start")
                    else "—"
                ),
                "Rows": meta.get("row_count", "—"),
                "Status": "❌ " + (fr.error or "error") if fr.error else "✅ OK",
            }
        )
    if rows:
        import pandas as _pd

        with st.expander("File details", expanded=False):
            st.dataframe(_pd.DataFrame(rows), hide_index=True)


def _render_import_history(ctx: TabContext) -> None:
    """Render the recent import history footer section."""
    section_title(
        "Recent import activity",
        "Last 10 saved files for this outlet scope.",
        icon="history",
    )
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
        st.dataframe(hdf, width="stretch", hide_index=True)
    else:
        st.caption("No imports yet for this outlet.")


def _render_post_import_footfall(shell, ctx: TabContext) -> None:
    """Render the optional footfall entry step shown after a successful import."""
    state = st.session_state.get("_post_import_state", {})
    dates_by_loc: dict = state.get("dates_by_loc", {})
    saved_days: int = state.get("saved_days", 0)
    skipped: int = state.get("skipped", 0)
    note_count: int = state.get("note_count", 0)
    edited_by = str(st.session_state.get("username") or "")

    with shell.content:
        st.success(
            f"Import complete — **{saved_days}** day(s) saved"
            + (f", {skipped} skipped" if skipped else "")
            + "."
        )

        divider()
        section_title("Step 2: Footfall covers (optional)", icon="people")
        st.caption(
            "Enter Lunch and Dinner cover counts for the dates you just imported. "
            "Rows marked **✓ Set** already have overrides saved. "
            "Leave values blank to use POS-derived counts. "
            "Click **Done** to finish without entering footfall."
        )

        any_changed = False
        for loc_id, loc_data in dates_by_loc.items():
            loc_name: str = loc_data["name"]
            dates: list = sorted(loc_data["dates"])

            if len(dates_by_loc) > 1:
                st.markdown(f"##### {loc_name}")

            changed = render_footfall_editor(
                location_id=int(loc_id),
                dates=dates,
                loc_name=loc_name,
                edited_by=edited_by,
                key_prefix=f"upload_footfall_{loc_id}_",
            )
            if changed:
                any_changed = True

        divider()
        if st.button("Done", key="post_import_done_btn", type="primary"):
            st.session_state.pop("_post_import_state", None)
            st.session_state.pop("_upload_result", None)
            st.session_state.pop("_upload_fingerprint", None)
            st.session_state["_import_summary_flash"] = (saved_days, skipped, note_count)
            st.rerun()

        if any_changed:
            st.rerun()


def render(ctx: TabContext) -> None:
    """Render the Upload tab UI and handle import logic."""
    shell = page_shell()

    # If we're in the post-import footfall step, render that and stop.
    if st.session_state.get("_post_import_state"):
        _render_post_import_footfall(shell, ctx)
        with shell.footer_actions:
            _render_import_history(ctx)
        return

    flash = st.session_state.pop("_import_summary_flash", None)
    if flash is not None:
        sd, sk, nc = flash
        st.success(
            f"Last import: **{sd}** day(s) saved, **{sk}** day(s) skipped, **{nc}** note(s)."
        )

    with shell.filters:
        with classed_container(
            "tab-upload-mobile-filters",
            "mobile-layout-stack",
            "mobile-layout-filters",
            "mobile-layout-secondary",
        ):
            section_title(
                "Upload source files",
                "Drop any Petpooja exports (CSV/XLS/XLSX).",
                icon="upload_file",
            )
            uploaded_files = st.file_uploader(
                "Petpooja exports (XLSX, XLS, CSV — any report type)",
                type=["xlsx", "xls", "csv"],
                accept_multiple_files=True,
                help=(
                    "Drop Item Reports, Dynamic Reports, Timing Reports, Order Summaries, "
                    "Flash Reports — anything from Petpooja. "
                    "The system figures out what each file is."
                ),
                key="smart_upload_files",
                label_visibility="collapsed",
            )

            workflow_progress(
                total_steps=3,
                current_step=1 if not uploaded_files else 2,
                stage_label="Upload progress",
            )

    with shell.content:
        if not uploaded_files:
            # Clear cached result when files are removed
            st.session_state.pop("_upload_result", None)
            st.session_state.pop("_upload_fingerprint", None)
            info_banner(
                "No files selected yet. Download reports from Petpooja "
                "and drop any combination here.",
                tone="neutral",
                icon="upload",
            )

        if uploaded_files:
            section_title("Review detected files", icon="fact_check")
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
                    "**Growth Report Day Wise** or **Item Report With Customer/Order Details**."
                )

            if importable_count > 0:
                # Cache process_smart_upload in session_state to avoid re-parsing
                # on every Streamlit rerun (checkbox toggle, widget interaction, etc.)
                fp = _files_fingerprint(uploaded_files)
                if (
                    st.session_state.get("_upload_fingerprint") != fp
                    or "_upload_result" not in st.session_state
                ):
                    total_mb = sum(len(c) for _, c in files_payload) / (1024 * 1024)
                    _parse_label = (
                        f"Parsing {importable_count} file"
                        f"{'s' if importable_count != 1 else ''} "
                        f"({total_mb:.1f} MB)…"
                    )
                    with st.status(_parse_label, expanded=False) as _status:
                        upload_result = upload_service.preview_upload(
                            files_payload, ctx.location_id
                        )
                        _days = sum(len(days) for days in upload_result.location_results.values())
                        _outlets = len(upload_result.location_results)
                        _status.update(
                            label=(
                                f"Parsed {importable_count} file"
                                f"{'s' if importable_count != 1 else ''} → "
                                f"{_days} day{'s' if _days != 1 else ''} "
                                f"across {_outlets} outlet"
                                f"{'s' if _outlets != 1 else ''}"
                            ),
                            state="complete",
                        )
                    st.session_state["_upload_result"] = upload_result
                    st.session_state["_upload_fingerprint"] = fp
                else:
                    upload_result = st.session_state["_upload_result"]

                loc_name_map = {loc["id"]: loc["name"] for loc in ctx.all_locs}

                # Show detected outlets and per-outlet report completeness
                if upload_result.location_results:
                    outlet_names = [
                        loc_name_map.get(lid, str(lid)) for lid in upload_result.location_results
                    ]
                    st.info(f"Auto-detected outlets: **{'**, **'.join(outlet_names)}**")

                _render_outlet_completeness(upload_result, loc_name_map)
                _render_file_details(upload_result)

                # Collect overlaps — one batch query per location instead of per-day
                overlap_rows = upload_service.find_overlaps(upload_result)

                must_confirm_replace = len(overlap_rows) > 0
                if overlap_rows:
                    lines = "\n".join(
                        f"- **{loc_name_map.get(lid, str(lid))}** \u2014 **{d}** \u2014 "
                        f"saved net sales {utils.format_currency(v)}"
                        for lid, d, v in overlap_rows
                    )
                    st.warning("These dates already have data and will be **replaced**:\n" + lines)

                if must_confirm_replace:
                    confirm_replace = st.checkbox(
                        "I understand existing days listed above will be replaced.",
                        key="confirm_replace_smart",
                    )
                else:
                    confirm_replace = True

                import_blocked = must_confirm_replace and not confirm_replace

                with classed_container(
                    "tab-upload-mobile-primary-action",
                    "mobile-layout-primary-action",
                ):
                    import_clicked, _ = primary_action_bar(
                        f"Import {importable_count} file(s) \u2192 save to database",
                        primary_key="smart_import_btn",
                        primary_disabled=import_blocked,
                    )
                if import_clicked:
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

                        _save_total_days = sum(
                            len(days) for days in upload_result.location_results.values()
                        )
                        _save_label = (
                            f"Saving {_save_total_days} day"
                            f"{'s' if _save_total_days != 1 else ''} "
                            "to database…"
                        )
                        with st.status(_save_label, expanded=False) as _save_status:
                            saved_days, skipped_validation, save_messages = (
                                upload_service.import_upload(
                                    upload_result,
                                    ctx,
                                    options=ImportOptions(uploaded_by=uploaded_by),
                                )
                            )
                            _save_status.update(
                                label=(
                                    f"Saved {saved_days} day"
                                    f"{'s' if saved_days != 1 else ''}"
                                    + (
                                        f" · {skipped_validation} skipped"
                                        if skipped_validation
                                        else ""
                                    )
                                ),
                                state="complete",
                            )
                        total_saved = saved_days
                        total_skipped = skipped_validation
                        outlets = ", ".join(
                            loc_name_map.get(lid, str(lid))
                            for lid in upload_result.location_results
                        )
                        all_save_messages = [
                            f"**Outlets:** {outlets} \u2014 {saved_days} day(s) saved, "
                            f"{skipped_validation} day(s) skipped."
                        ]
                        all_save_messages.extend(save_messages)

                        for msg in all_save_messages:
                            st.info(msg)

                        # Show data quality warnings from validation
                        for _lid, day_results in upload_result.location_results.items():
                            for day_result in day_results:
                                for w in day_result.warnings or []:
                                    st.warning(f"⚠️ {day_result.date}: {w}")
                                # Inform when Item Report fallback parser was used
                                # (50/50 CGST/SGST split)
                                if "item_order_details" in (
                                    day_result.source_kinds or []
                                ) and "dynamic_report" not in (day_result.source_kinds or []):
                                    st.info(
                                        "ℹ️ Tax split estimated as 50/50 CGST/SGST for "
                                        f"{day_result.date}. For exact breakdown, "
                                        "upload the Dynamic Report CSV."
                                    )

                        cache_invalidation.invalidate_after_import(
                            list(upload_result.location_results.keys())
                        )

                        note_count = len(upload_result.global_notes)

                        if total_saved > 0:
                            most_recent_date = database.get_most_recent_date_with_data(
                                ctx.report_loc_ids
                            )
                            if most_recent_date:
                                latest_date = datetime.strptime(most_recent_date, "%Y-%m-%d").date()
                                st.session_state["report_date"] = latest_date
                                st.session_state["report_date_picker"] = latest_date

                        # Collect imported dates per location for the footfall step
                        loc_name_map_local = {loc["id"]: loc["name"] for loc in ctx.all_locs}
                        dates_by_loc = {
                            loc_id: {
                                "name": loc_name_map_local.get(loc_id, f"Outlet {loc_id}"),
                                "dates": [
                                    dr.date
                                    for dr in day_results
                                    if not dr.errors
                                ],
                            }
                            for loc_id, day_results in upload_result.location_results.items()
                        }
                        # Only include locations that actually had days saved
                        dates_by_loc = {
                            k: v for k, v in dates_by_loc.items() if v["dates"]
                        }

                        # Move to post-import footfall step (clears upload cache on Done)
                        st.session_state["_post_import_state"] = {
                            "saved_days": total_saved,
                            "skipped": total_skipped,
                            "note_count": note_count,
                            "dates_by_loc": dates_by_loc,
                        }
                        st.rerun()

    with shell.footer_actions:
        _render_import_history(ctx)
