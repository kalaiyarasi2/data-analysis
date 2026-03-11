import { useState, useCallback, useMemo } from "react";
import { getUploaderBase, getPgAgentBase, getQueryBase } from "@/lib/settings";

// ── Shared types ─────────────────────────────────────────────────────────────
export interface UploaderTableInfo {
  table_name: string;
  columns: { name: string; type: string }[];
  row_count: number;
  created_at: string;
  database_name: string;
}

export interface PgTableInfo {
  name: string;
  columns: string[];
  row_count: number;
}

export interface UploadResult {
  filename: string;
  table_name: string;
  rows_processed: number;
  columns_processed: number;
  message: string;
  preview_data: Record<string, unknown>[];
  database_created: boolean;
  table_created: boolean;
}

export interface SqlResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  duration_ms?: number;
}

export interface AnalyzeResult {
  query: string;
  answer: string;
  row_count: number;
  data_endpoint: string;
}

export interface TableMeta {
  name: string;
}

// ── Hook ─────────────────────────────────────────────────────────────────────
export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiFetch = useCallback(async <T>(url: string, options?: RequestInit): Promise<T> => {
    const res = await fetch(url, options);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  }, []);

  const wrap = useCallback(<Args extends unknown[], R>(fn: (...args: Args) => Promise<R>) => {
    return async (...args: Args): Promise<R> => {
      setLoading(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (e: any) {
        setError(e.message ?? "Unknown error");
        throw e;
      } finally {
        setLoading(false);
      }
    };
  }, []);

  const uploadFile = useMemo(() => wrap(async (file: File, tableName?: string): Promise<UploadResult> => {
    const form = new FormData();
    form.append("file", file);
    if (tableName) form.append("table_name", tableName);
    return apiFetch<UploadResult>(`${getUploaderBase()}/upload`, { method: "POST", body: form });
  }), [wrap, apiFetch]);

  const getUploaderTables = useMemo(() => wrap(async (): Promise<UploaderTableInfo[]> => {
    return apiFetch<UploaderTableInfo[]>(`${getUploaderBase()}/tables`);
  }), [wrap, apiFetch]);

  const getUploaderTableData = useMemo(() => wrap(async (tableName: string, limit = 100) => {
    return apiFetch<{ table_name: string; data: Record<string, unknown>[]; total_rows: number; columns: string[] }>(
      `${getUploaderBase()}/table/${encodeURIComponent(tableName)}?limit=${limit}`
    );
  }), [wrap, apiFetch]);

  const getPgTables = useMemo(() => wrap(async (): Promise<{ tables: TableMeta[] }> => {
    const res = await apiFetch<{ tables: string[] }>(`${getPgAgentBase()}/api/tables`);
    return { tables: (res.tables || []).map(name => ({ name })) };
  }), [wrap, apiFetch]);

  const getPgTableData = useMemo(() => wrap(async (table: string, limit = 100, offset = 0) => {
    return apiFetch<{ rows: Record<string, unknown>[]; total: number; columns: string[] }>(
      `${getPgAgentBase()}/api/tables/${encodeURIComponent(table)}?limit=${limit}&offset=${offset}`
    );
  }), [wrap, apiFetch]);

  const executeSql = useMemo(() => wrap(async (sql: string): Promise<SqlResult> => {
    return apiFetch<SqlResult>(`${getPgAgentBase()}/api/sql/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: sql }),
    });
  }), [wrap, apiFetch]);

  const askNlq = useMemo(() => wrap(async (query: string, endpoint?: string) => {
    return apiFetch<{ answer: string }>(`${getPgAgentBase()}/api/nlq/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, endpoint }),
    });
  }), [wrap, apiFetch]);

  const checkHealth = useMemo(() => wrap(async () => apiFetch<{ status: string }>(`${getPgAgentBase()}/health`)), [wrap, apiFetch]);
  const getDbInfo = useMemo(() => wrap(async () => apiFetch<{ db_type: string; host: string; database: string }>(`${getPgAgentBase()}/api/info`)), [wrap, apiFetch]);

  const analyzeQuery = useMemo(() => wrap(async (query: string, endpoint?: string): Promise<AnalyzeResult> => {
    return apiFetch<AnalyzeResult>(`${getQueryBase()}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, ...(endpoint ? { endpoint } : {}) }),
    });
  }), [wrap, apiFetch]);

  const getPgViews = useMemo(() => wrap(async (): Promise<{ views: TableMeta[] }> => {
    const res = await apiFetch<{ views: string[] }>(`${getPgAgentBase()}/api/views`);
    return { views: (res.views || []).map(name => ({ name })) };
  }), [wrap, apiFetch]);

  const getPgViewData = useMemo(() => wrap(async (view: string, limit = 100, offset = 0) => {
    return apiFetch<{ rows: Record<string, unknown>[]; total: number; columns: string[] }>(
      `${getPgAgentBase()}/api/views/${encodeURIComponent(view)}?limit=${limit}&offset=${offset}`
    );
  }), [wrap, apiFetch]);

  return useMemo(() => ({
    loading,
    error,
    uploadFile,
    getUploaderTables,
    getUploaderTableData,
    getPgTables,
    getPgTableData,
    getPgViews,
    getPgViewData,
    executeSql,
    askNlq,
    checkHealth,
    getDbInfo,
    analyzeQuery,
  }), [loading, error, uploadFile, getUploaderTables, getUploaderTableData, getPgTables, getPgTableData, getPgViews, getPgViewData, executeSql, askNlq, checkHealth, getDbInfo, analyzeQuery]);
}
