# 📊 Data Analysis & AI Assistant System

A comprehensive full-stack solution for automated database management, data ingestion, and AI-powered natural language querying.

## 🚀 System Architecture

The project is structured into four main interoperable components:

1.  **[Data Uploader (Port 8000)](file:///c:/Users/Intern/data%20analysis/data-agent/main.py)**: A FastAPI service responsible for handling Excel and CSV file uploads, inferring database schemas, and performing bulk data ingestion.
2.  **[pg-agent (Port 8001)](file:///c:/Users/Intern/data%20analysis/data-agent/pg-agent/main.py)**: An asynchronous REST API layer that provides a universal gateway to PostgreSQL, MySQL, and SQL Server databases.
3.  **[Query Agent (Port 8002)](file:///c:/Users/Intern/data%20analysis/data-agent/query.py)**: The AI reasoning engine that translates natural language questions into executable SQL queries using OpenAI.
4.  **[Frontend Dashboard (Port 5173/8080)](file:///c:/Users/Intern/data%20analysis/data-agent/classic-mode-ui-main/src)**: A modern React/Vite/Tailwind interface for managing tables, viewing data, and interacting with the AI Assistant.

---

## 📂 Project Structure

```text
data analysis/
├── data-agent/               # Main Backend & Services
│   ├── pg-agent/             # Universal Database Gateway API
│   ├── classic-mode-ui-main/ # React/Vite Frontend Application
│   ├── routes/               # Modular API Routes
│   ├── static/               # Static assets and built frontend
│   ├── query.py              # Query Agent Entry Point
│   └── main.py              # Data Uploader Entry Point
└── README.md                 # This Root Guide
```

---

## 🛠 Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js & npm (for frontend)
- PostgreSQL (or target database)
- OpenAI API Key

### 2. Startup Sequence
To run the full system, start the following services in separate terminals from the `data-agent` directory:

```powershell
# 1. Start the Data Uploader (Port 8000)

cd "C:\Users\Intern\data analysis\data-agent\upload_data"

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start the Database Gateway (Port 8001)

cd "C:\Users\Intern\data analysis\data-agent"

cd pg-agent; uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 3. Start the Query Agent (Port 8002)

cd "C:\Users\Intern\data analysis\data-agent"

uvicorn query:app --host 0.0.0.0 --port 8002 --reload

# 4. Start the Frontend (Port 5173)
![1773746295949](image/README/1773746295949.png)
```

---

## 📖 Component Documentation

- **[Backend Guide](file:///c:/Users/Intern/data%20analysis/data-agent/README.md)**: Detailed info on ingestion, SQLAlchemy config, and environment settings.
- **[Database API Guide](file:///c:/Users/Intern/data%20analysis/data-agent/pg-agent/README.md)**: Reference for the `/api/tables`, `/api/sql`, and `/api/nlq` endpoints.
- **[Frontend Guide](file:///c:/Users/Intern/data%20analysis/data-agent/classic-mode-ui-main/README.md)**: UI component structure and development workflow.
