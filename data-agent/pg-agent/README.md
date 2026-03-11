# pg-agent — PostgreSQL → FastAPI REST API

Auto-exposes every PostgreSQL table as a REST endpoint, adds a safe custom SQL runner, and an OpenAI-powered natural language query layer.

## Architecture

```
PostgreSQL DB
      │  asyncpg / SQLAlchemy 2
      ▼
FastAPI (main.py)
  ├── GET/POST/PUT/PATCH/DELETE  /api/tables/{table}  ← auto CRUD for every table
  ├── GET                        /api/tables           ← list all tables
  ├── GET                        /api/schema           ← full schema introspection
  ├── POST                       /api/sql/run          ← run any SELECT
  ├── POST                       /api/sql/explain      ← EXPLAIN ANALYZE
  └── POST                       /api/nlq/ask          ← natural language → SQL → results
      │  OpenAI GPT-4o
      ▼
static/index.html  ← served by FastAPI (Table Explorer + SQL Editor + AI Query UI)
```

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Fill in PG_HOST, PG_DB, PG_USER, PG_PASSWORD, OPENAI_API_KEY

# 3. Run
python main.py
# → http://localhost:8000
```

---

## API Reference

### Auto Table Endpoints

Every table in your PostgreSQL schema is auto-exposed:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tables` | List all tables |
| GET | `/api/tables/{table}` | Paginated rows (filter, sort, columns) |
| GET | `/api/tables/{table}/schema` | Columns + primary keys |
| GET | `/api/tables/{table}/count` | Row count |
| GET | `/api/tables/{table}/{pk}` | Single row by PK |
| POST | `/api/tables/{table}` | Insert row |
| PUT | `/api/tables/{table}/{pk}` | Replace row |
| PATCH | `/api/tables/{table}/{pk}` | Partial update |
| DELETE | `/api/tables/{table}/{pk}` | Delete row |

**Query params for GET rows:**
```
?limit=100&offset=0
&filter_col=department&filter_val=Engineering
&sort_by=salary&sort_order=desc
&columns=id,name,salary
```

---

### Custom SQL

**POST /api/sql/run**
```json
{ "sql": "SELECT department, COUNT(*) FROM employees GROUP BY department" }
```

**POST /api/sql/explain**
```json
{ "sql": "SELECT * FROM employees WHERE department = 'Engineering'" }
```

**GET /api/sql/templates** — ready-to-use SQL snippets

> ⚠️ Write operations (INSERT, UPDATE, DELETE, DROP…) are blocked on the SQL endpoint.

---

### Natural Language Query (AI)

**POST /api/nlq/ask**
```json
{ "question": "Which employees have leave status as NA?" }
```

Response:
```json
{
  "question": "Which employees have leave status as NA?",
  "generated_sql": "SELECT * FROM \"public\".\"employees\" WHERE \"leave\" IS NULL LIMIT 100",
  "row_count": 5,
  "columns": ["id", "name", "department", "leave"],
  "rows": [...],
  "model": "gpt-4o",
  "prompt_tokens": 412,
  "reply_tokens": 38
}
```

---

### Schema Inspection

**GET /api/schema** — all tables and their column definitions  
**GET /api/schema/tables** — just table names  

---

## Config (.env)

| Variable | Default | Description |
|---|---|---|
| PG_HOST | localhost | PostgreSQL host |
| PG_PORT | 5432 | PostgreSQL port |
| PG_DB | postgres | Database name |
| PG_USER | postgres | Username |
| PG_PASSWORD | — | Password |
| PG_SCHEMA | public | Schema to expose |
| DATABASE_URL | — | Full DSN (overrides above) |
| OPENAI_API_KEY | — | For /api/nlq/ask |
| OPENAI_MODEL | gpt-4o | LLM model |
| DEFAULT_LIMIT | 100 | Default page size |
| MAX_LIMIT | 1000 | Hard row cap |
| HOST | 0.0.0.0 | Server bind host |
| PORT | 8000 | Server port |
