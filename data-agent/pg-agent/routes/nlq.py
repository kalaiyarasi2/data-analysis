"""
routes/nlq.py — Natural Language Query
POST /api/nlq/ask

Flow:
  1. Load full DB schema (tables + views)
  2. Send schema + user question to OpenAI → get SQL
  3. Execute generated SQL
  4. Return rows + the generated SQL (for transparency)
"""

from __future__ import annotations
import re, decimal, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI
from typing import Any, Literal

from core.database import db
from agent_config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS, PG_SCHEMA, DB_TYPE
from chat_store import MAX_HISTORY_MESSAGES

router  = APIRouter()
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# ── Serialise ─────────────────────────────────────────────────────────────────
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


# ── System prompt ─────────────────────────────────────────────────────────────
def _system_prompt(schema_text: str, db_type: str = "mssql") -> str:
    if db_type == "mssql":
        dialect_rules = f"""- Use T-SQL (Microsoft SQL Server) syntax.
- Use square brackets for ALL identifiers: [{PG_SCHEMA}].[TableName], [ColumnName].
- Use TOP N instead of LIMIT: e.g. SELECT TOP 100 [col] FROM [{PG_SCHEMA}].[Table]
- Do NOT use LIMIT keyword — it is not valid in T-SQL.
- Use ISNULL() for null checks, GETDATE() for current date.
- String concatenation uses +, not ||.
- For pagination: ORDER BY [col] OFFSET 0 ROWS FETCH NEXT 100 ROWS ONLY.
- When ordering or filtering on numeric values stored as VARCHAR (for example amounts with commas), ALWAYS use a safe conversion pattern:
  - First remove commas using REPLACE(col, ',', '').
  - Then use TRY_CONVERT(FLOAT, REPLACE(col, ',', '')) instead of CAST/CONVERT.
  - Optionally filter to rows where TRY_CONVERT(FLOAT, REPLACE(col, ',', '')) IS NOT NULL to avoid conversion errors."""
    else:
        dialect_rules = f"""- Use PostgreSQL syntax.
- Use double-quotes for identifiers: "{PG_SCHEMA}"."table_name".
- Use LIMIT clause."""

    return f"""You are a {db_type.upper()} database expert. Convert the user's natural language question into a valid SQL SELECT query.

IMPORTANT RULES FOR ACCURACY:
- **Robust Searching (CRITICAL)**: When filtering by business/insured/company names (e.g. "Kates Detective"):
  - ALWAYS use `LIKE '%Term%'` instead of `=`.
  - **Punctuation Robustness**: If a name might have punctuation (Kate's, Wal-Mart), use wildcards for each word: `LIKE '%Kate%' AND LIKE '%Detective%'`.
  - Search multiple columns: Check `[EmployerLocation]`, `[Insured]`, `[Account]`, `[NameofBusiness]`.
  - Example: `WHERE ([EmployerLocation] LIKE '%Kate%' AND [EmployerLocation] LIKE '%Detective%')`
- **Table Selection**: If multiple tables seem relevant (e.g., `ClaimDetails` and `Tbl_Claims_datas`), query the most modern sounding one (e.g. `ClaimDetails`) or the one that seems most comprehensive.
- Output ONLY the raw SQL. No markdown, no explanation, no code fences.
- Use only tables, views, and columns that exist in the schema below.
{dialect_rules}
- Do NOT use INSERT, UPDATE, DELETE, DROP, ALTER, or any write operations.
- Always include a row limit of 100 unless the user explicitly asks for more.
- For aggregations (SUM, COUNT, AVG), always include GROUP BY.
- Use IS NULL / IS NOT NULL for null checks.
- You may query views by their view name.

Database schema (tables and views):
{schema_text}"""


# ── Models ────────────────────────────────────────────────────────────────────
class NLQRequest(BaseModel):
    question: str
    limit:    int = 100
    # Optional per-chat identifiers for external tools.
    # If provided, the server can reuse stored conversation history.
    session_id: str | None = None
    # Optional full chat history sent by the client. When present, it is used as context
    # for generating SQL (and may also be persisted by the proxy layer).
    messages: list["NLQChatMessage"] | None = None


class NLQResponse(BaseModel):
    question:      str
    generated_sql: str
    row_count:     int
    columns:       list[str]
    rows:          list[dict]
    model:         str
    prompt_tokens: int
    reply_tokens:  int


class NLQChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


async def _nlq_ask_core(req: NLQRequest, allowed_views: list[str] | None = None) -> NLQResponse:
    if not OPENAI_API_KEY:
        raise HTTPException(503, "OPENAI_API_KEY is not configured.")
    if not req.question.strip():
        raise HTTPException(422, "Question cannot be empty.")

    db_type = (DB_TYPE or "mssql").lower()

    # 1. Get all table/view names (FAST)
    all_table_names = await db.list_tables(PG_SCHEMA)
    
    # Also get view names
    try:
        if db_type == "mssql":
            view_rows = await db.fetch_all("SELECT name FROM sys.views")
        else:
            view_rows = await db.fetch_all(
                f"SELECT table_name AS name FROM information_schema.views WHERE table_schema = '{PG_SCHEMA}'"
            )
        all_view_names = [v["name"] for v in view_rows]
    except Exception:
        all_view_names = []

    combined_names = [f"TABLE: {t}" for t in all_table_names] + [f"VIEW: {v}" for v in all_view_names]
    names_text = "\n".join(combined_names)

    # 2. Step 1: Table Selection (Filter tables/views down to relevant ones)
    if allowed_views:
        # Strict mode: ignore selection LLM and use only the explicitly allowed views.
        selected_names = [name for name in allowed_views if name in all_table_names or name in all_view_names]
    else:
        selection_prompt = f"""Given the following list of tables and views in a {db_type.upper()} database, identify which ones are relevant to the user's question.
Question: "{req.question}"

Tables/Views:
{names_text}

Rules:
- Return ONLY a comma-separated list of the relevant names (no prefixes like TABLE: or VIEW:).
- If no tables seem relevant, return "NONE".
- Be inclusive if a table might be needed for JOINs.
- Limit to maximum 10 tables."""

        try:
            select_resp = await _client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": selection_prompt}],
                temperature=0,
                max_tokens=200
            )
            selected_text = select_resp.choices[0].message.content or "NONE"
            selected_names = [n.strip() for n in selected_text.split(",") if n.strip() and n.strip() != "NONE"]
        except Exception:
            selected_names = all_table_names[:20]  # Safe fallback

    # 3. Step 2: Fetch detailed columns for ONLY selected tables
    schema_map = {}
    for name in selected_names:
        try:
            cols = await db.table_columns(name, PG_SCHEMA)
            schema_map[name] = cols
        except Exception:
            pass
            
    # Build mini-schema text
    schema_lines = []
    for name, cols in schema_map.items():
        is_view = name in all_view_names
        kind_comment = " -- (VIEW)" if is_view else ""
        col_defs = ", ".join(
            f"[{c['column_name']}] {c['data_type']}"
            for c in cols if isinstance(c, dict) and "column_name" in c
        )
        schema_lines.append(f"  [{PG_SCHEMA}].[{name}] ({col_defs}){kind_comment}")
    schema_text = "\n".join(schema_lines)

    # 4. Phase 2: SQL Generation
    # We keep the system prompt strict ("output ONLY raw SQL") and add prior conversation
    # (if supplied) to help follow-ups like "now filter for 2025".
    sql_messages: list[dict[str, str]] = [
        {"role": "system", "content": _system_prompt(schema_text, db_type)},
    ]

    history_messages: list[dict[str, str]] = []
    if req.messages:
        for m in req.messages:
            # Accept both:
            # - dict-form messages (what the proxy passes)
            # - NLQChatMessage objects (what FastAPI normally parses)
            if isinstance(m, dict):
                role = str(m.get("role", "")).lower()
                content = m.get("content", "")
            else:
                # Pydantic + Literal already restricts roles, but keep it defensive.
                role = str(getattr(m, "role", "")).lower()
                content = getattr(m, "content", "")

            if role not in ("user", "assistant"):
                continue
            history_messages.append({"role": role, "content": str(content)})

    # Cap history to avoid prompt blow-up.
    history_messages = history_messages[-MAX_HISTORY_MESSAGES:]
    sql_messages.extend(history_messages)

    # Avoid duplicating the last user turn if the client already included it.
    if sql_messages and sql_messages[-1]["role"] == "user":
        last_user = sql_messages[-1]["content"].strip()
        if last_user != req.question.strip():
            sql_messages.append({"role": "user", "content": req.question})
    else:
        sql_messages.append({"role": "user", "content": req.question})

    max_attempts = 2
    raw_sql = ""
    last_error = ""
    completion = None

    for attempt in range(max_attempts):
        try:
            completion = await _client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=OPENAI_MAX_TOKENS,
                temperature=0,
                messages=sql_messages,
            )
            raw_sql = completion.choices[0].message.content or ""
            raw_sql = re.sub(r"```sql|```", "", raw_sql).strip().rstrip(";")
            
            if not raw_sql.upper().startswith(("SELECT", "WITH")):
                raise Exception(f"LLM returned a non-SELECT statement: {raw_sql[:80]}")

            # Inject row limit
            if db_type == "mssql":
                if not re.search(r'\bTOP\b', raw_sql, re.IGNORECASE):
                    raw_sql = re.sub(r'(?i)^\s*SELECT\b', f'SELECT TOP {req.limit}', raw_sql)
            else:
                if not re.search(r'\bLIMIT\b', raw_sql, re.IGNORECASE):
                    raw_sql += f" LIMIT {req.limit}"

            # Try Execute
            rows = await db.fetch_all(raw_sql)
            
            # If we reach here, it worked!
            return NLQResponse(
                question=req.question,
                generated_sql=raw_sql,
                row_count=len(rows),
                columns=list(rows[0].keys()) if rows else [],
                rows=_serialize(rows),
                model=OPENAI_MODEL,
                prompt_tokens=completion.usage.prompt_tokens,
                reply_tokens=completion.usage.completion_tokens,
            )

        except Exception as e:
            last_error = str(e)
            
            if attempt < max_attempts - 1:
                # Add failure to conversation context for correction
                sql_messages.append({"role": "assistant", "content": raw_sql})
                sql_messages.append({
                    "role": "user", 
                    "content": f"The SQL above failed with this error: {last_error}\n\nPlease fix the SQL based on the schema and rules provided. Return ONLY the raw corrected SQL."
                })
            else:
                # Final failure
                raise HTTPException(400, f"NLQ failed after {max_attempts} attempts.\nError: {last_error}\n\nLast SQL Try:\n{raw_sql}")

    # Fallback (should not be reached)
    raise HTTPException(400, f"NLQ failed with error: {last_error}")


# ── Route wrappers ─────────────────────────────────────────────────────────────
@router.post("/ask", response_model=NLQResponse, summary="Natural language → SQL → results")
async def nlq_ask(req: NLQRequest):
    return await _nlq_ask_core(req)


async def nlq_ask_limited(req: NLQRequest) -> NLQResponse:
    allowed = ["vw_ProspectDetails", "vw_WageDataAndQuote", "vw_ClientProfitSummary"]
    return await _nlq_ask_core(req, allowed_views=allowed)
