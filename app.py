import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from io import BytesIO
import base64
import zipfile

import config
import customer_report_parser
import database
import file_detector
import pos_parser as parser
import scope
import sheet_reports as reports
import smart_upload
import utils
import auth
import clipboard_ui
import ui_theme

ui_theme.apply_plotly_theme()

# Page configuration
st.set_page_config(
    page_title="Boteco Dashboard",
    page_icon="🥂",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS (tokens align with .streamlit/config.toml)
st.markdown(
    """
<style>
    :root {
        --brand: #e94560;
        --brand-soft: #fff5f7;
        --surface: #f8f9fa;
        --surface-elevated: #ffffff;
        --text: #1a1a1a;
        --text-muted: #495057;
        --border-subtle: #dee2e6;
        --success-bg: #d4edda;
        --success-text: #155724;
        --success-border: #c3e6cb;
        --error-bg: #f8d7da;
        --error-text: #721c24;
        --error-border: #f5c6cb;
    }
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: var(--brand);
    }
    .metric-card {
        background: var(--surface);
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid var(--brand);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border-color: var(--border-subtle) !important;
        border-radius: 12px !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        background: var(--surface-elevated);
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border: 1px solid var(--border-subtle);
    }
    .success-box {
        background: var(--success-bg);
        color: var(--success-text);
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid var(--success-border);
    }
    .error-box {
        background: var(--error-bg);
        color: var(--error-text);
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid var(--error-border);
    }
    .upload-zone {
        border: 2px dashed var(--brand);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        text-align: left;
        background: var(--brand-soft);
        margin-bottom: 0.75rem;
    }
    .empty-upload-hint {
        color: var(--text-muted);
        font-size: 0.95rem;
        padding: 0.75rem 1rem;
        background: var(--surface);
        border-radius: 8px;
        border: 1px dashed var(--border-subtle);
        margin-top: 0.5rem;
    }
    [data-testid="stSidebar"] hr {
        margin: 0.75rem 0;
    }
    div[data-testid="stMetricValue"] {
        color: var(--brand);
        font-weight: bold;
    }
    .stCaption, [data-testid="stCaption"] {
        color: var(--text-muted);
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize authentication
auth.init_auth_state()

# Check if setup is needed
conn = database.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as count FROM users")
user_count = cursor.fetchone()["count"]
conn.close()

if user_count == 0:
    auth.show_setup_form()
else:
    if not auth.check_authentication():
        auth.show_login_form()
    else:
        # Render sidebar
        auth.render_auth_sidebar()
        st.sidebar.divider()
        st.sidebar.markdown("##### POS import")

        report_loc_ids = auth.get_report_location_ids()
        report_display_name = auth.get_report_display_name()
        all_locs = database.get_all_locations()
        if len(all_locs) > 1 and auth.is_admin():
            imp_labels = {
                str(loc["id"]): loc["name"]
                for loc in sorted(all_locs, key=lambda x: x["name"])
            }
            imp_keys = list(imp_labels.keys())
            default_imp = str(st.session_state.location_id)
            if default_imp not in imp_keys:
                default_imp = imp_keys[0]
            import_loc_id = int(
                st.sidebar.selectbox(
                    "POS import for",
                    options=imp_keys,
                    index=imp_keys.index(default_imp),
                    format_func=lambda k: imp_labels[k],
                    key="sidebar_import_location",
                )
            )
        elif len(all_locs) > 1:
            import_loc_id = int(st.session_state.location_id)
            imp_name = st.session_state.location_name or "your location"
            for loc in all_locs:
                if loc["id"] == import_loc_id:
                    imp_name = loc["name"]
                    break
            st.sidebar.caption(f"POS imports save to **{imp_name}**.")
        else:
            import_loc_id = (
                all_locs[0]["id"] if all_locs else st.session_state.location_id
            )

        import_location_settings = database.get_location_settings(import_loc_id)
        location_id = st.session_state.location_id

        # Tabs
        tab1, tab2, tab3, tab4 = st.tabs(["Upload", "Report", "Analytics", "Settings"])

        # ============ TAB 1: Upload Data ============
        with tab1:
            st.header("Upload POS Data")

            _imp_nm = (
                import_location_settings.get("name", "")
                if import_location_settings
                else ""
            ) or str(import_loc_id)

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
                    "2. **Import** Item Reports (primary data), Customer Reports (covers), "
                    "and Timing Reports (meal breakdown)\n"
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
                        "No importable files detected. Make sure you include an "
                        "**Item Report With Customer/Order Details** \u2014 that is the primary data source."
                    )

                # ── Phase 2: Pre-parse to find dates and check overlaps ──
                if importable_count > 0:
                    upload_result = smart_upload.process_smart_upload(
                        files_payload, import_loc_id
                    )

                    overlap_rows: list = []
                    for day in upload_result.days:
                        if day.errors:
                            continue
                        prev_net = database.peek_daily_net_sales(
                            import_loc_id, day.date
                        )
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
                                import_location_settings.get(
                                    "target_monthly_sales", config.MONTHLY_TARGET
                                )
                                if import_location_settings
                                else config.MONTHLY_TARGET
                            )
                            daily_tgt = (
                                import_location_settings.get(
                                    "target_daily_sales", config.DAILY_TARGET
                                )
                                if import_location_settings
                                else config.DAILY_TARGET
                            )
                            sc_setting = (
                                import_location_settings.get("seat_count")
                                if import_location_settings
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
                                    merged, import_loc_id, cr_lookup
                                )
                                merged["target"] = daily_tgt
                                if sc_setting:
                                    merged["seat_count"] = int(sc_setting)
                                merged = parser.calculate_derived_metrics(merged)
                                merged.pop("seat_count", None)
                                y_m = [int(x) for x in day.date.split("-")[:2]]
                                mtd = parser.calculate_mtd_metrics(
                                    import_loc_id,
                                    monthly_tgt,
                                    year=y_m[0],
                                    month=y_m[1],
                                    as_of_date=day.date,
                                )
                                merged.update(mtd)
                                database.save_daily_summary(import_loc_id, merged)

                                fnames = ", ".join(
                                    fr.filename
                                    for fr in upload_result.files
                                    if fr.importable and fr.kind != "customer_report"
                                )
                                if len(fnames) > 180:
                                    fnames = fnames[:177] + "..."
                                database.save_upload_record(
                                    import_loc_id,
                                    day.date,
                                    fnames,
                                    "item_order_details",
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
            if auth.is_admin() and all_locs:
                _sort_del = sorted(all_locs, key=lambda x: x["name"])
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
                        if st.button(
                            "Yes, delete", key="delete_confirm_yes", type="primary"
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
                                st.info(
                                    "No saved row existed for that outlet and date."
                                )
                            st.rerun()
                    with dc2:
                        if st.button("Cancel", key="delete_confirm_no"):
                            st.session_state.pop("_pending_delete", None)
                            st.rerun()
            elif auth.is_admin():
                st.caption("No outlets configured.")
            else:
                st.caption("Contact an admin to remove a mistaken import.")

            # ── Recent uploads ──
            st.markdown("---")
            st.markdown("### Recent Entries")
            history = database.get_upload_history(import_loc_id, 10)
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
                hdf = hdf.rename(
                    columns={k: v for k, v in rename.items() if k in hdf.columns}
                )
                st.dataframe(hdf, use_container_width=True, hide_index=True)
            else:
                st.caption("No imports yet for this outlet.")

        # ============ TAB 2: Daily Report ============
        with tab2:
            st.header("Daily Sales Report")
            st.caption(f"Viewing: **{report_display_name}** — pick a date below.")
            st.divider()

            # Date selector with Prev/Next navigation
            if "report_date" not in st.session_state:
                st.session_state["report_date"] = datetime.now().date()

            nav_col1, nav_col2, nav_col3 = st.columns([1, 3, 1])
            with nav_col1:
                st.write("")
                if st.button("← Prev", key="report_prev_day", use_container_width=True):
                    st.session_state["report_date"] -= timedelta(days=1)
                    st.rerun()
            with nav_col2:
                picked = st.date_input(
                    "Select Date",
                    value=st.session_state["report_date"],
                    key="report_date_picker",
                )
                if picked != st.session_state["report_date"]:
                    st.session_state["report_date"] = picked
                    st.rerun()
            with nav_col3:
                st.write("")
                if st.button("Next →", key="report_next_day", use_container_width=True):
                    st.session_state["report_date"] += timedelta(days=1)
                    st.rerun()

            selected_date = st.session_state["report_date"]
            date_str = selected_date.strftime("%Y-%m-%d")
            outlets_bundle, summary = scope.get_daily_report_bundle(
                report_loc_ids, date_str
            )

            if summary:
                y_m = [int(x) for x in date_str.split("-")[:2]]
                multi_outlet = len(outlets_bundle) > 1

                def _col_head(nm: str, max_len: int = 14) -> str:
                    nm = str(nm).strip()
                    return nm if len(nm) <= max_len else nm[: max_len - 1] + "…"

                with st.container(border=True):
                    if multi_outlet:
                        ncols = len(outlets_bundle) + 1
                        st.caption("Each outlet vs **Combined** (same date).")
                        st.markdown("##### Net sales")
                        cr = st.columns(ncols)
                        for i, (_, oname, s) in enumerate(outlets_bundle):
                            with cr[i]:
                                st.metric(
                                    _col_head(oname),
                                    utils.format_currency(s.get("net_total", 0)),
                                )
                        with cr[-1]:
                            st.metric(
                                "Combined",
                                utils.format_currency(summary.get("net_total", 0)),
                                delta=f"vs {utils.format_currency(summary.get('target', 0))} target",
                            )
                        st.markdown("##### Covers")
                        cr = st.columns(ncols)
                        for i, (_, _on, s) in enumerate(outlets_bundle):
                            with cr[i]:
                                st.metric(
                                    _col_head(_on),
                                    f"{int(s.get('covers') or 0):,}",
                                    delta=f"Turns {float(s.get('turns') or 0):.1f}",
                                )
                        with cr[-1]:
                            lc, dc = (
                                summary.get("lunch_covers"),
                                summary.get("dinner_covers"),
                            )
                            foot = (
                                f"Lunch {lc:,} · Dinner {dc:,}"
                                if lc is not None and dc is not None
                                else None
                            )
                            st.metric(
                                "Combined",
                                f"{int(summary.get('covers') or 0):,}",
                                delta=foot
                                or f"Turns: {float(summary.get('turns') or 0):.1f}",
                            )
                        st.markdown("##### APC")
                        cr = st.columns(ncols)
                        for i, (_, _on, s) in enumerate(outlets_bundle):
                            with cr[i]:
                                st.metric(
                                    _col_head(_on),
                                    utils.format_currency(s.get("apc", 0)),
                                )
                        with cr[-1]:
                            st.metric(
                                "Combined",
                                utils.format_currency(summary.get("apc", 0)),
                                help="Average per cover: net sales ÷ covers.",
                            )
                        st.markdown("##### Target achievement (day)")
                        cr = st.columns(ncols)
                        for i, (_, _on, s) in enumerate(outlets_bundle):
                            p = float(s.get("pct_target") or 0)
                            with cr[i]:
                                st.metric(
                                    _col_head(_on),
                                    f"{p:.1f}%",
                                    delta_color="normal" if p >= 100 else "inverse",
                                )
                        with cr[-1]:
                            pct = float(summary.get("pct_target") or 0)
                            st.metric(
                                "Combined",
                                f"{pct:.1f}%",
                                delta=f"vs {pct:.0f}%",
                                delta_color="normal" if pct >= 100 else "inverse",
                                help="Net sales for the day vs daily sales target.",
                            )
                    else:
                        _, _single_name, s_one = outlets_bundle[0]
                        _oc = int(s_one.get("order_count") or 0)
                        _aov = (
                            float(s_one.get("net_total") or 0) / _oc if _oc > 0 else 0.0
                        )
                        col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
                        with col_kpi1:
                            st.metric(
                                "Net Sales",
                                utils.format_currency(s_one.get("net_total", 0)),
                                delta=f"vs {utils.format_currency(s_one.get('target', 0))} target",
                            )
                        with col_kpi2:
                            lc = s_one.get("lunch_covers")
                            dc = s_one.get("dinner_covers")
                            foot = (
                                f"Lunch {lc:,} · Dinner {dc:,}"
                                if lc is not None and dc is not None
                                else None
                            )
                            st.metric(
                                "Covers",
                                f"{int(s_one.get('covers') or 0):,}",
                                delta=foot
                                or f"Turns: {float(s_one.get('turns') or 0):.1f}",
                            )
                        with col_kpi3:
                            st.metric(
                                "APC",
                                utils.format_currency(s_one.get("apc", 0)),
                                help="Average per cover: net sales ÷ covers.",
                            )
                        with col_kpi4:
                            st.metric(
                                "Orders / AOV",
                                f"{_oc:,}",
                                delta=utils.format_currency(_aov) + " avg"
                                if _oc > 0
                                else None,
                                help="Unique orders (invoices) and Average Order Value.",
                            )
                        with col_kpi5:
                            pct = float(s_one.get("pct_target") or 0)
                            st.metric(
                                "Target Achievement",
                                f"{pct:.1f}%",
                                delta_color="normal" if pct >= 100 else "inverse",
                                help="Net sales for the day vs daily sales target.",
                            )

                st.markdown("---")

                col_det1, col_det2 = st.columns(2)

                _pay_fields = [
                    ("Gross Total", "gross_total"),
                    ("Net Total", "net_total"),
                    ("Cash", "cash_sales"),
                    ("GPay", "gpay_sales"),
                    ("Zomato", "zomato_sales"),
                    ("Card", "card_sales"),
                    ("Other", "other_sales"),
                    ("Discount", "discount"),
                    ("Complimentary", "complimentary"),
                    ("Service Charge", "service_charge"),
                    ("CGST", "cgst"),
                    ("SGST", "sgst"),
                ]

                with col_det1:
                    st.markdown("### 💰 Sales & Tax Breakdown")
                    if multi_outlet:
                        sd = {
                            "Line item": [x[0] for x in _pay_fields],
                        }
                        for _, oname, s in outlets_bundle:
                            sd[_col_head(oname, 12)] = [
                                utils.format_currency(float(s.get(f) or 0))
                                for _l, f in _pay_fields
                            ]
                        sd["Combined"] = [
                            utils.format_currency(float(summary.get(f) or 0))
                            for _l, f in _pay_fields
                        ]
                        sales_df = pd.DataFrame(sd)
                        st.dataframe(
                            sales_df,
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        _, _sn, s_one = outlets_bundle[0]
                        sales_data = {
                            "Line item": [x[0] for x in _pay_fields],
                            "Amount (₹)": [
                                utils.format_currency(float(s_one.get(f) or 0))
                                for _l, f in _pay_fields
                            ],
                        }
                        sales_df = pd.DataFrame(sales_data)
                        st.dataframe(
                            sales_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Line item": st.column_config.TextColumn("Line item"),
                                "Amount (₹)": st.column_config.TextColumn("Amount (₹)"),
                            },
                        )

                with col_det2:
                    st.markdown("### 📊 MTD Summary")
                    _mtd_rows = [
                        ("Net Sales", "mtd_net_sales", "cur"),
                        ("Total Covers", "mtd_total_covers", "int"),
                        ("Avg Daily", "mtd_avg_daily", "cur"),
                        ("Target", "mtd_target", "cur"),
                        ("Achievement", "mtd_pct_target", "pct"),
                    ]
                    if multi_outlet:
                        md = {"Metric": [x[0] for x in _mtd_rows]}
                        for _, oname, s in outlets_bundle:
                            col_vals = []
                            for _lab, key, kind in _mtd_rows:
                                v = s.get(key, 0)
                                if kind == "int":
                                    col_vals.append(f"{int(v or 0):,}")
                                elif kind == "pct":
                                    col_vals.append(f"{float(v or 0):.1f}%")
                                else:
                                    col_vals.append(
                                        utils.format_currency(float(v or 0))
                                    )
                            md[_col_head(oname, 12)] = col_vals
                        md["Combined"] = []
                        for _lab, key, kind in _mtd_rows:
                            v = summary.get(key, 0)
                            if kind == "int":
                                md["Combined"].append(f"{int(v or 0):,}")
                            elif kind == "pct":
                                md["Combined"].append(f"{float(v or 0):.1f}%")
                            else:
                                md["Combined"].append(
                                    utils.format_currency(float(v or 0))
                                )
                        st.dataframe(
                            pd.DataFrame(md),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        _, _sn, s_one = outlets_bundle[0]
                        mtd_data = {
                            "Metric": [x[0] for x in _mtd_rows],
                            "Value": [],
                        }
                        for _lab, key, kind in _mtd_rows:
                            v = s_one.get(key, 0)
                            if kind == "int":
                                mtd_data["Value"].append(f"{int(v or 0):,}")
                            elif kind == "pct":
                                mtd_data["Value"].append(f"{float(v or 0):.1f}%")
                            else:
                                mtd_data["Value"].append(
                                    utils.format_currency(float(v or 0))
                                )
                        st.dataframe(
                            pd.DataFrame(mtd_data),
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Metric": st.column_config.TextColumn("Metric"),
                                "Value": st.column_config.TextColumn("Value"),
                            },
                        )

                st.markdown("---")

                # Sheet-style report + clipboard (matches Google Sheet EOD layout)
                st.markdown("### 📱 WhatsApp / sheet-style report")
                per_outlet_sheet = (
                    [(n, d) for _i, n, d in outlets_bundle] if multi_outlet else None
                )

                y_m = [int(x) for x in date_str.split("-")[:2]]
                if len(report_loc_ids) > 1:
                    mtd_cat = database.get_category_mtd_totals_multi(
                        report_loc_ids, y_m[0], y_m[1]
                    )
                    mtd_svc = database.get_service_mtd_totals_multi(
                        report_loc_ids, y_m[0], y_m[1]
                    )
                    foot_rows = scope.merge_month_footfall_rows(
                        report_loc_ids, y_m[0], y_m[1]
                    )
                else:
                    mtd_cat = database.get_category_mtd_totals(
                        report_loc_ids[0], y_m[0], y_m[1]
                    )
                    mtd_svc = database.get_service_mtd_totals(
                        report_loc_ids[0], y_m[0], y_m[1]
                    )
                    foot_rows = database.get_summaries_for_month(
                        report_loc_ids[0], y_m[0], y_m[1]
                    )

                img_buffer = reports.generate_sheet_style_report_image(
                    summary,
                    report_display_name,
                    mtd_category=mtd_cat,
                    mtd_service=mtd_svc,
                    month_footfall_rows=foot_rows,
                    per_outlet_summaries=per_outlet_sheet,
                )
                png_bytes = img_buffer.getvalue()
                section_bufs = reports.generate_sheet_style_report_sections(
                    summary,
                    report_display_name,
                    mtd_category=mtd_cat,
                    mtd_service=mtd_svc,
                    month_footfall_rows=foot_rows,
                    per_outlet_summaries=per_outlet_sheet,
                )
                whatsapp_text = reports.generate_whatsapp_text(
                    summary,
                    report_display_name,
                    per_outlet=per_outlet_sheet,
                )

                st.image(BytesIO(png_bytes), use_container_width=True)
                if multi_outlet:
                    st.caption(
                        "Lower sections of the image (category, service, footfall) use **combined** "
                        "MTD for all outlets in scope."
                    )

                st.caption(
                    "**Next step:** Use **Copy report image** and paste into WhatsApp, "
                    "or **Download PNG**. **Copy report text** for a plain-text version."
                )

                if len(report_loc_ids) > 1:
                    with st.expander("Per-outlet reports (same date)", expanded=False):
                        for lid in report_loc_ids:
                            sub = database.get_daily_summary(lid, date_str)
                            if not sub:
                                st.caption(f"Location id {lid}: no data for this date")
                                continue
                            loc_st = database.get_location_settings(lid)
                            sub_name = loc_st["name"] if loc_st else str(lid)
                            m_tgt = (
                                float(loc_st["target_monthly_sales"])
                                if loc_st
                                else config.MONTHLY_TARGET
                            )
                            sub = scope.enrich_summary_for_display(
                                sub, [lid], m_tgt, date_str
                            )
                            sm_cat = database.get_category_mtd_totals(
                                lid, y_m[0], y_m[1]
                            )
                            sm_svc = database.get_service_mtd_totals(
                                lid, y_m[0], y_m[1]
                            )
                            sm_foot = database.get_summaries_for_month(
                                lid, y_m[0], y_m[1]
                            )
                            buf = reports.generate_sheet_style_report_image(
                                sub,
                                sub_name,
                                mtd_category=sm_cat,
                                mtd_service=sm_svc,
                                month_footfall_rows=sm_foot,
                            )
                            st.caption(sub_name)
                            st.image(BytesIO(buf.getvalue()), use_container_width=True)

                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    clipboard_ui.render_copy_image_button(
                        png_bytes,
                        "Copy report image",
                        f"clip_img_{date_str}",
                    )
                with b2:
                    clipboard_ui.render_copy_text_button(
                        whatsapp_text,
                        "Copy report text",
                        f"clip_txt_{date_str}",
                        primary=False,
                    )
                with b3:
                    st.download_button(
                        "Download PNG",
                        png_bytes,
                        file_name=f"boteco_sheet_{date_str}.png",
                        mime="image/png",
                        key=f"dl_png_{date_str}",
                        type="secondary",
                    )
                with b4:
                    st.download_button(
                        "Download text",
                        whatsapp_text,
                        file_name=f"boteco_report_{date_str}.txt",
                        mime="text/plain",
                        key=f"dl_txt_{date_str}",
                        type="secondary",
                    )

                with st.expander("Individual PNG sections", expanded=False):
                    st.markdown("#### Individual sections")
                    _sec_meta = [
                        ("sales_summary", "Sales summary"),
                        ("category", "Category sales"),
                        ("service", "Service sales"),
                        ("footfall", "Footfall (month)"),
                    ]
                    zip_buf = BytesIO()
                    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for key, title in _sec_meta:
                            b = section_bufs[key].getvalue()
                            zf.writestr(
                                f"boteco_{key}_{date_str}.png",
                                b,
                            )
                    zip_buf.seek(0)
                    st.download_button(
                        "Download all sections (ZIP)",
                        zip_buf.getvalue(),
                        file_name=f"boteco_sections_{date_str}.zip",
                        mime="application/zip",
                        key=f"dl_zip_sections_{date_str}",
                        type="secondary",
                    )

                    r1c1, r1c2 = st.columns(2)
                    r2c1, r2c2 = st.columns(2)
                    _cells = [r1c1, r1c2, r2c1, r2c2]
                    for idx, (key, title) in enumerate(_sec_meta):
                        sec_bytes = section_bufs[key].getvalue()
                        with _cells[idx]:
                            st.caption(title)
                            st.image(BytesIO(sec_bytes), use_container_width=True)
                            cb1, cb2 = st.columns(2)
                            with cb1:
                                clipboard_ui.render_copy_image_button(
                                    sec_bytes,
                                    "Copy",
                                    f"clip_sec_{key}_{date_str}",
                                    height=44,
                                    primary=False,
                                )
                            with cb2:
                                st.download_button(
                                    "PNG",
                                    sec_bytes,
                                    file_name=f"boteco_{key}_{date_str}.png",
                                    mime="image/png",
                                    key=f"dl_sec_{key}_{date_str}",
                                    type="secondary",
                                )

                with st.expander("Plain text preview"):
                    st.text_area(
                        "Report text",
                        whatsapp_text,
                        height=280,
                        key=f"whatsapp_text_{date_str}",
                    )
            else:
                st.info(
                    f"No saved data for **{selected_date.strftime('%d %b %Y')}**. "
                    "Go to the **Upload** tab and import POS files for that date."
                )

        # ============ TAB 3: Analytics ============
        with tab3:
            st.header("Sales Analytics")
            st.caption(
                f"Viewing: **{report_display_name}** — trends for the period below."
            )
            st.divider()

            # ── Period selector ──────────────────────────────────────────
            col_per1, col_per2 = st.columns([2, 3])
            with col_per1:
                analysis_period = st.selectbox(
                    "Time Period",
                    [
                        "This Week",
                        "Last Week",
                        "Last 7 Days",
                        "This Month",
                        "Last Month",
                        "Last 30 Days",
                        "Custom",
                    ],
                    key="analysis_period",
                )

            if analysis_period == "Custom":
                with col_per2:
                    c1, c2 = st.columns(2)
                    with c1:
                        custom_start = st.date_input(
                            "From",
                            datetime.now().date() - timedelta(days=29),
                            key="analytics_custom_start",
                        )
                    with c2:
                        custom_end = st.date_input(
                            "To",
                            datetime.now().date(),
                            key="analytics_custom_end",
                        )
                start_date, end_date = custom_start, custom_end
                prior_start, prior_end = None, None
            else:
                period_key = analysis_period.lower().replace(" ", "_")
                start_date, end_date = utils.get_date_range(period_key)

                # Determine comparison period for period-over-period deltas
                _prior_map = {
                    "this_week": "last_week",
                    "this_month": "last_month",
                }
                _days_span = (end_date - start_date).days + 1
                if period_key in _prior_map:
                    prior_start, prior_end = utils.get_date_range(
                        _prior_map[period_key]
                    )
                elif period_key in ("last_7_days", "last_30_days"):
                    prior_end = start_date - timedelta(days=1)
                    prior_start = prior_end - timedelta(days=_days_span - 1)
                else:
                    prior_start, prior_end = None, None

                with col_per2:
                    st.write(
                        f"**From:** {start_date.strftime('%d %b')} "
                        f"to {end_date.strftime('%d %b %Y')}"
                    )

            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            raw_summaries = database.get_summaries_for_date_range_multi(
                report_loc_ids,
                start_str,
                end_str,
            )
            summaries = scope.merge_summaries_by_date(raw_summaries)
            multi_analytics = len(report_loc_ids) > 1
            df_raw = pd.DataFrame(raw_summaries) if raw_summaries else pd.DataFrame()
            if multi_analytics and not df_raw.empty:
                loc_names = {loc["id"]: str(loc["name"]) for loc in all_locs}
                df_raw = df_raw.copy()
                df_raw["Outlet"] = df_raw["location_id"].map(
                    lambda x: loc_names.get(x, str(x))
                )

            if summaries:
                df = pd.DataFrame(summaries)

                # ── Period-over-period comparison data ───────────────────
                prior_summaries = []
                if prior_start and prior_end:
                    prior_summaries = database.get_summaries_for_date_range_multi(
                        report_loc_ids,
                        prior_start.strftime("%Y-%m-%d"),
                        prior_end.strftime("%Y-%m-%d"),
                    )
                prior_df = (
                    pd.DataFrame(prior_summaries) if prior_summaries else pd.DataFrame()
                )

                total_sales = float(df["net_total"].sum())
                avg_daily = float(df["net_total"].mean())
                total_covers = int(df["covers"].sum())
                days_with_data = int(len(df[df["net_total"] > 0]))

                prior_total = (
                    float(prior_df["net_total"].sum()) if not prior_df.empty else None
                )
                prior_covers = (
                    int(prior_df["covers"].sum()) if not prior_df.empty else None
                )
                prior_avg = (
                    float(prior_df["net_total"].mean()) if not prior_df.empty else None
                )

                # ── Period Summary KPIs ──────────────────────────────────
                st.markdown("### Period Summary")
                with st.container(border=True):
                    # How many columns: 4 base + 1 projection when "This Month"
                    show_projection = analysis_period == "This Month"
                    _ncols = 5 if show_projection else 4
                    kpi_cols = st.columns(_ncols)

                    def _delta_str(current, prior):
                        if prior is None or prior == 0:
                            return None
                        g = utils.calculate_growth(current, prior)
                        sign = "+" if g["change"] >= 0 else ""
                        return f"{sign}{utils.format_currency(g['change'])} ({sign}{g['percentage']:.1f}%)"

                    with kpi_cols[0]:
                        st.metric(
                            "Total Sales",
                            utils.format_currency(total_sales),
                            delta=_delta_str(total_sales, prior_total),
                        )
                    with kpi_cols[1]:
                        cov_delta = None
                        if prior_covers is not None and prior_covers > 0:
                            g = utils.calculate_growth(total_covers, prior_covers)
                            sign = "+" if g["change"] >= 0 else ""
                            cov_delta = f"{sign}{int(g['change']):,} ({sign}{g['percentage']:.1f}%)"
                        st.metric(
                            "Total Covers",
                            f"{total_covers:,}",
                            delta=cov_delta,
                        )
                    with kpi_cols[2]:
                        st.metric(
                            "Avg Daily Sales",
                            utils.format_currency(avg_daily),
                            delta=_delta_str(avg_daily, prior_avg),
                        )
                    with kpi_cols[3]:
                        st.metric("Days with Data", days_with_data)

                    if show_projection:
                        days_in_mo = utils.get_days_in_month(
                            start_date.year, start_date.month
                        )
                        projected = utils.calculate_projected_sales(
                            total_sales, days_with_data, days_in_mo
                        )
                        with kpi_cols[4]:
                            st.metric(
                                "Projected Month-End",
                                utils.format_currency(projected),
                                help="Based on current run rate extrapolated to end of month.",
                            )

                st.markdown("---")

                # ── Sales & Covers charts ────────────────────────────────
                col_chart1, col_chart2 = st.columns(2)

                with col_chart1:
                    st.markdown("### Daily Sales Trend")
                    if multi_analytics and not df_raw.empty:
                        fig_line = px.line(
                            df_raw,
                            x="date",
                            y="net_total",
                            color="Outlet",
                            markers=True,
                            title="Net sales by outlet",
                        )
                    else:
                        fig_line = px.line(
                            df,
                            x="date",
                            y="net_total",
                            markers=True,
                            title="Net Sales Over Time",
                        )
                        fig_line.update_traces(line_color=ui_theme.BRAND_PRIMARY)
                    fig_line.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Net Sales (₹)",
                        hovermode="x unified",
                        height=ui_theme.CHART_HEIGHT,
                    )
                    st.plotly_chart(fig_line, use_container_width=True)

                with col_chart2:
                    st.markdown("### Covers Trend")
                    if multi_analytics and not df_raw.empty:
                        fig_bar = px.bar(
                            df_raw,
                            x="date",
                            y="covers",
                            color="Outlet",
                            barmode="group",
                            title="Daily covers by outlet",
                        )
                    else:
                        fig_bar = px.bar(df, x="date", y="covers", title="Daily Covers")
                        fig_bar.update_traces(marker_color=ui_theme.BRAND_SUCCESS)
                    fig_bar.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Covers",
                        height=ui_theme.CHART_HEIGHT,
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                # ── APC Trend ────────────────────────────────────────────
                st.markdown("### Average Per Cover (APC) Trend")
                apc_df = (
                    df[df["apc"] > 0].copy() if "apc" in df.columns else pd.DataFrame()
                )
                if not apc_df.empty:
                    fig_apc = px.line(
                        apc_df,
                        x="date",
                        y="apc",
                        markers=True,
                        title="APC over time",
                    )
                    fig_apc.update_traces(line_color=ui_theme.BRAND_PRIMARY)
                    avg_apc = float(apc_df["apc"].mean())
                    fig_apc.add_hline(
                        y=avg_apc,
                        line_dash="dash",
                        line_color="gray",
                        annotation_text=f"Avg {utils.format_currency(avg_apc)}",
                        annotation_position="top right",
                    )
                    fig_apc.update_layout(
                        xaxis_title="Date",
                        yaxis_title="APC (₹)",
                        hovermode="x unified",
                        height=ui_theme.CHART_HEIGHT,
                    )
                    st.plotly_chart(fig_apc, use_container_width=True)
                else:
                    st.caption("No APC data for this period.")

                st.markdown("---")

                # ── Payment Mode Distribution ────────────────────────────
                st.markdown("### Payment Mode Distribution")
                payment_totals = {
                    "Cash": float(df["cash_sales"].sum()),
                    "GPay": float(df["gpay_sales"].sum()),
                    "Zomato": float(df["zomato_sales"].sum()),
                    "Card": float(df["card_sales"].sum()),
                    "Other": float(df["other_sales"].sum()),
                }
                pay_df = pd.DataFrame(
                    {
                        "Mode": list(payment_totals.keys()),
                        "Amount": list(payment_totals.values()),
                    }
                ).sort_values("Amount", ascending=True)
                fig_pay = px.bar(
                    pay_df,
                    x="Amount",
                    y="Mode",
                    orientation="h",
                    title="Payment mode split (₹)",
                )
                fig_pay.update_layout(
                    xaxis_title="Amount (₹)",
                    yaxis_title="",
                    height=ui_theme.CHART_HEIGHT,
                    showlegend=False,
                )
                st.plotly_chart(fig_pay, use_container_width=True)

                st.markdown("---")

                # ── Category Sales ───────────────────────────────────────
                st.markdown("### Category Mix")
                cat_data = database.get_category_sales_for_date_range(
                    report_loc_ids, start_str, end_str
                )
                if cat_data:
                    cat_df = pd.DataFrame(cat_data)
                    col_cat1, col_cat2 = st.columns(2)
                    with col_cat1:
                        fig_cat_bar = px.bar(
                            cat_df,
                            x="amount",
                            y="category",
                            orientation="h",
                            title="Revenue by category (₹)",
                            color="amount",
                            color_continuous_scale=[
                                ui_theme.BRAND_SUCCESS,
                                ui_theme.BRAND_PRIMARY,
                            ],
                        )
                        fig_cat_bar.update_layout(
                            xaxis_title="Amount (₹)",
                            yaxis_title="",
                            height=ui_theme.CHART_HEIGHT,
                            coloraxis_showscale=False,
                        )
                        st.plotly_chart(fig_cat_bar, use_container_width=True)
                    with col_cat2:
                        fig_cat_pie = px.pie(
                            cat_df,
                            names="category",
                            values="amount",
                            title="Category revenue mix",
                            hole=0.4,
                        )
                        fig_cat_pie.update_layout(height=ui_theme.CHART_HEIGHT)
                        st.plotly_chart(fig_cat_pie, use_container_width=True)
                else:
                    st.caption("No category data for this period.")

                st.markdown("---")

                # ── Top Selling Items ────────────────────────────────────
                st.markdown("### Top Selling Items")
                top_items_data = database.get_top_items_for_date_range(
                    report_loc_ids, start_str, end_str, limit=15
                )
                if top_items_data:
                    items_df = pd.DataFrame(top_items_data)
                    col_items1, col_items2 = st.columns([3, 2])
                    with col_items1:
                        fig_items = px.bar(
                            items_df,
                            x="amount",
                            y="item_name",
                            orientation="h",
                            title="Top 15 items by revenue (₹)",
                            color="amount",
                            color_continuous_scale=[
                                ui_theme.BRAND_SUCCESS,
                                ui_theme.BRAND_PRIMARY,
                            ],
                        )
                        fig_items.update_layout(
                            xaxis_title="Revenue (₹)",
                            yaxis_title="",
                            height=420,
                            coloraxis_showscale=False,
                            yaxis={"categoryorder": "total ascending"},
                        )
                        st.plotly_chart(fig_items, use_container_width=True)
                    with col_items2:
                        items_tbl = items_df.copy()
                        items_tbl["amount"] = [
                            utils.format_currency(float(x or 0))
                            for x in items_tbl["amount"]
                        ]
                        items_tbl["qty"] = [
                            f"{int(x or 0):,}" for x in items_tbl["qty"]
                        ]
                        items_tbl = items_tbl.rename(
                            columns={
                                "item_name": "Item",
                                "amount": "Revenue",
                                "qty": "Qty",
                            }
                        )
                        st.dataframe(
                            items_tbl,
                            use_container_width=True,
                            hide_index=True,
                        )
                else:
                    st.caption(
                        "No item-level data for this period. "
                        "Re-import your Item Reports to populate top sellers."
                    )

                st.markdown("---")

                # ── Meal Period (Service) Charts ─────────────────────────
                st.markdown("### Meal Period Breakdown")
                daily_svc = database.get_daily_service_sales_for_date_range(
                    report_loc_ids, start_str, end_str
                )
                period_svc = database.get_service_sales_for_date_range(
                    report_loc_ids, start_str, end_str
                )
                if daily_svc and period_svc:
                    svc_daily_df = pd.DataFrame(daily_svc)
                    svc_period_df = pd.DataFrame(period_svc)
                    col_svc1, col_svc2 = st.columns(2)
                    with col_svc1:
                        fig_svc_stack = px.bar(
                            svc_daily_df,
                            x="date",
                            y="amount",
                            color="service_type",
                            barmode="stack",
                            title="Lunch vs Dinner revenue per day",
                            color_discrete_map={
                                "Lunch": ui_theme.BRAND_SUCCESS,
                                "Dinner": ui_theme.BRAND_PRIMARY,
                                "Breakfast": "#ffd93d",
                            },
                        )
                        fig_svc_stack.update_layout(
                            xaxis_title="Date",
                            yaxis_title="Amount (₹)",
                            height=ui_theme.CHART_HEIGHT,
                            legend_title="Service",
                        )
                        st.plotly_chart(fig_svc_stack, use_container_width=True)
                    with col_svc2:
                        fig_svc_tot = px.bar(
                            svc_period_df,
                            x="service_type",
                            y="amount",
                            title="Total revenue by meal period",
                            color="service_type",
                            color_discrete_map={
                                "Lunch": ui_theme.BRAND_SUCCESS,
                                "Dinner": ui_theme.BRAND_PRIMARY,
                                "Breakfast": "#ffd93d",
                            },
                        )
                        fig_svc_tot.update_layout(
                            xaxis_title="",
                            yaxis_title="Amount (₹)",
                            height=ui_theme.CHART_HEIGHT,
                            showlegend=False,
                        )
                        st.plotly_chart(fig_svc_tot, use_container_width=True)
                else:
                    st.caption("No meal-period data for this period.")

                st.markdown("---")

                # ── Weekday Analysis ─────────────────────────────────────
                st.markdown("### Weekday Analysis")
                if len(df) >= 3:
                    wd_df = df[df["net_total"] > 0].copy()
                    wd_df["weekday"] = wd_df["date"].apply(utils.get_weekday_name)
                    wd_agg = (
                        wd_df.groupby("weekday")["net_total"]
                        .mean()
                        .reset_index()
                        .rename(columns={"net_total": "avg_sales"})
                    )
                    day_order = [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ]
                    wd_agg["weekday"] = pd.Categorical(
                        wd_agg["weekday"], categories=day_order, ordered=True
                    )
                    wd_agg = wd_agg.sort_values("weekday")
                    _monthly_tgt = scope.sum_location_monthly_targets(report_loc_ids)
                    _daily_tgt = (
                        _monthly_tgt
                        / utils.get_days_in_month(start_date.year, start_date.month)
                        if _monthly_tgt > 0
                        else 0
                    )
                    wd_colors = [
                        "#4ecca3"
                        if v >= _daily_tgt
                        else "#ffd93d"
                        if v >= _daily_tgt * 0.8
                        else "#e94560"
                        for v in wd_agg["avg_sales"]
                    ]
                    fig_wd = px.bar(
                        wd_agg,
                        x="weekday",
                        y="avg_sales",
                        title="Average net sales by day of week",
                    )
                    fig_wd.update_traces(marker_color=wd_colors)
                    if _daily_tgt > 0:
                        fig_wd.add_hline(
                            y=_daily_tgt,
                            line_dash="dash",
                            line_color="gray",
                            annotation_text=f"Daily target {utils.format_currency(_daily_tgt)}",
                            annotation_position="top right",
                        )
                    fig_wd.update_layout(
                        xaxis_title="",
                        yaxis_title="Avg Net Sales (₹)",
                        height=ui_theme.CHART_HEIGHT,
                    )
                    st.plotly_chart(fig_wd, use_container_width=True)
                else:
                    st.caption("Need at least 3 days of data for weekday analysis.")

                st.markdown("---")

                # ── Target Achievement ───────────────────────────────────
                st.markdown("### Target Achievement")
                monthly_target = scope.sum_location_monthly_targets(report_loc_ids)
                if monthly_target > 0:
                    days_in_month = utils.get_days_in_month(
                        start_date.year, start_date.month
                    )
                    daily_target = monthly_target / days_in_month

                    fig_target = make_subplots(
                        rows=1,
                        cols=2,
                        subplot_titles=["Daily Achievement %", "Cumulative vs Target"],
                        specs=[[{"type": "bar"}, {"type": "scatter"}]],
                    )

                    df["achievement"] = (
                        df["net_total"] / daily_target * 100 if daily_target > 0 else 0
                    )
                    colors = [
                        "#4ecca3" if x >= 100 else "#ffd93d" if x >= 80 else "#e94560"
                        for x in df["achievement"]
                    ]
                    fig_target.add_trace(
                        go.Bar(
                            x=df["date"],
                            y=df["achievement"],
                            marker_color=colors,
                            name="Achievement %",
                        ),
                        row=1,
                        col=1,
                    )

                    df_sorted = df.sort_values("date")
                    df_sorted["cumulative"] = df_sorted["net_total"].cumsum()
                    target_line = [
                        monthly_target * (i / len(df_sorted))
                        for i in range(1, len(df_sorted) + 1)
                    ]
                    fig_target.add_trace(
                        go.Scatter(
                            x=df_sorted["date"],
                            y=df_sorted["cumulative"],
                            mode="lines+markers",
                            name="Actual",
                        ),
                        row=1,
                        col=2,
                    )
                    fig_target.add_trace(
                        go.Scatter(
                            x=df_sorted["date"],
                            y=target_line,
                            mode="lines",
                            name="Target",
                            line=dict(dash="dash"),
                        ),
                        row=1,
                        col=2,
                    )
                    fig_target.update_layout(
                        height=ui_theme.CHART_HEIGHT, showlegend=True
                    )
                    st.plotly_chart(fig_target, use_container_width=True)

                # ── Daily Data Table ─────────────────────────────────────
                st.markdown("### Daily Data")
                if multi_analytics and not df_raw.empty:
                    dv = (
                        df_raw[
                            [
                                "date",
                                "Outlet",
                                "covers",
                                "net_total",
                                "target",
                                "pct_target",
                            ]
                        ]
                        .sort_values(["date", "Outlet"])
                        .copy()
                    )
                    dv["covers"] = [f"{int(x or 0):,}" for x in dv["covers"]]
                    dv["net_total"] = [
                        utils.format_currency(float(x or 0)) for x in dv["net_total"]
                    ]
                    dv["target"] = [
                        utils.format_currency(float(x or 0)) for x in dv["target"]
                    ]
                    dv["pct_target"] = [
                        f"{float(x or 0):.1f}%" for x in dv["pct_target"]
                    ]
                    st.dataframe(
                        dv,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "date": st.column_config.TextColumn("Date"),
                            "Outlet": st.column_config.TextColumn("Outlet"),
                            "covers": st.column_config.TextColumn("Covers"),
                            "net_total": st.column_config.TextColumn("Net Sales (₹)"),
                            "target": st.column_config.TextColumn("Target (₹)"),
                            "pct_target": st.column_config.TextColumn("Achievement"),
                        },
                    )
                else:
                    daily_view = df[
                        ["date", "covers", "net_total", "target", "pct_target"]
                    ].copy()
                    daily_view["covers"] = [
                        f"{int(x or 0):,}" for x in daily_view["covers"]
                    ]
                    daily_view["net_total"] = [
                        utils.format_currency(float(x or 0))
                        for x in daily_view["net_total"]
                    ]
                    daily_view["target"] = [
                        utils.format_currency(float(x or 0))
                        for x in daily_view["target"]
                    ]
                    daily_view["pct_target"] = [
                        f"{float(x or 0):.1f}%" for x in daily_view["pct_target"]
                    ]
                    st.dataframe(
                        daily_view,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "date": st.column_config.TextColumn("Date"),
                            "covers": st.column_config.TextColumn("Covers"),
                            "net_total": st.column_config.TextColumn("Net Sales (₹)"),
                            "target": st.column_config.TextColumn("Target (₹)"),
                            "pct_target": st.column_config.TextColumn("Achievement"),
                        },
                    )

            else:
                st.info(
                    "No data in this period. Upload POS files from the **Upload** tab "
                    "or choose a different time range."
                )

        # ============ TAB 4: Settings ============
        with tab4:
            st.header("Settings")
            st.caption("Outlets, users, targets, and data export.")
            st.divider()

            # ── Account info (all users) ──────────────────────────────────
            with st.container(border=True):
                st.markdown("### Your Account")
                ac1, ac2, ac3 = st.columns(3)
                with ac1:
                    st.metric("Username", st.session_state.username)
                with ac2:
                    st.metric("Role", st.session_state.user_role.title())
                with ac3:
                    st.metric("Home location", st.session_state.location_name)

            if not auth.is_admin():
                st.info(
                    "Contact an admin to change your password, role, or location assignment."
                )
                st.stop()

            # ─────────────────────────────────────────────────────────────
            # ADMIN-ONLY SECTIONS BELOW
            # ─────────────────────────────────────────────────────────────

            st.markdown("---")

            # ── Location settings ─────────────────────────────────────────
            st.markdown("### Outlet Settings")
            sort_locs = sorted(all_locs, key=lambda x: x["name"]) if all_locs else []
            if sort_locs:
                name_by_id = {loc["id"]: loc["name"] for loc in sort_locs}
                settings_location_id = st.selectbox(
                    "Edit settings for outlet",
                    options=[loc["id"] for loc in sort_locs],
                    format_func=lambda i: name_by_id[i],
                    key="settings_which_location",
                )
                location_settings = database.get_location_settings(
                    int(settings_location_id)
                )
                location_settings = database.get_location_settings(settings_location_id)

                with st.form("location_settings_form"):
                    lf1, lf2, lf3 = st.columns(3)
                    with lf1:
                        new_name = st.text_input(
                            "Location Name",
                            value=(
                                location_settings.get("name", "")
                                if location_settings
                                else ""
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
                if all_locs:
                    del_loc_opts = {loc["id"]: loc["name"] for loc in sort_locs}
                    del_loc_id = st.selectbox(
                        "Select outlet to delete",
                        options=list(del_loc_opts.keys()),
                        format_func=lambda i: del_loc_opts[i],
                        key="del_loc_select",
                    )
                    if st.button("Delete outlet", key="del_loc_btn", type="primary"):
                        st.session_state["_pending_loc_delete"] = del_loc_id
                    pld = st.session_state.get("_pending_loc_delete")
                    if pld:
                        st.error(
                            f"**Confirm:** permanently delete outlet "
                            f"**{del_loc_opts.get(pld, pld)}**?"
                        )
                        dlc1, dlc2 = st.columns(2)
                        with dlc1:
                            if st.button(
                                "Yes, delete outlet", key="del_loc_yes", type="primary"
                            ):
                                ok, msg = database.delete_location(pld)
                                st.session_state.pop("_pending_loc_delete", None)
                                if ok:
                                    st.success(msg)
                                else:
                                    st.error(msg)
                                st.rerun()
                        with dlc2:
                            if st.button("Cancel", key="del_loc_no"):
                                st.session_state.pop("_pending_loc_delete", None)
                                st.rerun()

            st.markdown("---")

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
                    use_container_width=True,
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
                        cu_loc_opts = {
                            loc["id"]: loc["name"] for loc in (all_locs or [])
                        }
                        cu_loc_opts[0] = "— none —"
                        cu_loc = st.selectbox(
                            "Home location",
                            options=[0] + [loc["id"] for loc in (all_locs or [])],
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
                                    loc["id"]: loc["name"] for loc in (all_locs or [])
                                }
                                eu_loc_opts[0] = "— none —"
                                cur_loc = eu.get("location_id") or 0
                                eu_loc = st.selectbox(
                                    "Home location",
                                    options=[0]
                                    + [loc["id"] for loc in (all_locs or [])],
                                    index=(
                                        [0] + [loc["id"] for loc in (all_locs or [])]
                                    ).index(cur_loc)
                                    if cur_loc
                                    in ([0] + [loc["id"] for loc in (all_locs or [])])
                                    else 0,
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
                    if st.button("Delete user", key="del_user_btn", type="primary"):
                        st.session_state["_pending_user_delete"] = du_id
                    pud = st.session_state.get("_pending_user_delete")
                    if pud:
                        st.error(
                            f"**Confirm:** permanently delete user "
                            f"**{du_opts.get(pud, pud)}**?"
                        )
                        duc1, duc2 = st.columns(2)
                        with duc1:
                            if st.button(
                                "Yes, delete user", key="del_user_yes", type="primary"
                            ):
                                ok, msg = database.delete_user(
                                    pud, st.session_state.username
                                )
                                st.session_state.pop("_pending_user_delete", None)
                                if ok:
                                    st.success(msg)
                                else:
                                    st.error(msg)
                                st.rerun()
                        with duc2:
                            if st.button("Cancel##user", key="del_user_no"):
                                st.session_state.pop("_pending_user_delete", None)
                                st.rerun()

            st.markdown("---")

            # ── Data export ───────────────────────────────────────────────
            st.markdown("### Data Export")
            st.caption(
                "Download all saved daily summaries as CSV or Excel. "
                "Use the filters to narrow the export."
            )

            exp_c1, exp_c2, exp_c3 = st.columns(3)
            with exp_c1:
                exp_loc_opts = {"all": "All outlets"}
                exp_loc_opts.update(
                    {str(loc["id"]): loc["name"] for loc in (all_locs or [])}
                )
                exp_loc = st.selectbox(
                    "Outlet",
                    options=list(exp_loc_opts.keys()),
                    format_func=lambda k: exp_loc_opts[k],
                    key="export_outlet",
                )
            with exp_c2:
                exp_start = st.date_input(
                    "From date",
                    value=datetime.now().date().replace(day=1),
                    key="export_start",
                )
            with exp_c3:
                exp_end = st.date_input(
                    "To date",
                    value=datetime.now().date(),
                    key="export_end",
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
                    st.dataframe(
                        exp_df.head(10), use_container_width=True, hide_index=True
                    )
            else:
                st.caption("No data found for the selected filters.")

            st.markdown("---")

            # ── Quick outlet stats ────────────────────────────────────────
            with st.expander("Quick stats (all outlets)", expanded=False):
                for loc in sorted(
                    database.get_all_locations(), key=lambda x: x["name"]
                ):
                    st.write(f"**{loc['name']}**")
                    st.write(
                        f"- Monthly target: {utils.format_currency(loc.get('target_monthly_sales', 0))}"
                        f"  |  Seats: {loc.get('seat_count') or '—'}"
                    )
                    st.markdown("---")
