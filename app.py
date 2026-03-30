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
import database
import parser
import sheet_reports as reports
import utils
import auth
import clipboard_ui

# Page configuration
st.set_page_config(
    page_title="Boteco Dashboard",
    page_icon="🥂",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #e94560;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #e94560;
    }
    .stMetric {
        background: #ffffff;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    .error-box {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }
    .upload-zone {
        border: 2px dashed #e94560;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        background: #fff5f7;
    }
    div[data-testid="stMetricValue"] {
        color: #e94560;
        font-weight: bold;
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

        # Main content
        location_id = st.session_state.location_id
        location_settings = database.get_location_settings(location_id)

        # Tabs
        tab1, tab2, tab3, tab4 = st.tabs(
            ["📤 Upload Data", "📊 Daily Report", "📈 Analytics", "⚙️ Settings"]
        )

        # ============ TAB 1: Upload Data ============
        with tab1:
            st.header("Upload POS Data")

            flash = st.session_state.pop("_import_summary_flash", None)
            if flash is not None:
                sd, sk, nc = flash
                st.success(
                    f"Last import: **{sd}** day(s) saved, **{sk}** day(s) skipped "
                    f"(validation), **{nc}** parser note(s)."
                )

            st.markdown("### Upload Files")
            uploaded_files = st.file_uploader(
                "Upload XLSX files from POS system",
                type=["xlsx", "xls"],
                accept_multiple_files=True,
                help="Upload one or more XLSX files from your POS system",
            )

            if uploaded_files:
                for file in uploaded_files:
                    st.success(f"✅ {file.name} ready")

                if st.button(
                    "Import & save to database",
                    type="primary",
                    key="import_pos_batch",
                ):
                    files_payload = [(f.name, f.getvalue()) for f in uploaded_files]
                    results, batch_notes = parser.process_upload_batch(files_payload)
                    for note in batch_notes:
                        st.warning(note)

                    monthly_tgt = (
                        location_settings.get(
                            "target_monthly_sales", config.MONTHLY_TARGET
                        )
                        if location_settings
                        else config.MONTHLY_TARGET
                    )
                    daily_tgt = (
                        location_settings.get(
                            "target_daily_sales", config.DAILY_TARGET
                        )
                        if location_settings
                        else config.DAILY_TARGET
                    )
                    uploaded_by = st.session_state.get("username") or "user"
                    saved_any = False
                    saved_days = 0
                    skipped_validation = 0

                    for date_str, merged, day_errs in results:
                        if day_errs:
                            skipped_validation += 1
                            st.error(
                                f"{date_str}: " + " ".join(day_errs)
                                + " (add All Restaurant Sales or Sales Summary for this date)"
                            )
                            continue
                        merged["target"] = daily_tgt
                        merged = parser.calculate_derived_metrics(merged)
                        mtd = parser.calculate_mtd_metrics(
                            location_id, monthly_tgt
                        )
                        merged.update(mtd)
                        database.save_daily_summary(location_id, merged)
                        fnames = ", ".join(f.name for f in uploaded_files)
                        if len(fnames) > 180:
                            fnames = fnames[:177] + "..."
                        database.save_upload_record(
                            location_id,
                            date_str,
                            fnames,
                            "pos_batch",
                            uploaded_by,
                        )
                        st.success(f"Saved data for {date_str}")
                        saved_any = True
                        saved_days += 1

                    note_count = len(batch_notes)
                    st.info(
                        f"**Import summary:** {saved_days} day(s) saved, "
                        f"{skipped_validation} day(s) skipped (validation), "
                        f"{note_count} parser note(s)."
                    )

                    if saved_any:
                        st.session_state["_import_summary_flash"] = (
                            saved_days,
                            skipped_validation,
                            note_count,
                        )
                        st.rerun()

            st.markdown("---")

            with st.expander("ℹ️ Supported File Formats"):
                st.info(
                    """
                **Daily bundle (auto-detected by filename):**
                - `All_Restaurant_Sales_Report` — payments, net/gross, Pax (covers); rows filtered to **Boteco** (`DEFAULT_RESTAURANT_FILTER` in `config.py`).
                - `Restaurant_item_tax_report` — CGST, SGST, service charge (summed).
                - `Restaurant_timing_report` — Breakfast / Lunch / Dinner sales amounts.
                - `Item_Report_Group_Wise` — category mix (Food, Coffee, etc.).
                - `customer_report` — lunch/dinner **PAX** (served & walk-in) for footfall; fills `covers` if sales file has no Pax.
                - `sales_summary` — XLS/XLSX or HTML-as-.xls; keyword parsing for legacy layouts.

                Files for the **same calendar date** in one batch are merged before save. **Multiple dates** in one upload are split and saved per day. Undated files are only auto-assigned when the whole batch is a single day; in a multi-day batch they are skipped with a warning. Each calendar day still needs at least one sales export (net/gross); footfall-only files alone cannot create a row.
                """
                )

            # Show recent uploads
            st.markdown("---")
            st.markdown("### Recent Entries")

            col_hist1, col_hist2 = st.columns([1, 2])
            with col_hist1:
                history = database.get_upload_history(location_id, 10)
                if history:
                    st.dataframe(pd.DataFrame(history), use_container_width=True)

            with col_hist2:
                st.info("📋 Entry history shows recent POS imports.")

        # ============ TAB 2: Daily Report ============
        with tab2:
            st.header("Daily Sales Report")

            # Date selector
            col_date_sel1, col_date_sel2 = st.columns([1, 2])
            with col_date_sel1:
                selected_date = st.date_input("Select Date", datetime.now())

            date_str = selected_date.strftime("%Y-%m-%d")
            summary = database.get_daily_summary(location_id, date_str)

            if summary:
                # Calculate MTD for display
                mtd = parser.calculate_mtd_metrics(
                    location_id,
                    location_settings.get("target_monthly_sales", config.MONTHLY_TARGET)
                    if location_settings
                    else config.MONTHLY_TARGET,
                )
                summary.update(mtd)

                # KPI Cards Row 1
                col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

                with col_kpi1:
                    st.metric(
                        "Net Sales",
                        utils.format_currency(summary.get("net_total", 0)),
                        delta=f"vs {utils.format_currency(summary.get('target', 0))} target",
                    )

                with col_kpi2:
                    lc = summary.get("lunch_covers")
                    dc = summary.get("dinner_covers")
                    foot = (
                        f"Lunch {lc:,} · Dinner {dc:,}"
                        if lc is not None and dc is not None
                        else None
                    )
                    st.metric(
                        "Covers",
                        f"{summary.get('covers', 0):,}",
                        delta=foot or f"Turns: {summary.get('turns', 0):.1f}",
                    )

                with col_kpi3:
                    st.metric("APC", utils.format_currency(summary.get("apc", 0)))

                with col_kpi4:
                    pct = summary.get("pct_target", 0)
                    delta_color = "normal" if pct >= 100 else "inverse"
                    st.metric(
                        "Target Achievement",
                        f"{pct:.1f}%",
                        delta=f"vs {pct:.0f}%",
                        delta_color=delta_color,
                    )

                st.markdown("---")

                # Sales Details
                col_det1, col_det2 = st.columns(2)

                with col_det1:
                    st.markdown("### 💰 Sales Breakdown")

                    sales_data = {
                        "Payment Mode": [
                            "Gross Total",
                            "Cash",
                            "GPay",
                            "Zomato",
                            "Card",
                            "Other",
                        ],
                        "Amount (₹)": [
                            summary.get("gross_total", 0),
                            summary.get("cash_sales", 0),
                            summary.get("gpay_sales", 0),
                            summary.get("zomato_sales", 0),
                            summary.get("card_sales", 0),
                            summary.get("other_sales", 0),
                        ],
                    }
                    st.dataframe(pd.DataFrame(sales_data), use_container_width=True)

                with col_det2:
                    st.markdown("### 📊 MTD Summary")

                    mtd_data = {
                        "Metric": [
                            "Net Sales",
                            "Total Covers",
                            "Avg Daily",
                            "Target",
                            "Achievement",
                        ],
                        "Value": [
                            utils.format_currency(summary.get("mtd_net_sales", 0)),
                            f"{summary.get('mtd_total_covers', 0):,}",
                            utils.format_currency(summary.get("mtd_avg_daily", 0)),
                            utils.format_currency(summary.get("mtd_target", 0)),
                            f"{summary.get('mtd_pct_target', 0):.1f}%",
                        ],
                    }
                    st.dataframe(pd.DataFrame(mtd_data), use_container_width=True)

                st.markdown("---")

                # Sheet-style report + clipboard (matches Google Sheet EOD layout)
                st.markdown("### 📱 WhatsApp / sheet-style report")

                y_m = [int(x) for x in date_str.split("-")[:2]]
                mtd_cat = database.get_category_mtd_totals(location_id, y_m[0], y_m[1])
                mtd_svc = database.get_service_mtd_totals(location_id, y_m[0], y_m[1])
                foot_rows = database.get_summaries_for_month(
                    location_id, y_m[0], y_m[1]
                )

                img_buffer = reports.generate_sheet_style_report_image(
                    summary,
                    st.session_state.location_name or "Boteco",
                    mtd_category=mtd_cat,
                    mtd_service=mtd_svc,
                    month_footfall_rows=foot_rows,
                )
                png_bytes = img_buffer.getvalue()
                section_bufs = reports.generate_sheet_style_report_sections(
                    summary,
                    st.session_state.location_name or "Boteco",
                    mtd_category=mtd_cat,
                    mtd_service=mtd_svc,
                    month_footfall_rows=foot_rows,
                )
                whatsapp_text = reports.generate_whatsapp_text(
                    summary, st.session_state.location_name
                )

                st.image(BytesIO(png_bytes), use_container_width=True)

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
                    )
                with b3:
                    st.download_button(
                        "Download PNG",
                        png_bytes,
                        file_name=f"boteco_sheet_{date_str}.png",
                        mime="image/png",
                        key=f"dl_png_{date_str}",
                    )
                with b4:
                    st.download_button(
                        "Download text",
                        whatsapp_text,
                        file_name=f"boteco_report_{date_str}.txt",
                        mime="text/plain",
                        key=f"dl_txt_{date_str}",
                    )

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
                            )
                        with cb2:
                            st.download_button(
                                "PNG",
                                sec_bytes,
                                file_name=f"boteco_{key}_{date_str}.png",
                                mime="image/png",
                                key=f"dl_sec_{key}_{date_str}",
                            )

                with st.expander("Plain text preview"):
                    st.text_area(
                        "Report text",
                        whatsapp_text,
                        height=280,
                        key=f"whatsapp_text_{date_str}",
                    )
            else:
                st.warning(f"No data found for {selected_date.strftime('%d %b %Y')}")
                st.info(
                    "Import POS files for this date from the **Upload Data** tab."
                )

        # ============ TAB 3: Analytics ============
        with tab3:
            st.header("Sales Analytics")

            # Period selector
            col_per1, col_per2, col_per3 = st.columns([1, 1, 2])

            with col_per1:
                analysis_period = st.selectbox(
                    "Time Period",
                    ["This Week", "Last 7 Days", "This Month", "Last 30 Days"],
                    key="analysis_period",
                )

            with col_per2:
                start_date, end_date = utils.get_date_range(
                    analysis_period.lower().replace(" ", "_")
                )
                st.write(
                    f"**From:** {start_date.strftime('%d %b')} to {end_date.strftime('%d %b %Y')}"
                )

            # Get data for period
            summaries = database.get_summaries_for_date_range(
                location_id,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            if summaries:
                df = pd.DataFrame(summaries)

                # Summary metrics
                st.markdown("### 📈 Period Summary")

                total_sales = df["net_total"].sum()
                avg_daily = df["net_total"].mean()
                total_covers = df["covers"].sum()
                days_with_data = len(df[df["net_total"] > 0])

                col_ana1, col_ana2, col_ana3, col_ana4 = st.columns(4)

                with col_ana1:
                    st.metric("Total Sales", utils.format_currency(total_sales))
                with col_ana2:
                    st.metric("Avg Daily", utils.format_currency(avg_daily))
                with col_ana3:
                    st.metric("Total Covers", f"{total_covers:,}")
                with col_ana4:
                    st.metric("Days with Data", days_with_data)

                st.markdown("---")

                # Charts
                col_chart1, col_chart2 = st.columns(2)

                with col_chart1:
                    st.markdown("### 📊 Daily Sales Trend")

                    fig_line = px.line(
                        df,
                        x="date",
                        y="net_total",
                        markers=True,
                        title="Net Sales Over Time",
                    )
                    fig_line.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Net Sales (₹)",
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_line, use_container_width=True)

                with col_chart2:
                    st.markdown("### 🍽️ Covers Trend")

                    fig_bar = px.bar(df, x="date", y="covers", title="Daily Covers")
                    fig_bar.update_layout(xaxis_title="Date", yaxis_title="Covers")
                    st.plotly_chart(fig_bar, use_container_width=True)

                # Payment breakdown pie chart
                st.markdown("### 💳 Payment Mode Distribution")

                payment_totals = {
                    "Cash": df["cash_sales"].sum(),
                    "GPay": df["gpay_sales"].sum(),
                    "Zomato": df["zomato_sales"].sum(),
                    "Card": df["card_sales"].sum(),
                    "Other": df["other_sales"].sum(),
                }

                fig_pie = px.pie(
                    values=list(payment_totals.values()),
                    names=list(payment_totals.keys()),
                    title="Payment Mode Split",
                )
                st.plotly_chart(fig_pie, use_container_width=True)

                # Target achievement
                st.markdown("### 🎯 Target Achievement")

                if location_settings:
                    monthly_target = location_settings.get(
                        "target_monthly_sales", config.MONTHLY_TARGET
                    )
                    days_in_month = utils.get_days_in_month(
                        datetime.now().year, datetime.now().month
                    )
                    daily_target = monthly_target / days_in_month

                    fig_target = make_subplots(
                        rows=1,
                        cols=2,
                        subplot_titles=["Daily Achievement", "Cumulative Progress"],
                        specs=[[{"type": "bar"}, {"type": "scatter"}]],
                    )

                    # Daily achievement bar
                    df["achievement"] = (
                        (df["net_total"] / daily_target * 100)
                        if daily_target > 0
                        else 0
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

                    # Cumulative progress
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

                    fig_target.update_layout(height=400, showlegend=True)
                    st.plotly_chart(fig_target, use_container_width=True)

                # Data table
                st.markdown("### 📋 Daily Data")
                st.dataframe(
                    df[["date", "covers", "net_total", "target", "pct_target"]],
                    use_container_width=True,
                )

            else:
                st.warning("No data available for the selected period.")
                st.info("Please upload data for this date range.")

        # ============ TAB 4: Settings ============
        with tab4:
            st.header("Settings")

            if auth.is_admin():
                col_set1, col_set2 = st.columns(2)

                with col_set1:
                    st.markdown("### 🏪 Location Settings")

                    with st.form("location_settings"):
                        new_name = st.text_input(
                            "Location Name",
                            value=location_settings.get("name", "Boteco Bangalore")
                            if location_settings
                            else "Boteco Bangalore",
                        )
                        new_target = st.number_input(
                            "Monthly Target (₹)",
                            min_value=0,
                            value=int(
                                location_settings.get(
                                    "target_monthly_sales", config.MONTHLY_TARGET
                                )
                            )
                            if location_settings
                            else config.MONTHLY_TARGET,
                            step=100000,
                        )

                        settings_submit = st.form_submit_button("💾 Save Settings")

                        if settings_submit:
                            database.update_location_settings(
                                location_id,
                                {"name": new_name, "target_monthly_sales": new_target},
                            )
                            st.success("Settings saved!")
                            st.rerun()

                with col_set2:
                    st.markdown("### 👤 Account")
                    st.info(f"**Username:** {st.session_state.username}")
                    st.info(f"**Role:** {st.session_state.user_role}")
                    st.info(f"**Location:** {st.session_state.location_name}")
            else:
                st.info("You don't have permission to modify settings.")
                st.info("Please contact an administrator.")

            st.markdown("---")

            # Quick Stats
            st.markdown("### 📊 Quick Stats")

            all_locations = database.get_all_locations()
            for loc in all_locations:
                st.write(f"**{loc['name']}**")
                st.write(
                    f"- Monthly Target: {utils.format_currency(loc.get('target_monthly_sales', 0))}"
                )
                st.write(
                    f"- Daily Target: {utils.format_currency(loc.get('target_daily_sales', 0))}"
                )
                st.markdown("---")
