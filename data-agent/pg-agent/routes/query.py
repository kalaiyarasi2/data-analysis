"""
routes/query.py  (schema inspection)
GET /api/schema          → full schema of all tables
GET /api/schema/tables   → just table names
"""

from fastapi import APIRouter
from core.database import db
from agent_config import PG_SCHEMA

router = APIRouter()


@router.get("", summary="Full schema — all tables and their columns")
async def full_schema():
    schema = await db.full_schema(PG_SCHEMA)
    return {
        "pg_schema":   PG_SCHEMA,
        "table_count": len(schema),
        "tables":      schema,
    }


@router.get("/tables", summary="List table names only")
async def table_names():
    tables = await db.list_tables(PG_SCHEMA)
    return {"pg_schema": PG_SCHEMA, "tables": tables}
