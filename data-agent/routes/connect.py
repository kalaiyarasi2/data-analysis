"""
routes/connect.py — POST /api/connect
Accepts an endpoint URL + optional auth, fetches the data, stores it in memory.
"""

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional

import store
from config import MAX_ROWS_FETCH
from llm_service import generate_suggestions

router = APIRouter()


# ── Mock employee data (used when url == "MOCK_EMPLOYEES") ───────────────────
MOCK_EMPLOYEES = [
    {"id":"E001","name":"Arjun Mehta",   "department":"Engineering","role":"Senior Dev",     "leave":"NA",      "salary":95000, "joined":"2021-03","gender":"M"},
    {"id":"E002","name":"Priya Sharma",  "department":"Engineering","role":"Tech Lead",      "leave":"Approved","salary":112000,"joined":"2020-07","gender":"F"},
    {"id":"E003","name":"Ravi Kumar",    "department":"Design",     "role":"UI Designer",   "leave":"Rejected","salary":72000, "joined":"2022-01","gender":"M"},
    {"id":"E004","name":"Sneha Patel",   "department":"HR",         "role":"HR Manager",    "leave":"NA",      "salary":68000, "joined":"2019-11","gender":"F"},
    {"id":"E005","name":"Vikram Nair",   "department":"Marketing",  "role":"Growth Lead",   "leave":"Approved","salary":81000, "joined":"2023-04","gender":"M"},
    {"id":"E006","name":"Aisha Khan",    "department":"Engineering","role":"Backend Dev",    "leave":"NA",      "salary":88000, "joined":"2022-09","gender":"F"},
    {"id":"E007","name":"Deepak Roy",    "department":"Finance",    "role":"CFO",           "leave":"Pending", "salary":145000,"joined":"2018-06","gender":"M"},
    {"id":"E008","name":"Meera Iyer",    "department":"Design",     "role":"Sr. Designer",  "leave":"Approved","salary":79000, "joined":"2023-02","gender":"F"},
    {"id":"E009","name":"Karthik Bose",  "department":"Engineering","role":"Frontend Dev",  "leave":"Rejected","salary":82000, "joined":"2021-11","gender":"M"},
    {"id":"E010","name":"Divya Reddy",   "department":"Marketing",  "role":"Content Lead",  "leave":"NA",      "salary":65000, "joined":"2020-03","gender":"F"},
    {"id":"E011","name":"Suresh Menon",  "department":"HR",         "role":"Recruiter",     "leave":"Approved","salary":58000, "joined":"2023-07","gender":"M"},
    {"id":"E012","name":"Anjali Gupta",  "department":"Finance",    "role":"Analyst",       "leave":"Pending", "salary":74000, "joined":"2022-05","gender":"F"},
    {"id":"E013","name":"Rahul Joshi",   "department":"Engineering","role":"DevOps Eng",    "leave":"NA",      "salary":97000, "joined":"2019-08","gender":"M"},
    {"id":"E014","name":"Lakshmi Das",   "department":"Design",     "role":"Brand Designer","leave":"Approved","salary":71000, "joined":"2023-10","gender":"F"},
    {"id":"E015","name":"Nikhil Verma",  "department":"Marketing",  "role":"SEO Specialist","leave":"NA",      "salary":62000, "joined":"2024-01","gender":"M"},
]


# ── Request / Response models ────────────────────────────────────────────────
class ConnectRequest(BaseModel):
    url: str                          # endpoint URL or "MOCK_EMPLOYEES"
    auth_type: Optional[str] = "none" # "none" | "bearer" | "apikey"
    auth_value: Optional[str] = ""


class ConnectResponse(BaseModel):
    success: bool
    endpoint: str
    row_count: int
    keys: list[str]
    schema_summary: str
    suggestions: list[str]
    preview: list[dict]               # first 5 rows for quick display


# ── Helper: extract array from common API wrapper patterns ───────────────────
def extract_array(raw) -> list[dict]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("data", "users", "products", "results", "items",
                    "todos", "posts", "records", "employees"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
        # fall back: first list value found
        for v in raw.values():
            if isinstance(v, list) and len(v) > 0:
                return v
    raise ValueError("Could not find a JSON array in the endpoint response. "
                     "Expected a top-level array or a wrapper like {\"data\": [...]}.")


# ── Route ────────────────────────────────────────────────────────────────────
@router.post("/connect", response_model=ConnectResponse)
async def connect(req: ConnectRequest):
    url = req.url.strip()

    # 1. Fetch data
    if url == "MOCK_EMPLOYEES":
        data = MOCK_EMPLOYEES
    else:
        headers = {"Accept": "application/json"}
        if req.auth_type == "bearer" and req.auth_value:
            headers["Authorization"] = f"Bearer {req.auth_value}"
        elif req.auth_type == "apikey" and req.auth_value:
            headers["X-API-Key"] = req.auth_value

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                resp.raise_for_status()
                raw = resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Endpoint returned HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Could not reach endpoint: {e}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

        try:
            data = extract_array(raw)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    if not data:
        raise HTTPException(status_code=422, detail="Endpoint returned an empty dataset.")

    # 2. Cap rows
    data = data[:MAX_ROWS_FETCH]

    # 3. Persist in store
    store.set_data(url, data)
    info = store.get_data()

    # 4. Ask LLM to generate smart questions (best-effort)
    try:
        suggestions = generate_suggestions(info["schema_summary"], data[0])
    except Exception:
        suggestions = [
            "Which records have missing or NA values?",
            "How many total records are there?",
            f"What are the unique values in {info['keys'][0] if info['keys'] else 'the first field'}?",
        ]

    return ConnectResponse(
        success=True,
        endpoint=url,
        row_count=info["row_count"],
        keys=info["keys"],
        schema_summary=info["schema_summary"],
        suggestions=suggestions,
        preview=data[:5],
    )
