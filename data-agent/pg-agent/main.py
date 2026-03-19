"""
pg-agent / main.py
PostgreSQL → FastAPI REST API
- Auto-exposes every table as a CRUD endpoint
- Custom SQL query endpoint
- OpenAI-powered natural language query endpoint
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.database import db
from routes import tables, query, sql, nlq, views
from agent_config import ALLOWED_ORIGINS


# ── Simplified Response for /ask endpoint (chatbot-friendly) ─────────────────
class SimplifiedAskResponse(BaseModel):
    question: str
    answer: str
    generated_sql: str


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
async def ask_proxy(req: nlq.NLQRequest):
    """Simplified endpoint for external tools (chatbot-friendly).

    Returns: question, answer (AI-generated summary), and generated_sql.
    This is a user-friendly alternative to /api/nlq/ask.
    """
    import json
    from openai import AsyncOpenAI
    from agent_config import OPENAI_API_KEY, OPENAI_MODEL

    # Use the typed request model so Swagger can show the proper schema (question + limit)
    nlq_result = await nlq.nlq_ask(req)
    
    # Step 2: Generate AI chatbot-friendly summary (like frontend does)
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
        except Exception as e:
            # Fallback if LLM call fails
            answer_summary = f"Found {nlq_result.row_count} result(s). Data: {nlq_result.rows[0] if nlq_result.rows else 'No results'}"
    
    return SimplifiedAskResponse(
        question=nlq_result.question,
        answer=answer_summary,
        generated_sql=nlq_result.generated_sql,
    )


if __name__ == "__main__":
    import uvicorn
    from agent_config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
