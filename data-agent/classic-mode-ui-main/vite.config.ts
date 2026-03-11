import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
    proxy: {
      // ── pg-agent (port 8001) ───────────────────────────────────────────────
      "/api/tables": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/sql": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/schema": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/nlq": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      // ── Query / AI Agent (port 8002) ───────────────────────────────────────
      "/analyze": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
      "/preview-data": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
