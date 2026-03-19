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
      // ── Port 8000: Uploader / Connect Service ──────────────────────────────
      "/upload": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/api/connect": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/api/data": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/tables": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/table": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      // ── Port 8001: pg-agent ────────────────────────────────────────────────
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
      "/api/views": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/info": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      // ── Port 8002: Query / AI Agent ───────────────────────────────────────
      "/analyze": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
      "/preview-data": {
        target: "http://localhost:8002",
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
