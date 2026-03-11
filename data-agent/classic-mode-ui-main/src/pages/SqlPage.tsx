import { useState } from "react";
import { Play, Copy, Download, AlertCircle, Clock, Loader2 } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { useApi, SqlResult } from "@/hooks/useApi";

const DEFAULT_QUERIES = [
  "SELECT * FROM information_schema.tables WHERE table_schema = 'public' LIMIT 20",
  "SELECT table_name, pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS size FROM information_schema.tables WHERE table_schema = 'public'",
];

export default function SqlPage() {
  const { executeSql, loading } = useApi();

  const [sql, setSql] = useState("SELECT * FROM information_schema.tables WHERE table_schema = 'public' LIMIT 10;");
  const [result, setResult] = useState<SqlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>(DEFAULT_QUERIES);
  const [durationMs, setDurationMs] = useState<number | null>(null);

  const execute = async () => {
    if (!sql.trim()) return;
    setError(null);
    setResult(null);
    setDurationMs(null);
    const start = performance.now();

    try {
      const data = await executeSql(sql.trim());
      setDurationMs(Math.round(performance.now() - start));
      setResult(data);
      // Add to history (deduplicate)
      setHistory((prev) => [sql.trim(), ...prev.filter((q) => q !== sql.trim())].slice(0, 20));
    } catch (e: any) {
      setDurationMs(Math.round(performance.now() - start));
      setError(e.message || "Query failed");
    }
  };

  const copyResult = () => {
    if (!result) return;
    const csv = [
      result.columns.join(","),
      ...result.rows.map((r) => result.columns.map((c) => `"${String(r[c] ?? "").replace(/"/g, '""')}"`).join(",")),
    ].join("\n");
    navigator.clipboard.writeText(csv);
  };

  const downloadResult = () => {
    if (!result) return;
    const csv = [
      result.columns.join(","),
      ...result.rows.map((r) => result.columns.map((c) => `"${String(r[c] ?? "").replace(/"/g, '""')}"`).join(",")),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "query_result.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="animate-fade-in">
      <PageHeader title="SQL Query" description="Execute raw SQL queries against your PostgreSQL database." />

      <div className="flex gap-6">
        <div className="flex-1 space-y-4">
          {/* Editor */}
          <div className="glass-panel rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
              <span className="text-xs font-mono text-muted-foreground">SQL Editor</span>
              <Button size="sm" onClick={execute} disabled={loading}>
                {loading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Play className="w-4 h-4 mr-1" />}
                {loading ? "Running…" : "Execute"}
              </Button>
            </div>
            <Textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              className="font-mono text-sm border-0 rounded-none min-h-[180px] resize-y focus-visible:ring-0"
              placeholder="Enter your SQL query…"
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "Enter") execute();
              }}
            />
          </div>

          {/* Error */}
          {error && (
            <div className="glass-panel rounded-lg p-4 border-destructive/40 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
              <p className="text-sm text-destructive font-mono whitespace-pre-wrap">{error}</p>
            </div>
          )}

          {/* Results */}
          {result && (
            <div className="glass-panel rounded-lg overflow-hidden animate-fade-in">
              <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
                <span className="text-xs text-muted-foreground">
                  {result.row_count ?? result.rows.length} rows
                  {durationMs !== null ? ` · ${durationMs}ms` : ""}
                </span>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm" onClick={copyResult} title="Copy as CSV">
                    <Copy className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={downloadResult} title="Download CSV">
                    <Download className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm font-mono">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      {result.columns.map((col) => (
                        <th key={col} className="px-4 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr key={i} className="border-b border-border/50 hover:bg-muted/30">
                        {result.columns.map((col) => (
                          <td key={col} className="px-4 py-2 text-foreground whitespace-nowrap">
                            {String(row[col] ?? "NULL")}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {result.rows.length === 0 && (
                      <tr>
                        <td colSpan={result.columns.length || 1} className="px-4 py-6 text-center text-muted-foreground">
                          Query returned 0 rows.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* History Sidebar */}
        <div className="w-56 shrink-0">
          <div className="glass-panel rounded-lg p-4">
            <h3 className="font-display font-semibold text-sm text-foreground mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4" /> History
            </h3>
            <div className="space-y-2">
              {history.map((q, i) => (
                <button
                  key={i}
                  onClick={() => setSql(q)}
                  className="w-full text-left px-2 py-1.5 rounded text-xs font-mono text-muted-foreground hover:bg-muted hover:text-foreground transition-colors truncate"
                  title={q}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
