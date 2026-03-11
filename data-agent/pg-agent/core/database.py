"""
core/database.py
Async PostgreSQL connection via SQLAlchemy 2.x + asyncpg.
Provides a singleton `db` object used by all routes.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from agent_config import DATABASE_URL, PG_SCHEMA, DB_TYPE


class Database:
    """Thin wrapper around an async SQLAlchemy engine."""

    def __init__(self, url: str):
        self._url = url
        self._engine: AsyncEngine | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def connect(self):
        self._engine = create_async_engine(
            self._url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )

    async def disconnect(self):
        if self._engine:
            await self._engine.dispose()

    # ── Raw execute ───────────────────────────────────────────────────────────
    async def fetch_all(self, sql: str, params: dict | None = None) -> list[dict]:
        async with self._engine.connect() as conn:
            result = await conn.execute(text(sql), params or {})
            keys = list(result.keys())
            return [dict(zip(keys, row)) for row in result.fetchall()]

    async def fetch_one(self, sql: str, params: dict | None = None) -> dict | None:
        rows = await self.fetch_all(sql, params)
        return rows[0] if rows else None

    async def execute(self, sql: str, params: dict | None = None) -> int:
        """Execute DML; returns rowcount."""
        async with self._engine.begin() as conn:
            result = await conn.execute(text(sql), params or {})
            return result.rowcount

    # ── Schema introspection ──────────────────────────────────────────────────
    async def list_tables(self, schema: str = PG_SCHEMA) -> list[str]:
        if DB_TYPE == "mysql":
            sql = "SHOW TABLES"
            rows = await self.fetch_all(sql)
            return [list(r.values())[0] for r in rows]
        elif DB_TYPE == "mssql":
            sql = "SELECT name FROM sys.tables WHERE schema_id = SCHEMA_ID(:schema)"
            rows = await self.fetch_all(sql, {"schema": schema})
            return [r["name"] for r in rows]
        else: # postgres
            sql = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """
            rows = await self.fetch_all(sql, {"schema": schema})
            return [r["table_name"] for r in rows]

    async def table_columns(self, table: str, schema: str = PG_SCHEMA) -> list[dict]:
        if DB_TYPE == "mysql":
            sql = f"DESCRIBE `{table}`" # MySQL doesn't traditionally use schema in DESCRIBE if connected to DB
            rows = await self.fetch_all(sql)
            return [
                {
                    "column_name": r["Field"],
                    "data_type": r["Type"],
                    "is_nullable": r["Null"],
                    "column_default": r["Default"],
                }
                for r in rows
            ]
        elif DB_TYPE == "mssql":
            sql = """
                SELECT 
                    c.name AS column_name,
                    t.name AS data_type,
                    c.is_nullable,
                    d.definition AS column_default,
                    c.max_length AS character_maximum_length
                FROM sys.columns c
                JOIN sys.types t ON c.user_type_id = t.user_type_id
                LEFT JOIN sys.default_constraints d ON c.default_object_id = d.object_id
                WHERE c.object_id = OBJECT_ID(:table_path)
            """
            rows = await self.fetch_all(sql, {"table_path": f"{schema}.{table}"})
            return rows
        else: # postgres
            sql = """
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name   = :table
                ORDER BY ordinal_position
            """
            return await self.fetch_all(sql, {"schema": schema, "table": table})

    async def primary_keys(self, table: str, schema: str = PG_SCHEMA) -> list[str]:
        if DB_TYPE == "mysql":
            sql = f"SHOW KEYS FROM `{table}` WHERE Key_name = 'PRIMARY'"
            rows = await self.fetch_all(sql)
            return [r["Column_name"] for r in rows]
        elif DB_TYPE == "mssql":
            sql = """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + CONSTRAINT_NAME), 'IsPrimaryKey') = 1
                AND TABLE_NAME = :table AND TABLE_SCHEMA = :schema
            """
            rows = await self.fetch_all(sql, {"table": table, "schema": schema})
            return [r["COLUMN_NAME"] for r in rows]
        else: # postgres
            sql = """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema    = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = :schema
                  AND tc.table_name   = :table
                ORDER BY kcu.ordinal_position
            """
            rows = await self.fetch_all(sql, {"schema": schema, "table": table})
            return [r["column_name"] for r in rows]

    async def full_schema(self, schema: str = PG_SCHEMA) -> dict[str, list[dict]]:
        """Return {table: [column_info, ...]} for all tables in schema."""
        tables = await self.list_tables(schema)
        result = {}
        for t in tables:
            result[t] = await self.table_columns(t, schema)
        return result

    # ── Safety & Dialect Helpers ──────────────────────────────────────────────
    @staticmethod
    def safe_identifier(name: str) -> str:
        """Validate a table/column name to prevent SQL injection (allowing hyphens)."""
        if not re.match(r'^[A-Za-z0-9_\-]+$', name):
            raise ValueError(f"Invalid identifier: {name!r}")
        return name

    @staticmethod
    def quote_identifier(name: str) -> str:
        """Wrap identifier in dialect-specific quotes."""
        Database.safe_identifier(name)
        if DB_TYPE == "mysql":
            return f"`{name}`"
        elif DB_TYPE == "mssql":
            return f"[{name}]"
        else: # postgres
            return f'"{name}"'

    async def insert_row(self, table: str, schema: str, data: dict):
        """Dialect-aware row insertion."""
        q_table = self.quote_identifier(table)
        q_schema = self.quote_identifier(schema)
        cols = [self.quote_identifier(k) for k in data.keys()]
        placeholders = [f":{k}" for k in data.keys()]
        
        sql = f"INSERT INTO {q_schema}.{q_table} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
        return await self.execute(sql, data)

    async def update_row(self, table: str, schema: str, pk_col: str, pk_val: Any, data: dict):
        """Dialect-aware row update."""
        q_table = self.quote_identifier(table)
        q_schema = self.quote_identifier(schema)
        q_pk = self.quote_identifier(pk_col)
        
        set_parts = [f"{self.quote_identifier(k)} = :{k}" for k in data.keys()]
        params = {**data, "__pk_val": pk_val}
        
        sql = f"UPDATE {q_schema}.{q_table} SET {', '.join(set_parts)} WHERE {q_pk} = :__pk_val"
        return await self.execute(sql, params)

    async def delete_row(self, table: str, schema: str, pk_col: str, pk_val: Any):
        """Dialect-aware row deletion."""
        q_table = self.quote_identifier(table)
        q_schema = self.quote_identifier(schema)
        q_pk = self.quote_identifier(pk_col)
        
        sql = f"DELETE FROM {q_schema}.{q_table} WHERE {q_pk} = :pk_val"
        return await self.execute(sql, {"pk_val": pk_val})

    @classmethod
    def build_select_sql(
        cls,
        table: str,
        schema: str = PG_SCHEMA,
        columns: list[str] | str = "*",
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str = "ASC",
        filter_col: str | None = None,
    ) -> str:
        q_schema = cls.quote_identifier(schema)
        q_table = cls.quote_identifier(table)
        
        if isinstance(columns, list):
            col_sql = ", ".join(cls.quote_identifier(c) for c in columns)
        else:
            col_sql = columns

        if DB_TYPE == "mssql":
            if limit is not None and (offset is None or offset == 0):
                # Use TOP for the first page as it's more compatible
                sql = f"SELECT TOP {limit} {col_sql} FROM {q_schema}.{q_table}"
                if filter_col:
                    sql += f" WHERE {cls.quote_identifier(filter_col)} = :filter_val"
                if sort_by:
                    sql += f" ORDER BY {cls.quote_identifier(sort_by)} {sort_order.upper()}"
                return sql
            
            # Use OFFSET/FETCH for subsequent pages
            off = offset or 0
            fetch = f" FETCH NEXT {limit} ROWS ONLY" if limit is not None else ""
            
            sql = f"SELECT {col_sql} FROM {q_schema}.{q_table}"
            if filter_col:
                sql += f" WHERE {cls.quote_identifier(filter_col)} = :filter_val"
            
            if sort_by:
                sql += f" ORDER BY {cls.quote_identifier(sort_by)} {sort_order.upper()}"
            else:
                sql += " ORDER BY (SELECT NULL)"
            
            sql += f" OFFSET {off} ROWS{fetch}"
            return sql

        # Postgres / MySQL
        sql = f"SELECT {col_sql} FROM {q_schema}.{q_table}"
        if filter_col:
            sql += f" WHERE {cls.quote_identifier(filter_col)} = :filter_val"
        if sort_by:
            sql += f" ORDER BY {cls.quote_identifier(sort_by)} {sort_order.upper()}"
        
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"
        
        return sql


db = Database(DATABASE_URL)
