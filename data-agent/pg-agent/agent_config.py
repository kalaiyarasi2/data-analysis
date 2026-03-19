import os
from dotenv import load_dotenv

"""config.py — All settings loaded from environment / .env"""

# Look for .env in current and parent directories
print(f"DEBUG: CWD is {os.getcwd()}")
print(f"DEBUG: Loading .env from {os.path.abspath('.env')}")
load_dotenv(override=True)
parent_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
print(f"DEBUG: Loading .env from {parent_env}")
load_dotenv(parent_env, override=True)
print(f"DEBUG: OPENAI_API_KEY is {'set' if os.getenv('OPENAI_API_KEY') else 'NOT set'}")

# ── Database Configuration ────────────────────────────────────────────────────
DB_TYPE:     str = os.getenv("DB_TYPE",     "postgres")  # postgres | mysql | mssql
DB_HOST:     str = os.getenv("DB_HOST",     os.getenv("PG_HOST", "localhost"))
DB_PORT:     str = os.getenv("DB_PORT",     os.getenv("PG_PORT", "5432"))
DB_DB:       str = os.getenv("DB_NAME",     os.getenv("PG_DB",   "postgres"))
DB_USER:     str = os.getenv("DB_USER",     os.getenv("PG_USER", "postgres"))
DB_PASSWORD: str = os.getenv("DB_PASSWORD", os.getenv("PG_PASSWORD", ""))
DB_SCHEMA:   str = os.getenv("DB_SCHEMA",   os.getenv("PG_SCHEMA", "dbo" if DB_TYPE == "mssql" else "public"))

def get_database_url() -> str:
    import urllib.parse
    pw = urllib.parse.quote_plus(DB_PASSWORD)
    if DB_TYPE == "postgres":
        return f"postgresql+asyncpg://{DB_USER}:{pw}@{DB_HOST}:{DB_PORT}/{DB_DB}"
    elif DB_TYPE == "mysql":
        return f"mysql+aiomysql://{DB_USER}:{pw}@{DB_HOST}:{DB_PORT}/{DB_DB}"
    elif DB_TYPE == "mssql":
        driver = urllib.parse.quote_plus(os.getenv("DB_DRIVER", "SQL Server"))
        return f"mssql+aioodbc://{DB_USER}:{pw}@{DB_HOST}:{DB_PORT}/{DB_DB}?driver={driver}&TrustServerCertificate=yes"
    return f"postgresql+asyncpg://{DB_USER}:{pw}@{DB_HOST}:{DB_PORT}/{DB_DB}"

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
