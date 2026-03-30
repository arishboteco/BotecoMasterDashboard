# Boteco Dashboard - Restaurant Sales Management System

## Setup Instructions

### 1. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate   # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
streamlit run app.py
```

### 4. First Time Setup
- On first run, you'll be prompted to create an admin account
- Default location "Boteco Bangalore" will be created
- Set your monthly sales target (default: ₹5,00,000)

## Cloud Deployment (Streamlit Cloud)

1. Push this code to GitHub
2. Go to [streamlit.io](https://streamlit.io)
3. Connect your GitHub repository
4. Deploy

**Note:** For cloud deployment, SQLite file storage is limited.
Consider using an external database (PostgreSQL, MySQL) for production.

## Default Credentials
- Username: admin
- Password: (set during first run)

## Features
- Multi-location support
- XLSX file upload for POS data
- WhatsApp-ready report generation
- Historical analytics and trends
- Target tracking

## File Structure
```
boteco_dashboard/
├── app.py              # Main application
├── database.py          # Database models
├── parser.py           # File parsing
├── reports.py           # Report generation
├── auth.py             # Authentication
├── utils.py            # Utilities
├── config.py           # Configuration
└── data/
    └── boteco.db       # SQLite database (auto-created)
```
