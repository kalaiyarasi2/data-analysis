# PG-Agent API Reference

**Base URL:** `http://10.10.8.206:8001`

---

## Quick Start for External Integration

### 1. Chatbot-Friendly Endpoint (Recommended)

**Endpoint:** `POST /ask`

**Request:**
```bash
curl -X POST http://10.10.8.206:8001/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many open claims are there for 2024?",
    "limit": 100
  }'
```

**Response:**
```json
{
  "question": "How many open claims are there for 2024?",
  "answer": "Found 1 result(s). The data shows: {'OpenClaimsCount': 0}",
  "generated_sql": "SELECT TOP 100 COUNT(*) AS [OpenClaimsCount]...",
  "session_id": "c4b0e7f3c8c64f3f8c2e3a8c7a1b2c3d",
  "messages": [
    {
      "role": "user",
      "content": "How many open claims are there for 2024?"
    },
    {
      "role": "assistant",
      "content": "Found 1 result(s). The data shows: {'OpenClaimsCount': 0}"
    }
  ]
}
```

---

### 1b. Follow-up Turn (reuse `session_id` / send `messages`)

```bash
curl -X POST http://10.10.8.206:8001/ask \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "c4b0e7f3c8c64f3f8c2e3a8c7a1b2c3d",
    "question": "Now do the same but only for 2025.",
    "limit": 100,
    "messages": [
      {
        "role": "user",
        "content": "How many open claims are there for 2024?"
      },
      {
        "role": "assistant",
        "content": "Found 1 result(s). The data shows: {'OpenClaimsCount': 0}"
      }
    ]
  }'
```

---

### 2. Technical Endpoint (Full Data)

**Endpoint:** `POST /api/nlq/ask`

**Request:**
```bash
curl -X POST http://10.10.8.206:8001/api/nlq/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many open claims are there for 2024?",
    "limit": 100
  }'
```

**Response:**
```json
{
  "question": "How many open claims are there for 2024?",
  "generated_sql": "SELECT TOP 100 COUNT(*) AS [OpenClaimsCount]...",
  "row_count": 1,
  "columns": ["OpenClaimsCount"],
  "rows": [{"OpenClaimsCount": 0}],
  "model": "gpt-4o",
  "prompt_tokens": 1728,
  "reply_tokens": 39
}
```

---

## API Documentation

### Interactive Docs
- **Swagger UI:** http://10.10.8.206:8001/api/docs
- **ReDoc:** http://10.10.8.206:8001/api/redoc
- **OpenAPI JSON:** http://10.10.8.206:8001/api/openapi.json

---

## Response Format Comparison

| Feature | `/ask` | `/api/nlq/ask` |
|---------|--------|----------------|
| **To Use** | External tools, chatbots | Detailed analysis |
| **Response Type** | Simplified | Full technical |
| **Includes** | Q&A + SQL | Q&A + SQL + data + tokens |
| **Use Case** | Quick integration | Data science, debugging |

---

## Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `question` | string | ✅ Yes | — | Natural language question about the database |
| `limit` | integer | ❌ No | 100 | Max rows to return |
| `session_id` | string | ❌ No | — | Per-chat identifier (returned by the server) |
| `messages` | array | ❌ No | — | Chat history: `[{ "role": "user"|"assistant", "content": "..." }]` |

---

## Error Responses

| Code | Meaning | Example |
|------|---------|---------|
| `200` | Success | Question answered |
| `400` | Bad request | Invalid SQL generation or execution error |
| `422` | Validation error | Empty question parameter |
| `503` | Service unavailable | OpenAI API key not configured |

---

## Example Use Cases

**Question:** "What is the average claim amount by department?"
```json
{
  "question": "What is the average claim amount by department?",
  "limit": 50
}
```

**Question:** "Show me all employees in Engineering with salary > 100000"
```json
{
  "question": "Show me all employees in Engineering with salary > 100000",
  "limit": 100
}
```

---

## Support

For issues or questions, check:
- Swagger docs: http://10.10.8.206:8001/api/docs
- Error messages in the response body
- Server logs for detailed debugging
