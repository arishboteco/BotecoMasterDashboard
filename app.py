import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from io import BytesIO
import base64

import config
import database
import parser
import reports
import utils
import auth

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

            col1, col2 = st.columns([1, 1])

            with col1:
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

                        for date_str, merged, day_errs in results:
                            if day_errs:
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

                        if saved_any:
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

                    Files for the **same calendar date** in one batch are merged before save. Days without net/gross sales are skipped with an error (footfall-only rows need a sales export for that date).
                    """
                    )

            with col2:
                st.markdown("### Manual Entry")
                with st.form("manual_entry_form"):
                    col_date, col_covers = st.columns(2)
                    with col_date:
                        entry_date = st.date_input("Date", datetime.now())
                    with col_covers:
                        entry_covers = st.number_input("Covers", min_value=0, value=0)

                    st.markdown("#### Sales Figures")
                    col_sales1, col_sales2 = st.columns(2)
                    with col_sales1:
                        entry_gross = st.number_input(
                            "Gross Total (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )
                        entry_cash = st.number_input(
                            "Cash Sales (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )
                        entry_card = st.number_input(
                            "Card Sales (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )
                    with col_sales2:
                        entry_gpay = st.number_input(
                            "GPay Sales (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )
                        entry_zomato = st.number_input(
                            "Zomato Sales (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )
                        entry_other = st.number_input(
                            "Other Sales (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )

                    st.markdown("#### Taxes & Charges")
                    col_tax1, col_tax2, col_tax3 = st.columns(3)
                    with col_tax1:
                        entry_service = st.number_input(
                            "Service Charge (₹)",
                            min_value=0.0,
                            value=0.0,
                            format="%.2f",
                        )
                    with col_tax2:
                        entry_cgst = st.number_input(
                            "CGST (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )
                    with col_tax3:
                        entry_sgst = st.number_input(
                            "SGST (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )

                    st.markdown("#### Adjustments")
                    col_adj1, col_adj2 = st.columns(2)
                    with col_adj1:
                        entry_discount = st.number_input(
                            "Discount (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )
                    with col_adj2:
                        entry_complimentary = st.number_input(
                            "Complimentary (₹)", min_value=0.0, value=0.0, format="%.2f"
                        )

                    submitted = st.form_submit_button(
                        "💾 Save Data", use_container_width=True
                    )

                    if submitted:
                        # Calculate net total
                        net_total = entry_gross + entry_service - entry_discount

                        # Calculate derived metrics
                        apc = net_total / entry_covers if entry_covers > 0 else 0
                        target = (
                            location_settings.get(
                                "target_daily_sales", config.DAILY_TARGET
                            )
                            if location_settings
                            else config.DAILY_TARGET
                        )
                        pct_target = (net_total / target * 100) if target > 0 else 0

                        data = {
                            "date": entry_date.strftime("%Y-%m-%d"),
                            "covers": entry_covers,
                            "gross_total": entry_gross,
                            "net_total": net_total,
                            "cash_sales": entry_cash,
                            "card_sales": entry_card,
                            "gpay_sales": entry_gpay,
                            "zomato_sales": entry_zomato,
                            "other_sales": entry_other,
                            "service_charge": entry_service,
                            "cgst": entry_cgst,
                            "sgst": entry_sgst,
                            "discount": entry_discount,
                            "complimentary": entry_complimentary,
                            "apc": apc,
                            "turns": round(entry_covers / 100, 1),
                            "target": target,
                            "pct_target": pct_target,
                        }

                        # Calculate MTD
                        mtd = parser.calculate_mtd_metrics(location_id, target * 30)
                        data.update(mtd)

                        # Save to database
                        summary_id = database.save_daily_summary(location_id, data)

                        st.success(
                            f"✅ Data saved for {entry_date.strftime('%d %b %Y')}"
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
                st.info(
                    "📋 Entry history shows previously uploaded files and manual entries."
                )

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

                # WhatsApp Report Section
                st.markdown("### 📱 WhatsApp Report")

                col_wh1, col_wh2 = st.columns([1, 1])

                with col_wh1:
                    whatsapp_text = reports.generate_whatsapp_text(
                        summary, st.session_state.location_name
                    )

                    st.text_area(
                        "Report Text", whatsapp_text, height=400, key="whatsapp_text"
                    )

                    col_copy1, col_copy2 = st.columns(2)
                    with col_copy1:
                        st.button("📋 Copy to Clipboard", key="copy_text")
                    with col_copy2:
                        st.download_button(
                            "💾 Download Text",
                            whatsapp_text,
                            file_name=f"boteco_report_{date_str}.txt",
                            mime="text/plain",
                            key="download_text",
                        )

                with col_wh2:
                    # Generate and display image
                    img_buffer = reports.generate_report_image(
                        summary, st.session_state.location_name
                    )

                    st.image(img_buffer, use_container_width=True)

                    st.download_button(
                        "📥 Download Report Image",
                        img_buffer.getvalue(),
                        file_name=f"boteco_report_{date_str}.png",
                        mime="image/png",
                        key="download_image",
                    )
            else:
                st.warning(f"No data found for {selected_date.strftime('%d %b %Y')}")
                st.info(
                    "Please upload data for this date or enter manually in the Upload tab."
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
