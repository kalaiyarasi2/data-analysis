from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import json
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Advanced Data Analysis Agent (SQL-First)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# Configuration
# Extract base API URL (e.g., http://localhost:8001/api) from PG_AGENT_API_URL
raw_url = os.getenv("PG_AGENT_API_URL", "http://localhost:8001/api/tables/")
PG_AGENT_API_BASE = raw_url.split("/tables")[0].rstrip('/')

DEFAULT_TABLE = os.getenv("PG_AGENT_DEFAULT_TABLE", "ClaimDetails")
TABLE_API_BASE = f"{PG_AGENT_API_BASE}/tables"
SQL_ENDPOINT = f"{PG_AGENT_API_BASE}/sql/run"

# Limits
MAX_ROWS_DIRECT = int(os.getenv("MAX_ROWS_LLM", "100"))
TOKEN_SAFE_THRESHOLD = 60000 # Character limit as proxy for tokens to avoid context overflow

class QueryRequest(BaseModel):
    query: str
    endpoint: str = f"{TABLE_API_BASE}/{DEFAULT_TABLE}"

def estimate_tokens(text: str) -> int:
    """Rough character-based estimate of tokens (4 chars per token)."""
    return len(text) // 4

def clean_sql(sql: str) -> str:
    """Strip markdown and trailing semicolons."""
    sql = re.sub(r"```sql|```", "", sql).strip().rstrip(";")
    return sql

def normalize_endpoint(endpoint: str) -> str:
    """Ensure the endpoint has /api/tables/ if it's missing."""
    if "/api/" in endpoint and "/api/tables/" not in endpoint:
        # Check if it looks like http://host:port/api/resource
        new_endpoint = endpoint.replace("/api/", "/api/tables/")
        print(f"DEBUG: Normalized endpoint from {endpoint} to {new_endpoint}")
        return new_endpoint
    return endpoint

async def get_table_metadata(endpoint: str):
    """Fetch total row count and schema from the table endpoint."""
    endpoint = normalize_endpoint(endpoint)
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        # Get count and sample rows
        resp = await http_client.get(f"{endpoint}?limit=5")
        resp.raise_for_status()
        data = resp.json()
        
        total = data.get("total", 0)
        table_name = data.get("table", "unknown_table")
        
        # Get full schema
        schema_resp = await http_client.get(f"{endpoint}/schema")
        schema_resp.raise_for_status()
        schema_data = schema_resp.json()
        
        return {
            "table_name": table_name,
            "total_rows": total,
            "columns": schema_data.get("columns", []),
            "prompt_schema": json.dumps(schema_data.get("columns", []), indent=None)
        }

async def generate_sql_and_run(question: str, metadata: dict):
    """Ask LLM to generate SQL based on schema, then execute it."""
    schema_text = metadata["prompt_schema"]
    table_name = metadata["table_name"]
    db_type = os.getenv("DB_TYPE", "postgres").lower()
    pg_schema = os.getenv("PG_SCHEMA", "public")
    
    dialect_rules = ""
    if db_type == "mssql":
        dialect_rules = f"""- Use T-SQL (MSSQL) syntax.
- Use square brackets for identifiers: [{pg_schema}].[{table_name}]
- Use TOP N instead of LIMIT if appropriate, or OFFSET/FETCH for pagination.
- For counts, use "SELECT COUNT(*) FROM [{pg_schema}].[{table_name}]".
"""
    else:
        dialect_rules = f"""- Use PostgreSQL syntax.
- Use double quotes for identifiers: "{pg_schema}"."{table_name}"
- Use LIMIT clause.
"""

    system_prompt = f"""You are a {db_type} expert. Your goal is to answer the user's question by generating a valid SQL query.
The table name is "{table_name}" in schema "{pg_schema}".
The schema detail is: {schema_text}

Rules:
1. Output ONLY the raw SQL. No markdown, no explanation.
{dialect_rules}
2. Only use SELECT statements.
3. If no limit is implied, default to TOP 100 or LIMIT 100.
"""

    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0
    )
    
    generated_sql = clean_sql(completion.choices[0].message.content)
    with open("last_sql.log", "w") as f:
        f.write(generated_sql)
    print(f"--- GENERATED SQL ({db_type}) ---")
    print(generated_sql)
    print("---------------------------------")
    
    # Run the SQL via pg-agent
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        sql_resp = await http_client.post(SQL_ENDPOINT, json={"sql": generated_sql})
        if sql_resp.status_code != 200:
            error_detail = sql_resp.text
            print(f"SQL Execution Error: {error_detail}")
            raise Exception(f"SQL Error: {error_detail}")
            
        result_data = sql_resp.json()
        
    return generated_sql, result_data

async def fetch_direct_data(endpoint: str, limit: int):
    """Fetch a small chunk of data for direct analysis."""
    endpoint = normalize_endpoint(endpoint)
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        resp = await http_client.get(f"{endpoint}?limit={limit}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("rows", [])

@app.post("/analyze")
async def analyze(request: QueryRequest):
    try:
        # Step 1: Detect table size and metadata
        request.endpoint = normalize_endpoint(request.endpoint)
        metadata = await get_table_metadata(request.endpoint)
        total_rows = metadata["total_rows"]
        
        strategy = "SQL-First"
        if total_rows <= MAX_ROWS_DIRECT:
            strategy = "Direct-Scan"
            rows = await fetch_direct_data(request.endpoint, MAX_ROWS_DIRECT)
            data_to_analyze = json.dumps(rows, indent=None)
            context_description = f"Full dataset provided ({len(rows)} records)."
        else:
            # Strategy: SQL Generation
            generated_sql, sql_result = await generate_sql_and_run(request.query, metadata)
            data_to_analyze = json.dumps(sql_result.get("rows", []), indent=None)
            context_description = f"Analyzed using dynamic SQL: {generated_sql}. Found {sql_result.get('row_count', 0)} matching items out of {total_rows} total rows."

        # Step 2: Final Summary from LLM
        summary_prompt = f"""You are a data analyst. Answer the user's question based on the provided data snippet.
Context: {context_description}
Data: {data_to_analyze}
Question: {request.query}

Instructions:
- Provide a clear, natural language answer.
- If data was filtered by SQL, explain that briefly.
- Be precise with numbers.
"""

        summary_response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0
        )
        
        return {
            "query": request.query,
            "answer": summary_response.choices[0].message.content,
            "strategy": strategy,
            "total_rows": total_rows,
            "context": context_description
        }

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("query_v2:app", host="0.0.0.0", port=8002, reload=True)
