import { useEffect, useMemo, useState } from "react";
import { Save, Database, Globe, Key, CheckCircle } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { buildDataEndpoint, loadSettings, saveSettings, type AppSettings } from "@/lib/settings";

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);
  const [config, setConfig] = useState<AppSettings>({
    host: "COG-AMB-COM158",
    port: "1433",
    database: "insurance",
    username: "sa",
    password: "",
    apiBase: "http://10.10.8.218:8000",
    uploaderApiUrl: "http://10.10.8.218:8000",
    pgAgentApiUrl: "http://10.10.8.218:8001",
    queryAgentApiUrl: "http://10.10.8.218:8002",
    llmDataBaseUrl: "http://10.10.8.218:8001",
    llmDataPathPrefix: "/api/tables/",
    llmDataResourceName: "insurance_claims",
    autoRefresh: true,
  });

  useEffect(() => {
    const stored = loadSettings();
    if (!stored) return;
    setConfig((c) => ({ ...c, ...stored }));
  }, []);

  const handleSave = () => {
    saveSettings(config);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const update = (key: string, value: string | boolean) => setConfig((c) => ({ ...c, [key]: value }));

  const combinedDataEndpoint = useMemo(
    () => buildDataEndpoint(config.llmDataBaseUrl, config.llmDataPathPrefix, config.llmDataResourceName),
    [config.llmDataBaseUrl, config.llmDataPathPrefix, config.llmDataResourceName]
  );

  return (
    <div className="animate-fade-in max-w-2xl">
      <PageHeader title="Settings" description="Configure your database connection and application preferences." />

      {/* Database Connection */}
      <div className="glass-panel rounded-lg p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Database className="w-5 h-5 text-primary" />
          <h2 className="font-display font-semibold text-foreground">Database Connection</h2>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="host">Host</Label>
            <Input id="host" value={config.host} onChange={(e) => update("host", e.target.value)} className="mt-1" />
          </div>
          <div>
            <Label htmlFor="port">Port</Label>
            <Input id="port" value={config.port} onChange={(e) => update("port", e.target.value)} className="mt-1" />
          </div>
          <div>
            <Label htmlFor="database">Database</Label>
            <Input id="database" value={config.database} onChange={(e) => update("database", e.target.value)} className="mt-1" />
          </div>
          <div>
            <Label htmlFor="username">Username</Label>
            <Input id="username" value={config.username} onChange={(e) => update("username", e.target.value)} className="mt-1" />
          </div>
          <div className="col-span-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" value={config.password} onChange={(e) => update("password", e.target.value)} className="mt-1" placeholder="••••••••" />
          </div>
        </div>
      </div>

      {/* API Configuration */}
      <div className="glass-panel rounded-lg p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-5 h-5 text-info" />
          <h2 className="font-display font-semibold text-foreground">API Configuration</h2>
        </div>
        <div className="space-y-4">
          <div>
            <Label htmlFor="uploaderApiUrl">Uploader API Base URL</Label>
            <Input
              id="uploaderApiUrl"
              value={config.uploaderApiUrl}
              onChange={(e) => update("uploaderApiUrl", e.target.value)}
              className="mt-1"
              placeholder="http://localhost:8000"
            />
            <p className="text-xs text-muted-foreground mt-1">Used for Excel/CSV file uploads and data ingestion.</p>
          </div>
          <div>
            <Label htmlFor="pgAgentApiUrl">pg-agent API Base URL</Label>
            <Input
              id="pgAgentApiUrl"
              value={config.pgAgentApiUrl}
              onChange={(e) => update("pgAgentApiUrl", e.target.value)}
              className="mt-1"
              placeholder="http://localhost:8001"
            />
            <p className="text-xs text-muted-foreground mt-1">Used for listing tables, running SQL, and natural language queries.</p>
          </div>
          <div>
            <Label htmlFor="queryAgentApiUrl">Query Agent API Base URL</Label>
            <Input
              id="queryAgentApiUrl"
              value={config.queryAgentApiUrl}
              onChange={(e) => update("queryAgentApiUrl", e.target.value)}
              className="mt-1"
              placeholder="http://localhost:8002"
            />
            <p className="text-xs text-muted-foreground mt-1">Used for advanced data analysis and table insights.</p>
          </div>
        </div>
      </div>

      {/* LLM Configuration */}
      <div className="glass-panel rounded-lg p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Key className="w-5 h-5 text-accent" />
          <h2 className="font-display font-semibold text-foreground">LLM Configuration</h2>
        </div>
        <div className="space-y-4">
          <div>
            <Label htmlFor="llmDataBaseUrl">Base URL</Label>
            <Input
              id="llmDataBaseUrl"
              value={config.llmDataBaseUrl}
              onChange={(e) => update("llmDataBaseUrl", e.target.value)}
              className="mt-1"
              placeholder="http://localhost:8001"
            />
          </div>
          <div>
            <Label htmlFor="llmDataPathPrefix">API path/prefix</Label>
            <Input
              id="llmDataPathPrefix"
              value={config.llmDataPathPrefix}
              onChange={(e) => update("llmDataPathPrefix", e.target.value)}
              className="mt-1"
              placeholder="/api/tables/"
            />
          </div>
          <div>
            <Label htmlFor="llmDataResourceName">Resource/table name</Label>
            <Input
              id="llmDataResourceName"
              value={config.llmDataResourceName}
              onChange={(e) => update("llmDataResourceName", e.target.value)}
              className="mt-1"
              placeholder="extracted_schema_20260304_192410"
            />
          </div>
          <div>
            <Label htmlFor="llmDataCombined">Combined endpoint preview</Label>
            <Input id="llmDataCombined" value={combinedDataEndpoint} readOnly className="mt-1 font-mono text-xs" />
          </div>
        </div>
      </div>

      {/* Preferences */}
      <div className="glass-panel rounded-lg p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Key className="w-5 h-5 text-accent" />
          <h2 className="font-display font-semibold text-foreground">Preferences</h2>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Auto-refresh tables</p>
            <p className="text-xs text-muted-foreground">Automatically refresh table list on page load</p>
          </div>
          <Switch checked={config.autoRefresh} onCheckedChange={(v) => update("autoRefresh", v)} />
        </div>
      </div>

      <Button onClick={handleSave} className="w-full">
        {saved ? (
          <>
            <CheckCircle className="w-4 h-4 mr-2" />
            Saved!
          </>
        ) : (
          <>
            <Save className="w-4 h-4 mr-2" />
            Save Settings
          </>
        )}
      </Button>
    </div>
  );
}
