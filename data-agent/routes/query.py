"""
routes/query.py — POST /api/query
Accepts a natural language question, runs OpenAI analysis on stored data.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Optional

import store
from config import MAX_ROWS_LLM
from llm_service import analyze

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    max_rows: Optional[int] = None   # override default MAX_ROWS_LLM if needed


class QueryResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    question: str
    answer: str
    result_type: str                 # "list" | "stat" | "text"
    result_items: list[dict]
    stats: dict
    highlight_indices: list[int]
    model_used: str
    prompt_tokens: int
    reply_tokens: int


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    info = store.get_data()

    if not info["raw_data"]:
        raise HTTPException(
            status_code=400,
            detail="No data loaded. Call POST /api/connect first."
        )

    if not req.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    # Slice rows for LLM (stay within token budget)
    limit = req.max_rows or MAX_ROWS_LLM
    data_slice = info["raw_data"][:limit]

    try:
        result = analyze(
            question=req.question,
            data=data_slice,
            schema_summary=info["schema_summary"],
            total_rows=info["row_count"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {e}")

    return QueryResponse(
        question=req.question,
        answer=result.get("answer", ""),
        result_type=result.get("result_type", "text"),
        result_items=result.get("result_items", []),
        stats=result.get("stats", {}),
        highlight_indices=result.get("highlight_indices", []),
        model_used=result.get("model_used", ""),
        prompt_tokens=result.get("prompt_tokens", 0),
        reply_tokens=result.get("reply_tokens", 0),
    )
