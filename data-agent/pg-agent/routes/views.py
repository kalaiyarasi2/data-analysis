"""
routes/views.py
Auto-exposes database views as REST endpoints.
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from core.database import db
from agent_config import DEFAULT_LIMIT, MAX_LIMIT, PG_SCHEMA, DB_TYPE

router = APIRouter()

async def _list_views_internal(schema: str = PG_SCHEMA) -> list[str]:
    """Helper to list ONLY views."""
    if DB_TYPE == "mssql":
        sql = "SELECT name FROM sys.objects WHERE type = 'V' AND schema_id = SCHEMA_ID(:schema) ORDER BY name"
        rows = await db.fetch_all(sql, {"schema": schema})
        return [r["name"] for r in rows]
    else: # postgres
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_type = 'VIEW'
            ORDER BY table_name
        """
        rows = await db.fetch_all(sql, {"schema": schema})
        return [r["table_name"] for r in rows]

async def _assert_view(view: str):
    views = await _list_views_internal(PG_SCHEMA)
    if view not in views:
        raise HTTPException(404, f"View '{view}' not found in schema '{PG_SCHEMA}'.")
    db.safe_identifier(view)

def _serialize(rows: list[dict]) -> list[dict]:
    import decimal, datetime
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

@router.get("", summary="List all views")
async def list_views():
    views = await _list_views_internal(PG_SCHEMA)
    return {"schema": PG_SCHEMA, "views": views, "count": len(views)}

@router.get("/{view}/schema", summary="View column definitions")
async def view_schema(view: str):
    await _assert_view(view)
    cols = await db.table_columns(view, PG_SCHEMA)
    return {"view": view, "columns": cols}

@router.get("/{view}", summary="Paginated view rows")
async def list_view_rows(
    view: str,
    limit:      int          = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset:     int          = Query(0, ge=0),
    sort_by:    str | None   = Query(None, description="Column to sort by"),
    sort_order: str          = Query("asc", regex="^(asc|desc)$"),
    columns:    str | None   = Query(None, description="Comma-separated columns to return"),
):
    try:
        await _assert_view(view)
        
        sql = db.build_select_sql(
            table=view,
            schema=PG_SCHEMA,
            columns=columns.split(",") if columns else "*",
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        rows = await db.fetch_all(sql)
        
        # Count total for pagination
        t = db.safe_identifier(view)
        count_sql = f"SELECT COUNT(*) AS cnt FROM {db.quote_identifier(PG_SCHEMA)}.{db.quote_identifier(t)}"
        total = await db.fetch_one(count_sql)

        return {
            "view":   view,
            "total":  total["cnt"],
            "limit":  limit,
            "offset": offset,
            "rows":   _serialize(rows),
        }
    except Exception as e:
        import logging
        logging.error(f"Error fetching rows for view {view}: {e}")
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")
