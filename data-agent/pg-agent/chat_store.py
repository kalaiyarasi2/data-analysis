"""
chat_store.py — Process-local in-memory chat history.

This is intentionally NOT persistent: memory is cleared when the server restarts.
For multi-instance deployments, replace with Redis or a database keyed by `session_id`.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any


MAX_HISTORY_MESSAGES = 20  # cap prompt size (10 turns)

_lock = threading.Lock()
_sessions: dict[str, list[dict[str, Any]]] = {}

# Store full table payloads so we can serve them via an HTML link later.
# This is also process-local RAM (like chat history).
MAX_TABLES_PER_SESSION = 5
_tables: dict[str, dict[str, Any]] = {}  # table_id -> {"session_id": ..., "columns": ..., "rows": ...}
_session_table_ids: dict[str, list[str]] = {}  # session_id -> [table_id,...]


def new_session_id() -> str:
    return uuid.uuid4().hex


def ensure_session_id(session_id: str | None) -> str:
    return session_id or new_session_id()


def get_messages(session_id: str) -> list[dict[str, Any]]:
    with _lock:
        # Return a copy to avoid external mutation.
        return list(_sessions.get(session_id, []))


def _trim(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages
    return messages[-MAX_HISTORY_MESSAGES:]


def set_messages(session_id: str, messages: list[dict[str, Any]]) -> None:
    """
    Store conversation messages for a session.

    We keep `role` + `content` as strings, but we also preserve any extra
    fields (e.g. `table#<id>: "<url>"`) so the client can reconstruct UI.
    """
    import json

    cleaned: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role", "")).lower()
        if role not in ("user", "assistant"):
            continue
        content = m.get("content", "")

        msg: dict[str, Any] = {"role": role, "content": str(content)}
        # Preserve any additional fields provided by the caller.
        for k, v in m.items():
            if k in ("role", "content"):
                continue
            if v is None:
                continue
            if isinstance(v, str):
                msg[k] = v
            elif isinstance(v, (int, float, bool)):
                msg[k] = str(v)
            else:
                try:
                    msg[k] = json.dumps(v, default=str)
                except Exception:
                    msg[k] = str(v)

        cleaned.append(msg)

    with _lock:
        _sessions[session_id] = _trim(cleaned)


def append_turn(session_id: str, user_content: str, assistant_content: str) -> list[dict[str, Any]]:
    with _lock:
        history = list(_sessions.get(session_id, []))
        history.append({"role": "user", "content": str(user_content)})
        history.append({"role": "assistant", "content": str(assistant_content)})
        _sessions[session_id] = _trim(history)
        return list(_sessions[session_id])


def clear_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)

        # Also clear any stored table payloads for this session.
        table_ids = _session_table_ids.pop(session_id, [])
        for tid in table_ids:
            _tables.pop(tid, None)


def store_table(session_id: str, columns: list[str], rows: list[dict[str, Any]]) -> str:
    """
    Store the rows/columns payload for a session and return a `table_id`.
    """
    table_id = uuid.uuid4().hex
    with _lock:
        _tables[table_id] = {
            "session_id": session_id,
            "columns": columns,
            "rows": rows,
        }
        ids = _session_table_ids.setdefault(session_id, [])
        ids.append(table_id)

        # Trim stored tables for this session to avoid unbounded growth.
        if len(ids) > MAX_TABLES_PER_SESSION:
            overflow = len(ids) - MAX_TABLES_PER_SESSION
            for old_id in ids[:overflow]:
                _tables.pop(old_id, None)
            del ids[:overflow]

    return table_id


def get_table(session_id: str, table_id: str) -> dict[str, Any] | None:
    with _lock:
        payload = _tables.get(table_id)
        if not payload:
            return None
        if payload.get("session_id") != session_id:
            return None
        return payload

