"""
DataMind Agent — Python Backend
Uses OpenAI GPT to answer natural language questions about data from any endpoint.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os

from routes.connect import router as connect_router
from routes.query import router as query_router
from routes.data import router as data_router

app = FastAPI(
    title="DataMind Agent API",
    description="AI-powered data analysis agent using OpenAI LLM",
    version="1.0.0"
)

# Allow all origins for development (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(connect_router, prefix="/api", tags=["Connect"])
app.include_router(query_router,   prefix="/api", tags=["Query"])
app.include_router(data_router,    prefix="/api", tags=["Data"])

# Serve the frontend HTML
@app.get("/", response_class=FileResponse)
def serve_ui():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    return {"status": "ok", "message": "DataMind Agent is running"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
