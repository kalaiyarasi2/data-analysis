"""
CLI script to directly query the Data Analysis Agent.
Run: python query_agent.py "Which employees have closed claims?"
"""
import asyncio
import sys
import httpx
import json


AGENT_URL = "http://localhost:8002/analyze"


async def ask(query: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        print(f"\n🔍 Query: {query}")
        print("⏳ Fetching data and analyzing...\n")
        resp = await client.post(AGENT_URL, json={"query": query})
        resp.raise_for_status()
        result = resp.json()

        print(f"📊 Data rows analyzed: {result['row_count']}")
        print(f"✅ Answer:\n{result['answer']}")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List all employees and their claim status"
    asyncio.run(ask(query))