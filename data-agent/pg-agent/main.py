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

from core.database import db
from routes import tables, query, sql, nlq, views
from agent_config import ALLOWED_ORIGINS


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


if __name__ == "__main__":
    import uvicorn
    from agent_config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
