import { useState, useEffect, useCallback } from "react";
import { Table2, Search, ChevronLeft, ChevronRight, Eye, RefreshCw, Loader2 } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useApi } from "@/hooks/useApi";

interface TableMeta {
  name: string;
  row_count?: number;
  columns?: string[];
}

const PAGE_SIZE = 50;

export default function TablesPage() {
  const { getPgTables, getPgTableData, loading } = useApi();

  const [tables, setTables] = useState<TableMeta[]>([]);
  const [tablesError, setTablesError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const [selected, setSelected] = useState<TableMeta | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const [rowsLoading, setRowsLoading] = useState(false);

  const fetchTables = useCallback(async () => {
    setTablesError(null);
    try {
      const res = await getPgTables();
      setTables(res.tables ?? []);
    } catch (e: any) {
      setTablesError(e.message ?? "Failed to load tables");
    }
  }, []);

  useEffect(() => { fetchTables(); }, []);

  const loadTableData = useCallback(async (tableName: string, pg: number) => {
    setRowsError(null);
    setRowsLoading(true);
    try {
      const offset = (pg - 1) * PAGE_SIZE;
      const res = await getPgTableData(tableName, PAGE_SIZE, offset);
      setRows(res.rows ?? []);
      setColumns(res.columns ?? (res.rows?.[0] ? Object.keys(res.rows[0]) : []));
      setTotal(res.total ?? 0);
    } catch (e: any) {
      setRowsError(e.message ?? "Failed to load table data");
      setRows([]);
    } finally {
      setRowsLoading(false);
    }
  }, []);

  const selectTable = (t: TableMeta) => {
    setSelected(t);
    setPage(1);
    setRows([]);
    setColumns([]);
    loadTableData(t.name, 1);
  };

  const changePage = (newPage: number) => {
    if (!selected) return;
    setPage(newPage);
    loadTableData(selected.name, newPage);
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = tables.filter((t) => t.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Tables"
        description="Browse and inspect your database tables."
        actions={
          <Button variant="outline" size="sm" onClick={fetchTables} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            Refresh
          </Button>
        }
      />

      {tablesError && (
        <div className="mb-4 glass-panel rounded-lg p-3 border-destructive/40 text-sm text-destructive">
          {tablesError}
        </div>
      )}

      <div className="flex gap-6">
        {/* Table List */}
        <div className="w-64 shrink-0 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input placeholder="Search tables..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
          </div>
          <div className="space-y-1">
            {loading && tables.length === 0 && (
              <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading…
              </div>
            )}
            {filtered.map((t) => (
              <button
                key={t.name}
                onClick={() => selectTable(t)}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2.5 rounded-md text-sm text-left transition-colors",
                  selected?.name === t.name
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-foreground hover:bg-muted"
                )}
              >
                <Table2 className="w-4 h-4 shrink-0" />
                <span className="truncate flex-1">{t.name}</span>
                {t.row_count !== undefined && (
                  <span className="text-xs text-muted-foreground">{t.row_count}</span>
                )}
              </button>
            ))}
            {!loading && filtered.length === 0 && (
              <p className="text-sm text-muted-foreground px-3 py-2">
                {tables.length === 0 ? "No tables found. Check database connection." : "No tables match your search."}
              </p>
            )}
          </div>
        </div>

        {/* Table Data */}
        <div className="flex-1 min-w-0">
          {selected ? (
            <div className="glass-panel rounded-lg overflow-hidden">
              <div className="p-4 border-b border-border flex items-center justify-between">
                <div>
                  <h3 className="font-display font-semibold text-foreground">{selected.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    {total.toLocaleString()} rows · {columns.length} columns
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1 || rowsLoading} onClick={() => changePage(page - 1)}>
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    {page} / {totalPages}
                  </span>
                  <Button variant="outline" size="sm" disabled={page >= totalPages || rowsLoading} onClick={() => changePage(page + 1)}>
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {rowsError && (
                <div className="p-4 text-sm text-destructive">{rowsError}</div>
              )}

              {rowsLoading ? (
                <div className="p-8 flex items-center justify-center text-muted-foreground gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" /> Loading rows…
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/50">
                        {columns.map((col) => (
                          <th key={col} className="px-4 py-2.5 text-left font-medium text-muted-foreground whitespace-nowrap">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr key={i} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                          {columns.map((col) => (
                            <td key={col} className="px-4 py-2.5 text-foreground whitespace-nowrap">
                              {String(row[col] ?? "")}
                            </td>
                          ))}
                        </tr>
                      ))}
                      {rows.length === 0 && !rowsLoading && (
                        <tr>
                          <td colSpan={columns.length || 1} className="px-4 py-6 text-center text-muted-foreground text-sm">
                            No rows returned.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="glass-panel rounded-lg p-12 text-center">
              <Eye className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">Select a table to view its data.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
