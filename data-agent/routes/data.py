"""
routes/data.py — GET /api/data endpoints
Inspect and browse the currently loaded dataset.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any

import store

router = APIRouter()


class DataInfoResponse(BaseModel):
    endpoint: str | None
    row_count: int
    keys: list[str]
    schema_summary: str


class DataRowsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    rows: list[dict]


@router.get("/data/info", response_model=DataInfoResponse)
def data_info():
    """Return metadata about the currently loaded dataset."""
    info = store.get_data()
    if not info["raw_data"]:
        raise HTTPException(status_code=404, detail="No data loaded yet.")
    return DataInfoResponse(
        endpoint=info["endpoint"],
        row_count=info["row_count"],
        keys=info["keys"],
        schema_summary=info["schema_summary"],
    )


@router.get("/data/rows", response_model=DataRowsResponse)
def data_rows(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Return paginated rows from the loaded dataset."""
    info = store.get_data()
    if not info["raw_data"]:
        raise HTTPException(status_code=404, detail="No data loaded yet.")

    start = (page - 1) * page_size
    end   = start + page_size
    rows  = info["raw_data"][start:end]

    return DataRowsResponse(
        total=info["row_count"],
        page=page,
        page_size=page_size,
        rows=rows,
    )


@router.delete("/data")
def clear_data():
    """Clear the in-memory dataset."""
    store.clear()
    return {"message": "Data cleared."}
