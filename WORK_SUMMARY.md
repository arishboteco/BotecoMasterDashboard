# Boteco Dashboard - Work Summary

## Project Overview
A Streamlit-based dashboard for Boteco Bangalore restaurant to manage daily sales, generate WhatsApp-ready reports, and analyze historical data.

**Repository:** https://github.com/arishboteco/BotecoMasterDashboard

---

## What Was Built

### Core Application Files

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit application with 4 tabs: Upload, Report, Analytics, Settings |
| `database.py` | SQLite database with tables: locations, users, daily_summaries, category_sales, service_sales |
| `parser.py` | XLSX file parser for POS data extraction |
| `reports.py` | WhatsApp report generator (text + image) |
| `auth.py` | Password authentication system |
| `utils.py` | Helper functions for formatting, date handling |
| `config.py` | Configuration settings (targets, currency format) |

### Database Schema

```
locations (id, name, target_monthly_sales, target_daily_sales)
users (id, username, password_hash, email, role, location_id)
daily_summaries (id, location_id, date, covers, turns, gross_total, net_total, 
                 cash_sales, card_sales, gpay_sales, zomato_sales, other_sales,
                 service_charge, cgst, sgst, discount, complimentary, apc,
                 target, pct_target, mtd_*, created_at)
category_sales (id, summary_id, category, qty, amount)
service_sales (id, summary_id, service_type, amount)
upload_history (id, location_id, date, filename, file_type, uploaded_by, uploaded_at)
```

---

## Features Implemented

### 1. Data Upload
- [x] XLSX file upload (multiple files)
- [x] Manual data entry form
- [x] Upload history tracking
- [x] Automatic date detection from files

### 2. Daily Report
- [x] Sales KPI cards (Net Sales, Covers, APC, Target Achievement)
- [x] Payment breakdown display
- [x] MTD summary
- [x] **WhatsApp Text Report** - Formatted with emojis, copy to clipboard
- [x] **WhatsApp Image Report** - Dark themed PNG generation, downloadable

### 3. Analytics
- [x] Daily sales trend (line chart)
- [x] Covers trend (bar chart)
- [x] Payment mode distribution (pie chart)
- [x] Target achievement tracking
- [x] Period selection (This Week, Last 7 Days, This Month, Last 30 Days)

### 4. Settings
- [x] Location management (name, monthly target)
- [x] User authentication
- [x] Role-based access (admin/manager)

### 5. Security
- [x] Password-protected access
- [x] Admin role verification
- [x] Session management

---

## Configuration

```python
MONTHLY_TARGET = 5,00,000
DAILY_TARGET = 16,667 (monthly / 30)
SERVICE_CHARGE_RATE = 10%
GST_RATE = 2.5% (CGST + SGST)
```

---

## Deployment

**Platform:** Streamlit Cloud  
**URL:** https://arishboteco-botecomasterdashboard.streamlit.app

**Setup on Streamlit Cloud:**
1. Connect GitHub repository
2. Set main file: `app.py`
3. Deploy

---

## Current Limitations

1. **SQLite on Cloud:** File-based database has limitations on Streamlit Cloud (read-only, 1GB limit)
   - **Recommendation:** For production, migrate to PostgreSQL or use Streamlit Cloud's built-in data storage

2. **XLSX Parser:** Auto-detection may not work for all POS formats
   - **Recommendation:** Upload actual POS files to improve parsing logic

3. **Single Location:** Currently configured for Boteco Bangalore only
   - **Recommendation:** Multi-location support planned but not fully implemented

---

## Next Steps / Recommendations

### Immediate
1. ✅ Test dashboard with actual POS data files
2. ✅ Verify WhatsApp report format matches your WhatsApp group style
3. ✅ Add actual logo/branding if available

### Short Term
1. Migrate to PostgreSQL for cloud deployment stability
2. Add more POS file format parsers
3. Implement category/service data entry in manual form
4. Add date range picker for analytics

### Long Term
1. Multi-location support
2. WhatsApp API integration (direct sending)
3. SMS/Email notifications
4. Inventory integration
5. Staff management module
6. Customer feedback integration

---

## Tech Stack

| Component | Technology |
|----------|------------|
| Frontend | Streamlit |
| Database | SQLite (local) / PostgreSQL (recommended) |
| Charts | Plotly |
| Image Gen | Matplotlib + Pillow |
| Auth | Custom session-based |

---

## Files Structure

```
boteco_dashboard/
├── app.py              # 24KB - Main application
├── database.py          # 14KB - Database models
├── parser.py           # 12KB - File parsing
├── reports.py          # 12KB - Report generation
├── auth.py             # 6KB - Authentication
├── utils.py           # 6KB - Utilities
├── config.py          # 1KB - Configuration
├── requirements.txt    # Dependencies
├── README.md          # Documentation
└── .gitignore         # Git rules
```

---

## Contact & Support

For issues or feature requests, create an issue on GitHub:
https://github.com/arishboteco/BotecoMasterDashboard/issues

---

*Generated: 30 March 2026*
*Last Updated: 30 March 2026*
