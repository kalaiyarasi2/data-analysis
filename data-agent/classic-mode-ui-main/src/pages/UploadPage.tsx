import { useState, useRef } from "react";
import { Upload, FileSpreadsheet, CheckCircle, AlertCircle, X } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { useApi } from "@/hooks/useApi";
import { loadSettings, saveSettings, AppSettings } from "@/lib/settings";

export default function UploadPage() {
  const { uploadFile, loading } = useApi();

  const [file, setFile] = useState<File | null>(null);
  const [tableName, setTableName] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{
    filename: string;
    table_name: string;
    rows_processed: number;
    columns_processed: number;
    message: string;
    preview_data: Record<string, unknown>[];
    database_created: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.name.endsWith(".xlsx") || dropped.name.endsWith(".xls"))) {
      setFile(dropped);
      setError(null);
      setResult(null);
    } else {
      setError("Please upload an Excel (.xlsx or .xls) file.");
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setProgress(0);
    setError(null);
    setResult(null);

    // Animate progress while waiting
    const ticker = setInterval(() => {
      setProgress((p) => (p >= 85 ? 85 : p + 12));
    }, 250);

    try {
      const data = await uploadFile(file, tableName || undefined);
      clearInterval(ticker);
      setProgress(100);
      setResult(data);

      // Sync to settings
      const currentSettings = loadSettings() || {};
      const updatedSettings: AppSettings = {
        host: "localhost",
        port: "5432",
        database: "insurance",
        username: "postgres",
        password: "",
        apiBase: "http://localhost:8000",
        uploaderApiUrl: "http://localhost:8000",
        pgAgentApiUrl: "http://localhost:8001",
        queryAgentApiUrl: "http://localhost:8002",
        llmDataBaseUrl: "http://localhost:8001",
        llmDataPathPrefix: "/api/tables/",
        llmDataResourceName: data.table_name,
        autoRefresh: true,
        ...currentSettings,
        llmDataResourceName: data.table_name,
      };
      saveSettings(updatedSettings);
    } catch (e: any) {
      clearInterval(ticker);
      setProgress(0);
      setError(e.message || "Upload failed");
    }
  };

  const reset = () => {
    setFile(null);
    setTableName("");
    setProgress(0);
    setResult(null);
    setError(null);
  };

  // Derive column keys from first preview row
  const previewCols = result?.preview_data?.[0] ? Object.keys(result.preview_data[0]) : [];

  return (
    <div className="animate-fade-in max-w-2xl">
      <PageHeader title="Upload Data" description="Upload Excel files to automatically create PostgreSQL database tables." />

      {/* Drop Zone */}
      <div
        className={cn(
          "glass-panel rounded-lg p-10 text-center cursor-pointer transition-all",
          dragOver && "border-primary border-2 bg-primary/5",
          file && "border-success/40"
        )}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) { setFile(f); setError(null); setResult(null); }
          }}
        />
        {file ? (
          <div className="flex items-center justify-center gap-3">
            <FileSpreadsheet className="w-10 h-10 text-success" />
            <div className="text-left">
              <p className="font-medium text-foreground">{file.name}</p>
              <p className="text-sm text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
            <button onClick={(e) => { e.stopPropagation(); reset(); }} className="ml-4 text-muted-foreground hover:text-foreground">
              <X className="w-5 h-5" />
            </button>
          </div>
        ) : (
          <>
            <Upload className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
            <p className="font-medium text-foreground mb-1">Drop your file here or click to browse</p>
            <p className="text-sm text-muted-foreground">Supports .xlsx and .xls files</p>
          </>
        )}
      </div>

      {/* Table Name + Upload Button */}
      {file && !result && (
        <div className="mt-6 space-y-4 animate-fade-in">
          <div>
            <Label htmlFor="tableName">Table Name (optional)</Label>
            <Input
              id="tableName"
              placeholder="Auto-generated from filename"
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              className="mt-1"
            />
          </div>
          {loading && <Progress value={progress} className="h-2" />}
          <Button onClick={handleUpload} disabled={loading} className="w-full">
            {loading ? "Uploading…" : "Upload & Create Table"}
          </Button>
        </div>
      )}

      {/* Success Result */}
      {result && (
        <div className="mt-6 glass-panel rounded-lg p-6 border-success/40 animate-fade-in space-y-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-success" />
            <h3 className="font-display font-semibold text-foreground">Upload Successful</h3>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><span className="text-muted-foreground">Table:</span> <span className="font-medium text-foreground font-mono">{result.table_name}</span></div>
            <div><span className="text-muted-foreground">Rows:</span> <span className="font-medium text-foreground">{result.rows_processed.toLocaleString()}</span></div>
            <div><span className="text-muted-foreground">Columns:</span> <span className="font-medium text-foreground">{result.columns_processed}</span></div>
            <div><span className="text-muted-foreground">DB Created:</span> <span className="font-medium text-foreground">{result.database_created ? "Yes" : "Existing"}</span></div>
          </div>
          <p className="text-xs text-muted-foreground">{result.message}</p>

          {/* Preview table */}
          {result.preview_data && result.preview_data.length > 0 && (
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    {previewCols.map((col) => (
                      <th key={col} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.preview_data.map((row, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-muted/30">
                      {previewCols.map((col) => (
                        <td key={col} className="px-3 py-2 text-foreground whitespace-nowrap">
                          {String(row[col] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <Button variant="outline" onClick={reset}>Upload Another File</Button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-6 glass-panel rounded-lg p-4 border-destructive/40 animate-fade-in flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-destructive shrink-0" />
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}
    </div>
  );
}
