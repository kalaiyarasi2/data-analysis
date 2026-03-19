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
    """Ensure the endpoint is a full URL. Prepend base URL or fix placeholder IPs if needed."""
    if not endpoint: return endpoint
    endpoint = endpoint.strip()
    
    # Fix hardcoded placeholder IP from frontend if present
    placeholder_ip = "10.10.8.218"
    if placeholder_ip in endpoint:
        endpoint = endpoint.replace(placeholder_ip, "localhost")
    
    # If it looks like it has a host (e.g. localhost:8001) but no protocol, prepend http://
    if endpoint.startswith(("localhost:", "127.0.0.1:")) and not endpoint.startswith(("http://", "https://")):
        endpoint = "http://" + endpoint

    # If it's already a full valid API path with protocol, return it
    if endpoint.startswith(("http://", "https://")):
        return endpoint

    # Handle relative paths - assume they are relative to the pg-agent base
    # PG_AGENT_API_BASE is like http://localhost:8001/api
    base_root = PG_AGENT_API_BASE.split("/api")[0]
    
    if endpoint.startswith("/api/"):
        return f"{base_root}{endpoint}"
    
    if endpoint.startswith("api/"):
        return f"{base_root}/{endpoint}"
        
    # Default: assume it's just the table name or a tables/views path
    if endpoint.startswith(("tables/", "views/")):
        return f"{base_root}/api/{endpoint}"
        
    return f"{base_root}/api/tables/{endpoint}"

def normalize_endpoint_deprecated(endpoint: str) -> str:
    """Ensure the endpoint has /api/tables/[name] or /api/views/[name]. Skip NLQ and other special endpoints."""
    if not endpoint: return endpoint
    endpoint = endpoint.strip()
    
    # Never rewrite NLQ or other special endpoints
    if "/api/nlq/" in endpoint:
        return endpoint
    
    # If it's already a full valid API path, leave it
    if "/api/tables" in endpoint or "/api/views" in endpoint:
        return endpoint
        
    # If it has /api/ but not tables/views, assume it's a tables resource by default
    if "/api/" in endpoint:
        new_endpoint = endpoint.replace("/api/", "/api/tables/")
        print(f"DEBUG: Normalized endpoint from {endpoint} to {new_endpoint}")
        return new_endpoint
            
    return endpoint

async def get_table_metadata(endpoint: str):
    """Fetch total row count and schema from the table or view endpoint."""
    endpoint = normalize_endpoint(endpoint)
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        try:
            # Try original endpoint (defaulting to tables)
            resp = await http_client.get(f"{endpoint}?limit=5")
            if resp.status_code == 404 and "/api/tables/" in endpoint:
                # Fallback: Maybe it's a view?
                view_endpoint = endpoint.replace("/api/tables/", "/api/views/")
                print(f"DEBUG: 404 on tables, trying view endpoint: {view_endpoint}")
                resp = await http_client.get(f"{view_endpoint}?limit=5")
                if resp.status_code == 200:
                    endpoint = view_endpoint
            
            resp.raise_for_status()
            data = resp.json()
            
            total = data.get("total", 0)
            # Use 'view' key if 'table' is missing (for views API)
            resource_name = data.get("table") or data.get("view") or "unknown"
            
            # Get full schema
            schema_resp = await http_client.get(f"{endpoint}/schema")
            schema_resp.raise_for_status()
            schema_data = schema_resp.json()
            
            return {
                "table_name": resource_name,
                "total_rows": total,
                "columns": schema_data.get("columns", []),
                "prompt_schema": json.dumps(schema_data.get("columns", []), indent=None),
                "actual_endpoint": endpoint
            }
        except httpx.HTTPStatusError as e:
            print(f"Metadata Fetch Error: {e.response.status_code} for {e.request.url}")
            raise

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
        # ── NLQ Mode: check BEFORE normalization ─────────────────────────────
        # When user selects "Full Database (AI Query)" endpoint
        if "/api/nlq/ask" in request.endpoint:
            nlq_url = normalize_endpoint(request.endpoint)
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                nlq_resp = await http_client.post(
                    nlq_url,
                    json={"question": request.query, "limit": 100}
                )
                if nlq_resp.status_code != 200:
                    raise Exception(f"NLQ endpoint error {nlq_resp.status_code}: {nlq_resp.text}")
                nlq_data = nlq_resp.json()

            rows = nlq_data.get("rows", [])
            generated_sql = nlq_data.get("generated_sql", "")
            row_count = nlq_data.get("row_count", 0)

            # Summarise the results using LLM
            data_snippet = json.dumps(rows[:50], indent=None)
            summary_prompt = f"""You are a data analyst. Answer the user's question based on the provided data.
Context: The AI generated and ran this SQL query: {generated_sql}
It returned {row_count} records. Here is a sample of up to 50 rows:
{data_snippet}

Question: {request.query}

Instructions:
- Provide a clear, natural language answer with specific numbers.
- Mention key insights from the data.
- Note the SQL used if it helps explain the answer.
"""
            summary_response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0
            )

            return {
                "query": request.query,
                "answer": summary_response.choices[0].message.content,
                "strategy": "NLQ-MultiTable",
                "total_rows": row_count,
                "context": f"AI generated SQL query across all tables. SQL: {generated_sql[:200]}..."
            }

        # ── Standard single-table/view mode ──────────────────────────────────
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
    uvicorn.run("query:app", host="0.0.0.0", port=8002, reload=True)
