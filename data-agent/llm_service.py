"""
llm_service.py — Handles all OpenAI API calls for data analysis.
"""

import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS, OPENAI_TEMPERATURE

client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = """You are DataMind, a precise AI data analysis agent.
You are given a dataset fetched live from an API endpoint.
Your job is to answer the user's natural-language question by carefully analyzing the exact data provided.

STRICT RULES:
1. Never hallucinate or invent data values — only reference what is actually in the dataset.
2. If the user asks for records matching a condition (e.g. field = NA, null, a specific string, a number range),
   find EVERY single matching record — do not miss any.
3. NA, null, None, empty string, "N/A", "na", "n/a" are all considered "missing" values.
4. Be precise with counts and names.
5. Respond ONLY with a valid JSON object — no markdown fences, no extra text outside the JSON.

Response JSON schema:
{
  "answer": "<clear natural language answer summarising the finding>",
  "highlight_indices": [0, 3, 7],        // 0-based row indices that match the query ([] if not applicable)
  "result_type": "list" | "stat" | "text",
  "result_items": [                       // for result_type=list: matching records
    { "label": "<identifier or name>", "detail": "<relevant field = value>" }
  ],
  "stats": {                              // for result_type=stat: aggregate numbers
    "Label": value
  }
}
"""


def build_user_prompt(question: str, data: list[dict], schema_summary: str, total_rows: int) -> str:
    data_json = json.dumps(data, indent=1, default=str)
    return f"""Dataset info:
- Total rows in endpoint: {total_rows}
- Rows provided for analysis: {len(data)}
- Schema:
{schema_summary}

Data:
{data_json}

Question: {question}"""


def analyze(question: str, data: list[dict], schema_summary: str, total_rows: int) -> dict:
    """
    Send the question + data to OpenAI and return the structured JSON response.
    """
    prompt = build_user_prompt(question, data, schema_summary, total_rows)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=OPENAI_MAX_TOKENS,
        temperature=OPENAI_TEMPERATURE,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},   # enforces JSON output (GPT-4o / GPT-4-turbo)
    )

    raw = response.choices[0].message.content or "{}"

    # Extra safety: strip accidental markdown fences
    raw = re.sub(r"```json|```", "", raw).strip()

    result = json.loads(raw)
    result["model_used"]    = OPENAI_MODEL
    result["prompt_tokens"] = response.usage.prompt_tokens
    result["reply_tokens"]  = response.usage.completion_tokens
    return result


def generate_suggestions(schema_summary: str, sample_row: dict) -> list[str]:
    """
    Ask OpenAI to auto-generate 5 smart questions for the loaded dataset.
    """
    prompt = f"""Given this dataset schema and a sample row, generate exactly 5 useful natural-language 
questions a data analyst would ask. Return ONLY a JSON array of 5 strings.

Schema:
{schema_summary}

Sample row:
{json.dumps(sample_row, default=str)}
"""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=300,
        temperature=0.5,
        messages=[
            {"role": "system", "content": "You generate smart data analysis questions. Respond only with a JSON array of strings."},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or '{"questions":[]}'
    parsed = json.loads(raw)
    # handle {"questions": [...]} or direct array wrapped in an object
    if isinstance(parsed, list):
        return parsed[:5]
    for v in parsed.values():
        if isinstance(v, list):
            return v[:5]
    return []
