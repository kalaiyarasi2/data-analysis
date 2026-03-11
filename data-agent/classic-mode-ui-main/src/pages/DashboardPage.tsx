import { useEffect, useState } from "react";
import { Database, Table2, HardDrive, Activity, Upload, Clock, Loader2 } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";

interface DashStats {
  tableCount: number | null;
  status: "checking" | "online" | "offline";
  dbInfo: { db_type: string; host: string; database: string } | null;
}

export default function DashboardPage() {
  const { getPgTables, checkHealth, getDbInfo } = useApi();
  const [stats, setStats] = useState<DashStats>({
    tableCount: null,
    status: "checking",
    dbInfo: null
  });

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const [tablesRes, dbRes] = await Promise.all([
          getPgTables().catch(() => ({ tables: null })),
          getDbInfo().catch(() => null),
          checkHealth().catch(() => null),
        ]);
        if (!mounted) return;
        setStats({
          tableCount: tablesRes.tables ? tablesRes.tables.length : null,
          status: "online",
          dbInfo: dbRes,
        });
      } catch {
        if (mounted) setStats({ tableCount: null, status: "offline", dbInfo: null });
      }
    })();

    return () => { mounted = false; };
  }, []);

  const tableCountLabel =
    stats.tableCount === null
      ? stats.status === "checking"
        ? "…"
        : "—"
      : String(stats.tableCount);

  const dbTypeLabel = stats.dbInfo?.db_type
    ? stats.dbInfo.db_type.charAt(0).toUpperCase() + stats.dbInfo.db_type.slice(1)
    : "Database";

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Dashboard"
        description={`Monitor your ${dbTypeLabel} and manage data pipelines.`}
        actions={
          <Link to="/upload">
            <Button>
              <Upload className="w-4 h-4 mr-2" />
              Upload Data
            </Button>
          </Link>
        }
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<Database className="w-5 h-5" />}
          label="Database"
          value={stats.dbInfo?.database || "—"}
          variant="primary"
        />
        <StatCard
          icon={
            stats.status === "checking" ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Table2 className="w-5 h-5" />
            )
          }
          label="Tables"
          value={tableCountLabel}
          variant="info"
        />
        <StatCard
          icon={<HardDrive className="w-5 h-5" />}
          label="Host"
          value={stats.dbInfo?.host || "—"}
          variant="success"
        />
        <StatCard
          icon={<Activity className="w-5 h-5" />}
          label="Status"
          value={stats.status === "checking" ? "Checking…" : stats.status === "online" ? "Online" : "Offline"}
          variant={stats.status === "online" ? "success" : stats.status === "checking" ? "info" : "primary"}
          trend={stats.status === "online" ? "pg-agent connected" : undefined}
        />
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Link to="/upload" className="glass-panel rounded-lg p-6 hover:border-primary/40 transition-colors group">
          <Upload className="w-8 h-8 text-primary mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="font-display font-semibold text-foreground mb-1">Upload Excel</h3>
          <p className="text-sm text-muted-foreground">Upload Excel files and auto-create database tables.</p>
        </Link>
        <Link to="/sql" className="glass-panel rounded-lg p-6 hover:border-primary/40 transition-colors group">
          <Activity className="w-8 h-8 text-info mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="font-display font-semibold text-foreground mb-1">Run SQL</h3>
          <p className="text-sm text-muted-foreground">Execute custom SQL queries against your database.</p>
        </Link>
        <Link to="/ask" className="glass-panel rounded-lg p-6 hover:border-primary/40 transition-colors group">
          <Activity className="w-8 h-8 text-accent mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="font-display font-semibold text-foreground mb-1">AI Assistant</h3>
          <p className="text-sm text-muted-foreground">Ask questions in plain English about your data.</p>
        </Link>
      </div>

      {/* Getting Started */}
      <div className="glass-panel rounded-lg p-6">
        <h2 className="font-display text-xl font-semibold text-foreground mb-4">Getting Started</h2>
        <div className="space-y-3">
          {[
            { action: "Step 1", detail: "Start enhanced_data_uploader.py on port 8000", link: "/upload" },
            { action: "Step 2", detail: "Start pg-agent/main.py on port 8001", link: "/tables" },
            { action: "Step 3", detail: "Start query.py on port 8002", link: "/ask" },
            { action: "Step 4", detail: "Upload an Excel file to create a database table", link: "/upload" },
            { action: "Step 5", detail: "Browse tables or run SQL queries", link: "/tables" },
          ].map((item, i) => (
            <Link key={i} to={item.link} className="flex items-center gap-4 py-2 border-b border-border/50 last:border-0 hover:text-primary transition-colors">
              <Clock className="w-4 h-4 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground">{item.action}</p>
                <p className="text-xs text-muted-foreground truncate">{item.detail}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
