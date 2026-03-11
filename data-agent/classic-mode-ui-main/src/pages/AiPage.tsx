import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Sparkles, Loader2, Database, Save, CheckCircle } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useApi } from "@/hooks/useApi";
import { getDataEndpoint } from "@/lib/settings";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  rowCount?: number;
}

const SUGGESTIONS = [
  "Show me all employees in Engineering",
  "What is the average salary by department?",
  "List all active policies",
  "How many claims are pending?",
  "Top 5 highest paid employees",
];

const ENDPOINT_STORAGE_KEY = "ai-assistant-endpoint";

const PREDEFINED_ENDPOINTS = [
  { label: "Claim Details (Table)", value: "http://10.10.8.218:8001/api/tables/ClaimDetails" },
  { label: "Pipeline Report (View)", value: "http://10.10.8.218:8001/api/views/View_Report_pipiline" },
  { label: "Client Profit Summary (View)", value: "http://10.10.8.218:8001/api/views/vw_ClientProfitSummary" },
  { label: "🔍 Full Database (AI Query)", value: "http://10.10.8.218:8001/api/nlq/ask" },
];

export default function AiPage() {
  const { analyzeQuery, loading } = useApi();

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm your AI data analyst. Ask me anything about your database in plain English. You can also set the data endpoint below to target a specific table.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");

  // Persistence logic
  const [endpoint, setEndpoint] = useState(() => {
    const saved = localStorage.getItem(ENDPOINT_STORAGE_KEY);
    return saved || getDataEndpoint();
  });
  const [savedStatus, setSavedStatus] = useState(false);

  const [showEndpoint, setShowEndpoint] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSaveEndpoint = () => {
    localStorage.setItem(ENDPOINT_STORAGE_KEY, endpoint);
    setSavedStatus(true);
    setTimeout(() => setSavedStatus(false), 2000);
  };

  const send = async (text?: string) => {
    const query = (text || input).trim();
    if (!query) return;
    setInput("");

    const userMsg: Message = { role: "user", content: query, timestamp: new Date() };
    setMessages((m) => [...m, userMsg]);

    try {
      const result = await analyzeQuery(query, endpoint.trim() || undefined);

      const assistantMsg: Message = {
        role: "assistant",
        content: result.answer,
        timestamp: new Date(),
        rowCount: result.row_count,
      };
      setMessages((m) => [...m, assistantMsg]);
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Sorry, I encountered an error: **${e.message || "Unknown error"}**. Make sure the query agent (port 8002) and pg-agent (port 8001) are running.`,
          timestamp: new Date(),
        },
      ]);
    }
  };

  const renderContent = (content: string) =>
    content.split(/(\*\*.*?\*\*)/).map((part, j) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={j} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      ) : (
        <span key={j}>{part}</span>
      )
    );

  return (
    <div className="animate-fade-in flex flex-col h-[calc(100vh-2rem)]">
      <PageHeader
        title="AI Assistant"
        description="Ask questions about your data in natural language."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowEndpoint((v) => !v)}
            title="Configure data endpoint"
          >
            <Database className="w-4 h-4 mr-2" />
            Endpoint
          </Button>
        }
      />

      {/* Endpoint config */}
      {showEndpoint && (
        <div className="mb-4 glass-panel rounded-lg p-4 space-y-4 animate-fade-in">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Data Source Selection</span>
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={handleSaveEndpoint}>
              {savedStatus ? <CheckCircle className="w-3 h-3 mr-1 text-green-500" /> : <Save className="w-3 h-3 mr-1" />}
              {savedStatus ? "Saved" : "Save Choice"}
            </Button>
          </div>

          <div className="grid gap-3">
            <div className="space-y-1">
              <label className="text-[10px] uppercase font-bold text-muted-foreground ml-1">Quick Select</label>
              <Select value={endpoint} onValueChange={setEndpoint}>
                <SelectTrigger className="w-full text-xs h-9 bg-background/50">
                  <SelectValue placeholder="Select a table or view" />
                </SelectTrigger>
                <SelectContent>
                  {PREDEFINED_ENDPOINTS.map((ep) => (
                    <SelectItem key={ep.value} value={ep.value} className="text-xs">
                      {ep.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] uppercase font-bold text-muted-foreground ml-1">Manual Endpoint URL</label>
              <Input
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="http://10.10.8.218:8001/api/tables/your_table"
                className="text-xs font-mono h-9 bg-background/50"
              />
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2">
        {messages.map((msg, i) => (
          <div key={i} className={cn("flex gap-3 animate-fade-in", msg.role === "user" && "justify-end")}>
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
            )}
            <div className="max-w-[75%] space-y-1">
              <div
                className={cn(
                  "rounded-lg px-4 py-3 text-sm",
                  msg.role === "user" ? "bg-primary text-primary-foreground" : "glass-panel"
                )}
              >
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {renderContent(msg.content)}
                </p>
              </div>
              {msg.rowCount !== undefined && (
                <p className="text-xs text-muted-foreground px-1">{msg.rowCount} rows scanned</p>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                <User className="w-4 h-4 text-accent" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3 animate-fade-in">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <Bot className="w-4 h-4 text-primary" />
            </div>
            <div className="glass-panel rounded-lg px-4 py-3">
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              onClick={() => send(s)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors"
            >
              <Sparkles className="w-3 h-3" />
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="glass-panel rounded-lg p-3 flex items-center gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your data…"
          className="border-0 bg-transparent focus-visible:ring-0"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
          }}
          disabled={loading}
        />
        <Button size="sm" onClick={() => send()} disabled={loading || !input.trim()}>
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
