"""
routes/sql.py
POST /api/sql/run   → execute a read-only (SELECT) SQL query
POST /api/sql/explain → EXPLAIN ANALYZE a query
"""

from __future__ import annotations
import re, decimal, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from core.database import db
from agent_config import MAX_LIMIT

router = APIRouter()

# ── Blocklist: deny any write-altering keywords ───────────────────────────────
_WRITE_PATTERN = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE|COPY|VACUUM|ANALYZE\s+TABLE)\b',
    re.IGNORECASE,
)


def _is_safe(sql: str) -> bool:
    """Allow only SELECT / WITH … SELECT / EXPLAIN."""
    stripped = sql.strip().lstrip(";").strip()
    if _WRITE_PATTERN.search(stripped):
        return False
    return bool(re.match(r'^(SELECT|WITH|EXPLAIN)', stripped, re.IGNORECASE))


def _serialize(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if isinstance(v, (datetime.date, datetime.datetime)):
                clean[k] = v.isoformat()
            elif isinstance(v, decimal.Decimal):
                clean[k] = float(v)
            else:
                clean[k] = v
        out.append(clean)
    return out


# ── Models ────────────────────────────────────────────────────────────────────

class SQLRequest(BaseModel):
    sql:    str
    limit:  int = MAX_LIMIT          # soft cap; appended only if not already in query

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("SQL cannot be empty.")
        if not _is_safe(v):
            raise ValueError(
                "Only SELECT queries are allowed. "
                "INSERT / UPDATE / DELETE / DROP etc. are blocked."
            )
        return v.strip()


class ExplainRequest(BaseModel):
    sql: str

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("SQL cannot be empty.")
        return v.strip()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/run", summary="Run a read-only SQL query")
async def run_sql(req: SQLRequest):
    """
    Execute any SELECT statement against the connected PostgreSQL database.
    Write operations (INSERT, UPDATE, DELETE, DROP, …) are blocked.
    """
    # Inject LIMIT/TOP if query doesn't already contain one
    sql = req.sql.rstrip(";")
    from agent_config import DB_TYPE
    
    # Check if limit already exists (either LIMIT or TOP)
    has_limit = re.search(r'\b(LIMIT|TOP)\b', sql, re.IGNORECASE)
    
    if not has_limit:
        if DB_TYPE == "mssql":
            # For MSSQL, we inject TOP right after SELECT (robust to whitespace/newlines)
            sql = re.sub(r'(?i)^\s*SELECT\b', f'SELECT TOP {req.limit}', sql)
        else:
            # For Postgres/MySQL, we append LIMIT
            sql += f" LIMIT {req.limit}"

    try:
        rows = await db.fetch_all(sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL error: {e}")

    return {
        "sql":        req.sql,
        "row_count":  len(rows),
        "columns":    list(rows[0].keys()) if rows else [],
        "rows":       _serialize(rows),
    }


@router.post("/explain", summary="EXPLAIN ANALYZE a query")
async def explain_sql(req: ExplainRequest):
    """
    Returns the PostgreSQL query plan for performance analysis.
    """
    safe_sql = req.sql.rstrip(";")
    explain  = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {safe_sql}"

    try:
        rows = await db.fetch_all(explain)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"EXPLAIN error: {e}")

    plan = rows[0].get("QUERY PLAN") if rows else []
    return {"sql": req.sql, "plan": plan}


@router.get("/templates", summary="Example SQL query templates")
async def sql_templates():
    """Return ready-to-use SQL snippet templates."""
    tables = await db.list_tables()
    t = tables[0] if tables else "your_table"
    return {
        "templates": [
            {"label": "Select all",            "sql": f'SELECT * FROM "{t}" LIMIT 100;'},
            {"label": "Count rows",            "sql": f'SELECT COUNT(*) FROM "{t}";'},
            {"label": "Distinct values",       "sql": f'SELECT DISTINCT column_name FROM "{t}";'},
            {"label": "Group & count",         "sql": f'SELECT column_name, COUNT(*) FROM "{t}" GROUP BY column_name ORDER BY COUNT(*) DESC;'},
            {"label": "Filter rows",           "sql": f"SELECT * FROM \"{t}\" WHERE column_name = 'value';"},
            {"label": "Find NULLs",            "sql": f'SELECT * FROM "{t}" WHERE column_name IS NULL;'},
            {"label": "Order by column",       "sql": f'SELECT * FROM "{t}" ORDER BY column_name DESC LIMIT 50;'},
            {"label": "Join two tables",       "sql": f'SELECT a.*, b.* FROM "{t}" a JOIN other_table b ON a.id = b.foreign_id LIMIT 100;'},
            {"label": "Avg / Min / Max",       "sql": f'SELECT AVG(num_col), MIN(num_col), MAX(num_col) FROM "{t}";'},
            {"label": "Recent records",        "sql": f'SELECT * FROM "{t}" ORDER BY created_at DESC LIMIT 20;'},
        ]
    }
