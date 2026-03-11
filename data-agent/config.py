"""
config.py — Central configuration loaded from environment variables.
Copy .env.example to .env and fill in your values.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str  = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str    = os.getenv("OPENAI_MODEL", "gpt-4o")          # or gpt-4-turbo / gpt-3.5-turbo
OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "1500"))
OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0"))

# ── Data limits ───────────────────────────────────────────────────────────────
MAX_ROWS_FETCH: int  = int(os.getenv("MAX_ROWS_FETCH", "500"))   # max rows fetched from endpoint
MAX_ROWS_LLM: int    = int(os.getenv("MAX_ROWS_LLM", "100"))     # max rows sent to LLM per query

# ── CORS / Server ─────────────────────────────────────────────────────────────
ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "*").split(",")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# ── Validate ──────────────────────────────────────────────────────────────────
def validate_config():
    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )
