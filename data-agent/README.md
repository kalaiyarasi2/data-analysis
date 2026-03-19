# 📊 Data Analysis System: Project Guide

A powerful, full-stack application for automated database schema generation, Excel-to-DB data ingestion, and AI-powered natural language querying.

---

## 👨‍💻 Developer Guide (Technical Perspective)

### 1. Architecture Overview
The system consists of four main components:
- **Enhanced Uploader (Port 8000)**: Synchronous FastAPI service for Excel processing and dynamic table/database creation.
- **pg-agent (Port 8001)**: Asynchronous "Universal DB Gateway" that provides RESTful access to Postgres, MySQL, and SQL Server.
- **Query Agent (Port 8002)**: AI Controller that translates natural language into insights using OpenAI.
- **Frontend (Port 8080)**: React/Vite dashboard for visualization and management.

### 2. Universal Database Configuration
The system uses `SQLAlchemy` and `Dotenv` for dynamic database switching.
- **Requirements**: 
  - For SQL Server: `ODBC Driver 17 for SQL Server` must be installed.
  - Driver packages (`asyncpg`, `aiomysql`, `aioodbc`, etc.) are included in `requirements.txt`.

#### Connection Settings (`.env`)
```env
DB_TYPE=postgres          # postgres | mysql | mssql
DB_HOST=10.10.8.218       # Network IP or localhost
DB_PORT=5432              # 3306 for MySQL, 1433 for MSSQL
DB_NAME=insurance         # Target database name
DB_USER=postgres
DB_PASSWORD=your_password
DB_SCHEMA=public          # (Postgres/MSSQL only)
```

### 3. Running the Backend
Restart all services after any configuration change:
```powershell
# In separate terminals:
S
cd pg-agent; uvicorn main:app --host 0.0.0.0 --port 8001 --reload
uvicorn query:app --host 0.0.0.0 --port 8002 --reload
```

---

## 👤 End-User Guide (How to Use)

### 1. Ingesting Your Data
1.  Navigate to the **Upload Data** page.
2.  Click the upload box and select your **Excel (.xlsx)** or **CSV** file.
3.  Click **Upload & Create Table**.
4.  The system will:
    - Create the database if it doesn't exist.
    - Infer column types (Dates, Numbers, Text) automatically.
    - Create the table and import all rows.

### 2. Managing Tables
- **Tables List**: View all tables currently in your database.
- **Data View**: Click on a table to see a paginated spreadsheet view of your records.
- **Search & Filter**: Use the column headers to filter for specific values.

### 3. AI Assistant (NLQ)
- Go to the **AI Assistant** page.
- Select the table you want to analyze (the latest upload is selected by default).
- Ask questions like:
  - *"Show me the total sales by region."*
  - *"What is the average claim value for 2024?"*
  - *"Find the top 5 customers with late payments."*
- The AI will generate a summary and show you the relevant data records.

---

## 🛠 Troubleshooting
- **Failed to fetch**: Ensure your local IP in the **Settings** page matches `DB_HOST` in `.env`.
- **404 Not Found (Port 8001)**: Ensure the `pg-agent` is started from within its own subdirectory.
- **Pydantic Warnings**: These are managed by internal configurations and do not affect performance.
