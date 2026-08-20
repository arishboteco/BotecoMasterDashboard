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
    KpiMetric,
    classed_container,
    data_table,
    divider,
    empty_state,
    kpi_row,
    page_shell,
    primary_action_bar,
    section_title,
)
from components.footfall_editor import render_footfall_editor
from services import cache_invalidation, upload_service
from services.upload_service import ImportOptions, ImportPlan
from tabs import TabContext

logger = logging.getLogger("boteco")


def _files_fingerprint(uploaded_files) -> str:
    """Hash file names + sizes to detect when the file set changes."""
    h = hashlib.md5()
    for f in sorted(uploaded_files, key=lambda x: x.name):
        h.update(f.name.encode())
        h.update(str(f.size).encode())
    return h.hexdigest()


def _render_import_kpis(plan: ImportPlan, ready_files: int, total_files: int) -> None:
    """KPI strip giving an at-a-glance read of what a staged import will do."""
    with classed_container("tab-upload-mobile-kpis", "mobile-layout-stack"):
        kpi_row(
            [
                KpiMetric("Files ready", f"{ready_files} of {total_files}"),
                KpiMetric(
                    "Days to import",
                    str(plan.total_days),
                    delta=f"{plan.new_days} new" if plan.new_days else None,
                ),
                KpiMetric("Outlets", str(plan.outlet_count)),
                KpiMetric("Days replaced", str(plan.replace_days)),
            ]
        )


def _outlet_plan_dataframe(plan: ImportPlan) -> pd.DataFrame:
    rows = []
    for o in plan.outlets:
        reports = " · ".join(
            [
                "✅ Growth" if o.has_growth else "➖ Growth",
                "✅ Item" if o.has_item else "➖ Item",
                "✅ Comp" if o.has_comp else "➖ Comp",
            ]
        )
        period = f"{o.date_min} → {o.date_max}" if o.date_min else "—"
        rows.append(
            {
                "Outlet": o.location_name,
                "Reports": reports,
                "Period": period,
                "Days": o.total_days,
                "New": o.new_days,
                "Replacing": o.replace_days,
                "Net in file": utils.format_currency(o.incoming_net),
            }
        )
    return pd.DataFrame(rows)


def _render_replaced_dates(plan: ImportPlan) -> None:
    """Collapsed detail behind the headline replace-count — sorted by size of change."""
    if not plan.replaced:
        return
    with st.expander(f"Replaced dates ({len(plan.replaced)})", expanded=False):
        rdf = pd.DataFrame(
            [
                {
                    "Outlet": r.location_name,
                    "Date": r.date,
                    "Saved net": utils.format_currency(r.existing_net),
                    "Incoming net": utils.format_currency(r.incoming_net),
                    "Change": utils.format_currency(r.delta),
                }
                for r in plan.replaced
            ]
        )
        st.dataframe(rdf, hide_index=True, width="stretch")


def _render_import_plan(plan: ImportPlan) -> None:
    """Show what a staged import will do: headline, per-outlet table, replaced dates."""
    if not plan.outlets:
        return

    if not plan.has_replacements and not plan.has_coverage_warnings:
        st.success(
            f"Ready to import **{plan.total_days}** day(s) across **{plan.outlet_count}** "
            "outlet(s) — all new data, nothing will be overwritten."
        )
    else:
        parts = []
        if plan.has_replacements:
            parts.append(f"**{plan.replace_days}** day(s) will be **replaced**")
        if plan.has_coverage_warnings:
            gap_word = "gap" if len(plan.coverage_warnings) == 1 else "gaps"
            parts.append(f"**{len(plan.coverage_warnings)}** report coverage {gap_word} found")
        st.warning(" · ".join(parts) + " — review below before importing.")

    data_table(_outlet_plan_dataframe(plan), empty_message="No outlets detected.")

    for msg in plan.coverage_warnings:
        st.warning(msg)

    _render_replaced_dates(plan)


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
        detected_as = upload_service.report_type_label(str(meta.get("file_type") or ""))
        rows.append(
            {
                "File": fr.filename,
                "Type": fr.kind_label[:35],
                "Detected as": detected_as,
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


def _fmt_short_day(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date[:10], "%Y-%m-%d").strftime("%d %b")
    except ValueError:
        return iso_date


@st.cache_data(ttl=600, show_spinner=False)
def _cached_full_history_audit(
    location_ids: tuple[int, ...],
    loc_name_map_items: tuple[tuple[int, str], ...],
    as_of_date: str,
):
    from services import data_quality

    return data_quality.audit_full_history_report(
        list(location_ids), dict(loc_name_map_items), as_of_date
    )


def clear_upload_health_cache() -> None:
    """Invalidate the cached full-history audit — called after a save."""
    _cached_full_history_audit.clear()


_STATUS_ICON = {"complete": "✅", "partial": "◐", "missing": "✕"}


def _selected_checks(report, loc_id: int | None) -> list:
    """The check list to render — global, or one outlet's filtered subset."""
    if loc_id is None:
        return report.checks
    loc = next((lo for lo in report.locations if lo.location_id == loc_id), None)
    return loc.checks if loc else []


def _render_health_kpis(report, loc_id: int | None) -> None:
    checks = _selected_checks(report, loc_id)
    checks_total = sum(1 for c in checks if c.severity != "info")
    checks_passed = sum(1 for c in checks if c.severity != "info" and c.passed)

    if loc_id is None:
        days_audited = report.days_audited
        days_clean = report.days_clean
        outlets_clear = report.outlets_clear
        outlet_count = report.outlet_count
    else:
        loc = next((lo for lo in report.locations if lo.location_id == loc_id), None)
        days_audited = max((c.days_examined for c in checks), default=0)
        days_with_issues = len({f.date for c in checks for f in c.findings if c.severity != "info"})
        days_clean = max(days_audited - days_with_issues, 0)
        outlets_clear = 1 if (loc and not loc.has_issues) else 0
        outlet_count = 1

    with classed_container("tab-upload-mobile-kpis", "mobile-layout-stack"):
        kpi_row(
            [
                KpiMetric("Days audited", str(days_audited)),
                KpiMetric(
                    "Days fully clean",
                    str(days_clean),
                    delta=(
                        f"{days_audited - days_clean} with issues"
                        if days_audited > days_clean
                        else None
                    ),
                    delta_color="inverse",
                ),
                KpiMetric("Checks passed", f"{checks_passed} / {checks_total}"),
                KpiMetric("Outlets clear", f"{outlets_clear} of {outlet_count}"),
            ]
        )


def _render_health_checklist(report, loc_id: int | None) -> None:
    checks = _selected_checks(report, loc_id)
    rows = [
        {
            "Check": c.label,
            "What it proves": c.proves,
            "Days checked": c.days_examined,
            "Result": "✅ Pass" if c.passed else f"⚠️ {c.failed_days} day(s) flagged",
        }
        for c in checks
    ]
    data_table(pd.DataFrame(rows), empty_message="No checks have run yet.")


def _render_month_rollup(report, loc_id: int | None) -> None:
    months = (
        report.months
        if loc_id is None
        else [m for m in report.months if m.location_id == loc_id]
    )
    if not months:
        return
    with st.expander("Month-by-month history", expanded=False):
        rows = [
            {
                "Month": m.month,
                "Outlet": m.location_name,
                "Days": m.days,
                "Complete": m.days_clean,
                "Issues": m.issue_count,
            }
            for m in months
        ]
        data_table(pd.DataFrame(rows), empty_message="No history yet.")


def _render_health_findings(report, loc_id: int | None) -> None:
    checks = _selected_checks(report, loc_id)
    failing = [c for c in checks if not c.passed and c.severity != "info"]
    if not failing:
        st.caption("✅ No integrity issues found across the audited history.")
        return

    cap = 25
    for check in failing:
        findings = sorted(check.findings, key=lambda f: -f.magnitude)
        with st.expander(f"⚠️ {check.label} — {check.failed_days} day(s)", expanded=False):
            rows = [
                {
                    "Outlet": f.location_name,
                    "Date": _fmt_short_day(f.date),
                    "What's missing": f.detail,
                }
                for f in findings[:cap]
            ]
            data_table(pd.DataFrame(rows))
            if len(findings) > cap:
                st.caption(f"…and {len(findings) - cap} more")


def _render_coverage_grid(report, loc_id: int | None) -> None:
    """Pivot of outlet × day-of-month, one grid per month — the sanest way to see coverage."""
    if not report.day_status:
        return
    with st.expander("Coverage grid (by day)", expanded=False):
        st.caption("✅ complete · ◐ sales but no category breakdown · ✕ no upload found")
        loc_ids = [loc_id] if loc_id is not None else sorted({lid for lid, _ in report.day_status})
        loc_name_by_id = {lo.location_id: lo.location_name for lo in report.locations}
        months = sorted({d[:7] for _lid, d in report.day_status}, reverse=True)
        for month in months:
            days_in_month = sorted(
                {d for lid, d in report.day_status if lid in loc_ids and d[:7] == month}
            )
            if not days_in_month:
                continue
            st.markdown(f"**{month}**")
            rows = []
            for lid in loc_ids:
                row = {"Outlet": loc_name_by_id.get(lid, f"Outlet {lid}")}
                for d in days_in_month:
                    status = report.day_status.get((lid, d))
                    row[str(int(d[-2:]))] = _STATUS_ICON.get(status, "·")
                rows.append(row)
            data_table(pd.DataFrame(rows))


def _render_data_quality(ctx: TabContext) -> None:
    """Prove the saved data is sane: every check, every month, per outlet.

    Runs a fixed battery of integrity checks over the *whole* saved history
    (not just a recent window) and renders every one of them — including
    passing checks, with how many days each examined — so a clean result is
    demonstrated, not just asserted. Cached for 10 minutes; cleared after a
    save via ``clear_upload_health_cache``.
    """
    loc_name_map = {loc["id"]: loc["name"] for loc in ctx.all_locs}
    as_of = datetime.now().strftime("%Y-%m-%d")
    report = _cached_full_history_audit(
        tuple(ctx.report_loc_ids), tuple(sorted(loc_name_map.items())), as_of
    )

    if not report.checks:
        section_title(
            "Data health", "No saved data yet for this outlet scope.", icon="fact_check"
        )
        return

    section_title(
        "Data health",
        f"{report.window_start} → {report.window_end} · {report.outlet_count} outlet(s) · "
        f"{report.days_audited} days · {report.checks_total} checks",
        icon="fact_check",
    )

    filter_loc_id: int | None = None
    if len(ctx.report_loc_ids) > 1:
        outlet_options = {loc_name_map.get(lid, f"Outlet {lid}"): lid for lid in ctx.report_loc_ids}
        choice = st.segmented_control(
            "Outlet",
            ["All outlets", *outlet_options.keys()],
            default="All outlets",
            key="upload_health_outlet_filter",
        )
        if choice and choice != "All outlets":
            filter_loc_id = outlet_options[choice]

    _render_health_kpis(report, filter_loc_id)
    _render_health_checklist(report, filter_loc_id)
    _render_month_rollup(report, filter_loc_id)
    _render_health_findings(report, filter_loc_id)
    _render_coverage_grid(report, filter_loc_id)


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
        section_title("Step 2 of 2 — Footfall covers (optional)", icon="people")
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
            _render_data_quality(ctx)
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

    with shell.content:
        if not uploaded_files:
            # Clear cached result when files are removed
            st.session_state.pop("_upload_result", None)
            st.session_state.pop("_upload_fingerprint", None)
            empty_state(
                "Drop your Petpooja exports above",
                hint="Growth Report Day Wise, Item Report With Customer/Order "
                "Details, Complimentary Orders Summary — any combination works.",
                icon="upload_file",
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

                # Collect overlaps — one batch query per location instead of per-day
                overlap_rows = upload_service.find_overlaps(upload_result)
                plan = upload_service.build_import_plan(upload_result, overlap_rows, loc_name_map)

                total_files = len(upload_result.files)
                ready_files = sum(1 for fr in upload_result.files if not fr.error)
                with shell.kpi_row:
                    _render_import_kpis(plan, ready_files, total_files)

                _render_import_plan(plan)
                _render_file_details(upload_result)

                must_confirm_replace = plan.has_replacements
                if must_confirm_replace:
                    confirm_replace = st.checkbox(
                        f"I understand the {plan.replace_days} day(s) summarised above "
                        "will be replaced.",
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
        _render_data_quality(ctx)
        _render_import_history(ctx)
