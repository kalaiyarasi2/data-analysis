"""config.py — All settings loaded from environment / .env"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Database Configuration ────────────────────────────────────────────────────
DB_TYPE:     str = os.getenv("DB_TYPE",     "postgres")  # postgres | mysql | mssql
DB_HOST:     str = os.getenv("DB_HOST",     os.getenv("PG_HOST", "localhost"))
DB_PORT:     str = os.getenv("DB_PORT",     os.getenv("PG_PORT", "5432"))
DB_DB:       str = os.getenv("DB_NAME",     os.getenv("PG_DB",   "postgres"))
DB_USER:     str = os.getenv("DB_USER",     os.getenv("PG_USER", "postgres"))
DB_PASSWORD: str = os.getenv("DB_PASSWORD", os.getenv("PG_PASSWORD", ""))
DB_SCHEMA:   str = os.getenv("DB_SCHEMA",   os.getenv("PG_SCHEMA", "public"))

def get_database_url() -> str:
    import urllib.parse
    if DB_TYPE == "postgres":
        pw = urllib.parse.quote_plus(DB_PASSWORD)
        return f"postgresql+asyncpg://{DB_USER}:{pw}@{DB_HOST}:{DB_PORT}/{DB_DB}"
    elif DB_TYPE == "mysql":
        pw = urllib.parse.quote_plus(DB_PASSWORD)
        return f"mysql+aiomysql://{DB_USER}:{pw}@{DB_HOST}:{DB_PORT}/{DB_DB}"
    elif DB_TYPE == "mssql":
        # Requires ODBC Driver for SQL Server
        driver = urllib.parse.quote_plus(os.getenv("DB_DRIVER", "SQL Server"))
        pw = urllib.parse.quote_plus(DB_PASSWORD)
        # For SQL Server, some drivers prefer commas for port in SERVER or just host in URL
        # We'll use the standard URL format but add TrustServerCertificate for better compatibility
        return f"mssql+aioodbc://{DB_USER}:{pw}@{DB_HOST}:{DB_PORT}/{DB_DB}?driver={driver}&TrustServerCertificate=yes"
    return f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DB}"

DATABASE_URL: str = os.getenv("DATABASE_URL", get_database_url())
PG_SCHEMA: str = DB_SCHEMA

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY:   str   = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL:     str   = os.getenv("OPENAI_MODEL",   "gpt-4o")
OPENAI_MAX_TOKENS: int  = int(os.getenv("OPENAI_MAX_TOKENS", "1500"))

# ── API behaviour ─────────────────────────────────────────────────────────────
DEFAULT_LIMIT:  int  = int(os.getenv("DEFAULT_LIMIT",  "100"))   # rows per page default
MAX_LIMIT:      int  = int(os.getenv("MAX_LIMIT",      "1000"))  # hard cap
ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ── Server ────────────────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
