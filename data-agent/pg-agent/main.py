"""
pg-agent / main.py
PostgreSQL → FastAPI REST API
- Auto-exposes every table as a CRUD endpoint
- Custom SQL query endpoint
- OpenAI-powered natural language query endpoint
"""

from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from core.database import db
from routes import tables, query, sql, nlq, views
from agent_config import ALLOWED_ORIGINS
from chat_store import ensure_session_id, get_messages, set_messages, store_table, get_table


# ── Simplified Response for /ask endpoint (chatbot-friendly) ─────────────────
class SimplifiedAskResponse(BaseModel):
    question: str
    answer: str
    generated_sql: str
    session_id: str
    # `messages` can include extra fields (e.g. `table#<id>` link) so use a dict.
    messages: list[dict[str, Any]]


def _wants_detail_rows(question: str) -> bool:
    """
    Heuristic for when the user asks for a real list/table of records.
    Keep deterministic to avoid extra LLM classification calls.
    """
    q = (question or "").lower()
    # Strong “list/detail” signals
    strong = [
        "list",
        "details",
        "detail",
        "show me",
        "show all",
        "show the",
        "provide me a list",
        "all claims",
        "all ",
        "all records",
        "every ",
        "each ",
        "extract",
        "table",
        "records",
    ]
    # Common “summary/aggregation only” signals
    summary_only = [
        "total",
        "count",
        "average",
        "sum",
        "maximum",
        "highest",
        "lowest",
        "minimum",
    ]

    if any(s in q for s in strong):
        # If user explicitly wants a summary metric (e.g. "total ..."),
        # don't switch to rows mode.
        if any(s in q for s in summary_only) and not any(
            s in q for s in ["list", "details", "records", "table", "extract"]
        ):
            return False
        return True
    return False


def _missing_column_from_error_detail(detail: str) -> str | None:
    """
    Extract invalid column name from SQL Server errors like:
      Invalid column name 'NatureOfInjury'.
    """
    import re

    if not detail:
        return None
    m = re.search(r"Invalid column name\s+'([^']+)'", detail)
    return m.group(1) if m else None


def _missing_field_message(detail: str | None, allowed_views: list[str]) -> str:
    missing_col = _missing_column_from_error_detail(detail or "")
    if missing_col:
        return (
            f"The requested field `{missing_col}` is not available in the limited views "
            f"({', '.join(allowed_views)}). Try a different question or use the full endpoint "
            f"`/api/nlq/ask`."
        )
    return (
        "The requested data is not available in the limited views "
        f"({', '.join(allowed_views)}). Try a different question or use the full endpoint "
        f"`/api/nlq/ask`."
    )


def _esc_attr(s: str) -> str:
    # Escape for HTML attribute contexts (e.g. href="...").
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace('"', "&quot;").replace("'", "&#39;")


def _render_table_html(columns: list[str], rows: list[dict[str, Any]]) -> str:
    """
    Render an HTML table for a stored NLQ result.

    This endpoint is used by the `table#<id>` link inside chat history.
    """
    import html
    import re

    def render_cell(v: Any) -> str:
        if v is None or v == "":
            return '<span class="null-val">NULL</span>'
        if isinstance(v, bool):
            return f'<span class="bool-val">{html.escape(str(v))}</span>'
        if isinstance(v, (int, float)):
            return f'<span class="num-val">{html.escape(str(v))}</span>'

        s = str(v)
        trimmed = s.strip()

        href = None
        if re.match(r"^https?://\S+$", trimmed, flags=re.IGNORECASE):
            href = trimmed
        elif re.match(r"^www\.\S+$", trimmed, flags=re.IGNORECASE):
            href = f"https://{trimmed}"

        if href:
            display = s[:58] + "…" if len(s) > 60 else s
            return (
                f'<a class="cell-link" href="{_esc_attr(href)}" '
                f'target="_blank" rel="noopener noreferrer">{html.escape(display)}</a>'
            )

        # Basic truncation to keep table compact.
        return html.escape(s[:60] + ("…" if len(s) > 60 else ""))

    cols = columns or (list(rows[0].keys()) if rows else [])
    thead = "".join(f"<th>{html.escape(c)}</th>" for c in cols)

    tbody_parts: list[str] = []
    for r in rows:
        tds = "".join(f"<td>{render_cell(r.get(c))}</td>" for c in cols)
        tbody_parts.append(f"<tr>{tds}</tr>")

    tbody = "".join(tbody_parts) if tbody_parts else "<tr><td colspan=\"1\">No rows</td></tr>"

    # Minimal standalone styles so it looks reasonable when opened directly.
    style = """
<style>
table{border-collapse:collapse;width:100%;font-family:Arial, sans-serif;font-size:12px}
th,td{border:1px solid #d0d7de;padding:6px 8px;vertical-align:top;text-align:left;white-space:nowrap;max-width:280px;overflow:hidden;text-overflow:ellipsis}
.null-val{color:#6b7280;font-style:italic}
.num-val{color:#7c3aed}
.bool-val{color:#059669}
.cell-link{color:#2563eb;text-decoration:underline}
</style>
"""

    return f"<!doctype html><html><head>{style}</head><body><table>{'<thead><tr>' + thead + '</tr></thead>'}<tbody>{tbody}</tbody></table></body></html>"


def _render_table_widget_html(columns: list[str], rows: list[dict[str, Any]]) -> str:
    """
    Render a compact styled HTML widget (to be embedded inside `messages`).
    Includes:
    - Header background: #F97316
    - Text color: #FFFFFF
    - Auto-scroll (scrollable container) for long tables
    """
    import html
    import re

    def esc_attr(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def render_cell(v: Any) -> str:
        if v is None or v == "":
            return '<span style="color:#cbd5e1;font-style:italic">NULL</span>'
        if isinstance(v, bool):
            return f'<span style="color:#34d399">{html.escape(str(v))}</span>'
        if isinstance(v, (int, float)):
            return f'<span style="color:#a78bfa">{html.escape(str(v))}</span>'

        s = str(v)
        trimmed = s.strip()

        href = None
        if re.match(r"^https?://\S+$", trimmed, flags=re.IGNORECASE):
            href = trimmed
        elif re.match(r"^www\.\S+$", trimmed, flags=re.IGNORECASE):
            href = f"https://{trimmed}"

        if href:
            display = s[:58] + "…" if len(s) > 60 else s
            return (
                f'<a style="color:#60a5fa;text-decoration:underline" '
                f'href="{esc_attr(href)}" target="_blank" rel="noopener noreferrer">'
                f"{html.escape(display)}"
                f"</a>"
            )

        if len(s) > 60:
            s = s[:58] + "…"
        return html.escape(s)

    cols = columns or (list(rows[0].keys()) if rows else [])
    thead = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    tbody_parts: list[str] = []
    for r in rows:
        tds = "".join(f"<td>{render_cell(r.get(c))}</td>" for c in cols)
        tbody_parts.append(f"<tr>{tds}</tr>")

    tbody = "".join(tbody_parts) if tbody_parts else '<tr><td colspan="1">No rows</td></tr>'

    # Inline styles so it works anywhere the HTML is embedded.
    return f"""
<div style="background:#FFFFFF;color:#000000;border:1px solid #D3D3D3;border-radius:10px;margin:10px 0;overflow:hidden;font-family:'Segoe UI', 'Segoe UI Web (West European)', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', sans-serif;">
<div style="background:#F97316;color:#FFFFFF;padding:10px 14px;font-weight:700;font-size:12px;letter-spacing:.2px;">
    Table Results
</div>
<div style="overflow-y:auto;overflow-x:auto;">
<table style="border-spacing:0;width:100%;font-size:12px;">
<style>
        th, td {{
          border: 1px solid #ddd;
          padding: 6px;
        }}
</style>
<thead>
<tr>{thead}</tr>
</thead>
<tbody>
        {tbody}
</tbody>
</table>
</div>
</div>""".strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(
    title="pg-agent API",
    description="PostgreSQL → REST API with auto-table endpoints, custom SQL, and AI natural-language queries",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(tables.router, prefix="/api/tables", tags=["Auto Tables"])
app.include_router(views.router,  prefix="/api/views",  tags=["Auto Views"])
app.include_router(sql.router,    prefix="/api/sql",    tags=["Custom SQL"])
app.include_router(query.router,  prefix="/api/schema", tags=["Schema"])
app.include_router(nlq.router,    prefix="/api/nlq",    tags=["AI / NLQ"])

# ── HTML table endpoint (for `table#<id>` links) ─────────────────────────────
@app.get("/api/nlq/html", response_class=HTMLResponse, include_in_schema=False)
async def nlq_html(session_id: str, table_id: str):
    payload = get_table(session_id=session_id, table_id=table_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Table not found for this session.")
    return _render_table_html(payload.get("columns", []), payload.get("rows", []))

# ── Frontend ──────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=FileResponse, include_in_schema=False)
def ui():
    return FileResponse("static/index.html")

@app.get("/api/info")
def get_info():
    from agent_config import DB_TYPE, DB_HOST, DB_PORT, DB_DB
    return {
        "db_type": DB_TYPE,
        "host": f"{DB_HOST}:{DB_PORT}",
        "database": DB_DB
    }


@app.get("/health")
async def health():
    try:
        # Simple query to test connectivity
        await db.fetch_all("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        import logging
        logging.error(f"Health check failed: {e}")
        return {"status": "error", "database": str(e)}


from routes import nlq


@app.post("/ask", response_model=SimplifiedAskResponse, summary="Chatbot-friendly Q&A endpoint")
async def ask_proxy(request: Request, req: nlq.NLQRequest):
    """Simplified endpoint for external tools (chatbot-friendly).

    Returns: question, answer (AI-generated summary), and generated_sql.
    This is a user-friendly alternative to /api/nlq/ask.
    """
    import json
    from openai import AsyncOpenAI
    from agent_config import OPENAI_API_KEY, OPENAI_MODEL

    # Resolve or create a per-chat session identifier.
    session_id = ensure_session_id(req.session_id)
    base_url = str(request.base_url).rstrip("/")

    # If the client sends full chat history, use it; otherwise, reuse the stored
    # history for this session (process-local).
    if req.messages is not None:
        base_history = [{"role": m.role, "content": m.content} for m in req.messages]
        # Persist the base history before answering, so the proxy can be fully
        # stateless from the caller perspective (client can omit `messages` later).
        set_messages(session_id, base_history)
    else:
        base_history = get_messages(session_id)

    # Call the NLQ layer with chat history so SQL generation can handle follow-ups.
    nlq_req = req.copy(update={"session_id": session_id, "messages": base_history})
    nlq_result = await nlq.nlq_ask(nlq_req)

    wants_details = _wants_detail_rows(req.question)
    
    # Step 2: Generate AI chatbot-friendly summary (like frontend does)
    table_id: str | None = None
    table_html: str | None = None
    if wants_details:
        # For “list/details/all” questions, return the actual records to the
        # caller; keep the answer short and machine-friendly.
        answer_summary = f"Returned {nlq_result.row_count} result(s)."
        table_id = store_table(session_id, nlq_result.columns, nlq_result.rows)
        table_html = _render_table_widget_html(nlq_result.columns, nlq_result.rows)
    else:
        if not OPENAI_API_KEY:
            # Fallback if OpenAI is not available
            answer_summary = f"Found {nlq_result.row_count} result(s). Query: {nlq_result.generated_sql[:100]}..."
        else:
            try:
                client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                data_snippet = json.dumps(nlq_result.rows[:20], indent=2)

                summary_prompt = f"""You are a helpful AI data analyst. Answer the user's question based on the provided data and SQL query.

Question: {nlq_result.question}

SQL Query Executed: {nlq_result.generated_sql}

Results ({nlq_result.row_count} rows found):
{data_snippet}

Please provide a clear, natural language answer:
- Explain what the data shows
- Provide specific numbers/insights from the results
- Be concise but informative (2-3 sentences)
"""

                completion = await client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0,
                    max_tokens=500
                )
                answer_summary = completion.choices[0].message.content
            except Exception:
                # Fallback if LLM call fails
                answer_summary = f"Found {nlq_result.row_count} result(s). Data: {nlq_result.rows[0] if nlq_result.rows else 'No results'}"
    
    # Persist updated conversation history: (user question, assistant answer summary).
    new_history = list(base_history)
    question_text = req.question.strip()
    if new_history and new_history[-1]["role"] == "user" and new_history[-1]["content"].strip() == question_text:
        # Client included the current user question already; only append assistant.
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": answer_summary}
        if wants_details and table_html:
            assistant_msg["table_html"] = table_html
        new_history.append(assistant_msg)
    else:
        new_history.append({"role": "user", "content": question_text})
        assistant_msg = {"role": "assistant", "content": answer_summary}
        if wants_details and table_html:
            assistant_msg["table_html"] = table_html
        new_history.append(assistant_msg)

    set_messages(session_id, new_history)
    updated_messages = get_messages(session_id)

    return SimplifiedAskResponse(
        question=nlq_result.question,
        answer=answer_summary,
        generated_sql=nlq_result.generated_sql,
        session_id=session_id,
        messages=updated_messages,
    )


@app.post(
    "/ask/limited",
    response_model=SimplifiedAskResponse,
    summary="Chatbot-friendly Q&A endpoint (limited views)",
)
async def ask_proxy_limited(request: Request, req: nlq.NLQRequest):
    """Chatbot endpoint restricted to three specific views.

    This behaves like /ask but only queries:
    - vw_ProspectDetails
    - vw_WageDataAndQuote
    - vw_ClientProfitSummary
    """
    import json
    from openai import AsyncOpenAI
    from agent_config import OPENAI_API_KEY, OPENAI_MODEL

    session_id = ensure_session_id(req.session_id)
    base_url = str(request.base_url).rstrip("/")

    if req.messages is not None:
        base_history = [{"role": m.role, "content": m.content} for m in req.messages]
        set_messages(session_id, base_history)
    else:
        base_history = get_messages(session_id)

    nlq_req = req.copy(update={"session_id": session_id, "messages": base_history})
    wants_details = _wants_detail_rows(req.question)

    allowed = ["vw_ProspectDetails", "vw_WageDataAndQuote", "vw_ClientProfitSummary"]
    table_id: str | None = None
    table_html: str | None = None
    try:
        nlq_result = await nlq.nlq_ask_limited(nlq_req)
    except HTTPException as e:
        # Convert “invalid column name” into a friendly response instead
        # of a hard 400 that prevents updating session history.
        answer_summary = _missing_field_message(str(getattr(e, "detail", "")), allowed)

        new_history = list(base_history)
        question_text = req.question.strip()
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": answer_summary}
        if new_history and new_history[-1]["role"] == "user" and new_history[-1]["content"].strip() == question_text:
            new_history.append(assistant_msg)
        else:
            new_history.append({"role": "user", "content": question_text})
            new_history.append(assistant_msg)

        set_messages(session_id, new_history)
        updated_messages = get_messages(session_id)

        return SimplifiedAskResponse(
            question=req.question,
            answer=answer_summary,
            generated_sql="",
            session_id=session_id,
            messages=updated_messages,
        )

    # If no rows are found in the restricted views, return a clear message
    # instead of asking the LLM to summarize an empty result set.
    if nlq_result.row_count == 0:
        answer_summary = (
            "Your question references data that is not available in the allowed views. "
            "This endpoint only has access to vw_ProspectDetails, vw_WageDataAndQuote, "
            "and vw_ClientProfitSummary."
        )
    elif wants_details:
        # For “list/details/all” questions, return the actual records to the caller.
        answer_summary = f"Returned {nlq_result.row_count} result(s)."
        table_id = store_table(session_id, nlq_result.columns, nlq_result.rows)
        table_html = _render_table_widget_html(nlq_result.columns, nlq_result.rows)
    elif not OPENAI_API_KEY:
        answer_summary = f"Found {nlq_result.row_count} result(s). Query: {nlq_result.generated_sql[:100]}..."
    else:
        try:
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            data_snippet = json.dumps(nlq_result.rows[:20], indent=2)

            summary_prompt = f"""You are a helpful AI data analyst. Answer the user's question based on the provided data and SQL query.

Question: {nlq_result.question}

SQL Query Executed: {nlq_result.generated_sql}

Results ({nlq_result.row_count} rows found):
{data_snippet}

Please provide a clear, natural language answer:
- Explain what the data shows
- Provide specific numbers/insights from the results
- Be concise but informative (2-3 sentences)
"""

            completion = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0,
                max_tokens=500,
            )
            answer_summary = completion.choices[0].message.content
        except Exception:
            answer_summary = f"Found {nlq_result.row_count} result(s). Data: {nlq_result.rows[0] if nlq_result.rows else 'No results'}"

    new_history = list(base_history)
    question_text = req.question.strip()
    if new_history and new_history[-1]["role"] == "user" and new_history[-1]["content"].strip() == question_text:
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": answer_summary}
        if wants_details and table_html:
            assistant_msg["table_html"] = table_html
        new_history.append(assistant_msg)
    else:
        new_history.append({"role": "user", "content": question_text})
        assistant_msg = {"role": "assistant", "content": answer_summary}
        if wants_details and table_html:
            assistant_msg["table_html"] = table_html
        new_history.append(assistant_msg)

    set_messages(session_id, new_history)
    updated_messages = get_messages(session_id)

    return SimplifiedAskResponse(
        question=nlq_result.question,
        answer=answer_summary,
        generated_sql=nlq_result.generated_sql,
        session_id=session_id,
        messages=updated_messages,
    )


if __name__ == "__main__":
    import uvicorn
    from agent_config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
