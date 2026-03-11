"""
routes/tables.py
Auto-exposes every PostgreSQL table as a REST endpoint.

GET    /api/tables                      → list all tables
GET    /api/tables/{table}              → paginated rows  (filter, sort, limit, offset)
GET    /api/tables/{table}/schema       → column definitions + primary keys
GET    /api/tables/{table}/count        → total row count (with optional filter)
GET    /api/tables/{table}/{pk_value}   → single row by primary key
POST   /api/tables/{table}             → insert a row
PUT    /api/tables/{table}/{pk_value}   → full replace a row
PATCH  /api/tables/{table}/{pk_value}   → partial update
DELETE /api/tables/{table}/{pk_value}   → delete a row
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse

from core.database import db
from agent_config import DEFAULT_LIMIT, MAX_LIMIT, PG_SCHEMA

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_pk(table: str) -> str:
    """Return the first primary key column, raise 400 if none."""
    pks = await db.primary_keys(table, PG_SCHEMA)
    if not pks:
        raise HTTPException(400, f"Table '{table}' has no primary key.")
    return pks[0]


async def _assert_table(table: str):
    tables = await db.list_tables(PG_SCHEMA)
    if table not in tables:
        raise HTTPException(404, f"Table '{table}' not found in schema '{PG_SCHEMA}'.")
    db.safe_identifier(table)


def _serialize(rows: list[dict]) -> list[dict]:
    """Make rows JSON-serialisable (dates, Decimals, etc.)."""
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


# ── List all tables ───────────────────────────────────────────────────────────

@router.get("", summary="List all tables")
async def list_tables():
    tables = await db.list_tables(PG_SCHEMA)
    return {"schema": PG_SCHEMA, "tables": tables, "count": len(tables)}


# ── Table schema ──────────────────────────────────────────────────────────────

@router.get("/{table}/schema", summary="Column definitions + primary keys")
async def table_schema(table: str):
    await _assert_table(table)
    cols = await db.table_columns(table, PG_SCHEMA)
    pks  = await db.primary_keys(table, PG_SCHEMA)
    return {"table": table, "primary_keys": pks, "columns": cols}


# ── Row count ─────────────────────────────────────────────────────────────────

@router.get("/{table}/count", summary="Total row count")
async def row_count(
    table: str,
    filter_col: str | None = Query(None, description="Column to filter on"),
    filter_val: str | None = Query(None, description="Value to match"),
):
    await _assert_table(table)
    t = db.safe_identifier(table)

    if filter_col and filter_val is not None:
        sql = f"SELECT COUNT(*) AS cnt FROM {db.quote_identifier(PG_SCHEMA)}.{db.quote_identifier(t)} WHERE {db.quote_identifier(filter_col)} = :val"
        row = await db.fetch_one(sql, {"val": filter_val})
    else:
        sql = f"SELECT COUNT(*) AS cnt FROM {db.quote_identifier(PG_SCHEMA)}.{db.quote_identifier(t)}"
        row = await db.fetch_one(sql)

    return {"table": table, "count": row["cnt"]}


# ── List rows ─────────────────────────────────────────────────────────────────

@router.get("/{table}", summary="Paginated rows with optional filter & sort")
async def list_rows(
    table: str,
    limit:      int          = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset:     int          = Query(0, ge=0),
    sort_by:    str | None   = Query(None, description="Column to sort by"),
    sort_order: str          = Query("asc", regex="^(asc|desc)$"),
    filter_col: str | None   = Query(None, description="Column to filter on (exact match)"),
    filter_val: str | None   = Query(None, description="Value to match"),
    columns:    str | None   = Query(None, description="Comma-separated columns to return"),
):
    await _assert_table(table)
    t = db.safe_identifier(table)

    sql = db.build_select_sql(
        table=table,
        schema=PG_SCHEMA,
        columns=columns.split(",") if columns else "*",
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_col=filter_col
    )
    
    params = {"filter_val": filter_val} if filter_col and filter_val is not None else {}
    rows = await db.fetch_all(sql, params)

    count_sql = f"SELECT COUNT(*) AS cnt FROM {db.quote_identifier(PG_SCHEMA)}.{db.quote_identifier(t)}"
    if filter_col and filter_val is not None:
        count_sql += f" WHERE {db.quote_identifier(filter_col)} = :filter_val"
        
    total = await db.fetch_one(count_sql, params)

    return {
        "table":  table,
        "total":  total["cnt"],
        "limit":  limit,
        "offset": offset,
        "rows":   _serialize(rows),
    }


# ── Single row by PK ──────────────────────────────────────────────────────────

@router.get("/{table}/{pk_value}", summary="Single row by primary key")
async def get_row(table: str, pk_value: str):
    await _assert_table(table)
    t  = db.safe_identifier(table)
    pk = await _get_pk(table)

    sql = db.build_select_sql(table=table, schema=PG_SCHEMA, columns="*", filter_col=pk)
    row = await db.fetch_one(sql, {"filter_val": pk_value})
    if not row:
        raise HTTPException(404, f"Row with {pk}={pk_value!r} not found in '{table}'.")
    return _serialize([row])[0]


# ── Insert row ────────────────────────────────────────────────────────────────

@router.post("/{table}", summary="Insert a new row", status_code=201)
async def insert_row(table: str, body: dict = Body(...)):
    await _assert_table(table)
    t = db.safe_identifier(table)

    await db.insert_row(table=table, schema=PG_SCHEMA, data=body)
    return {"message": f"Row inserted into '{table}'.", "data": body}


# ── Full replace (PUT) ────────────────────────────────────────────────────────

@router.put("/{table}/{pk_value}", summary="Replace a row (full update)")
async def replace_row(table: str, pk_value: str, body: dict = Body(...)):
    await _assert_table(table)
    t  = db.safe_identifier(table)
    pk = await _get_pk(table)

    n = await db.update_row(table=table, schema=PG_SCHEMA, pk_col=pk, pk_val=pk_value, data=body)
    if n == 0:
        raise HTTPException(404, f"Row with {pk}={pk_value!r} not found.")
    return {"message": f"Row {pk_value} replaced in '{table}'.", "data": body}


# ── Partial update (PATCH) ────────────────────────────────────────────────────

@router.patch("/{table}/{pk_value}", summary="Partial update")
async def update_row(table: str, pk_value: str, body: dict = Body(...)):
    await _assert_table(table)
    if not body:
        raise HTTPException(422, "Request body is empty.")
    t  = db.safe_identifier(table)
    pk = await _get_pk(table)

    n = await db.update_row(table=table, schema=PG_SCHEMA, pk_col=pk, pk_val=pk_value, data=body)
    if n == 0:
        raise HTTPException(404, f"Row with {pk}={pk_value!r} not found.")
    return {"message": f"Row {pk_value} partially updated in '{table}'.", "updated_fields": list(body.keys())}


# ── Delete row ────────────────────────────────────────────────────────────────

@router.delete("/{table}/{pk_value}", summary="Delete a row")
async def delete_row(table: str, pk_value: str):
    await _assert_table(table)
    t  = db.safe_identifier(table)
    pk = await _get_pk(table)

    n = await db.delete_row(table=table, schema=PG_SCHEMA, pk_col=pk, pk_val=pk_value)
    if n == 0:
        raise HTTPException(404, f"Row with {pk}={pk_value!r} not found.")
    return {"message": f"Row {pk_value} deleted from '{table}'."}
