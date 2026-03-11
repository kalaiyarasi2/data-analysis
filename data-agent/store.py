"""
store.py — Simple in-memory session store.
In production, replace with Redis or a database.
"""

from typing import Any

# Holds the last fetched dataset + metadata
_store: dict[str, Any] = {
    "endpoint":   None,   # URL that was fetched
    "raw_data":   [],     # list of dicts
    "keys":       [],     # column names
    "row_count":  0,
    "schema_summary": "", # short text description of the schema
}


def set_data(endpoint: str, data: list[dict]):
    _store["endpoint"]  = endpoint
    _store["raw_data"]  = data
    _store["keys"]      = list(data[0].keys()) if data else []
    _store["row_count"] = len(data)
    _store["schema_summary"] = _build_schema_summary(data)


def get_data() -> dict:
    return _store


def clear():
    _store.update(endpoint=None, raw_data=[], keys=[], row_count=0, schema_summary="")


def _build_schema_summary(data: list[dict]) -> str:
    """Build a short human-readable summary of the data schema."""
    if not data:
        return "No data."
    keys = list(data[0].keys())
    sample = data[0]
    lines = [f"  - {k}: {type(sample.get(k)).__name__} (e.g. {repr(sample.get(k))[:40]})"
             for k in keys]
    return f"Fields ({len(keys)}):\n" + "\n".join(lines)
