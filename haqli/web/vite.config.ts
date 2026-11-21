/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const backend = process.env.HAQLI_API_URL || "http://127.0.0.1:8002";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
    // The dev server is opened through preview proxies and Telegram tunnels, so any Host header is accepted.
    allowedHosts: true,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
      "/healthz": backend,
      "/readyz": backend,
    },
  },
  preview: {
    host: true,
    allowedHosts: true,
  },
  build: {
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "zustand", "@tanstack/react-query"],
          i18n: ["i18next", "react-i18next"],
          motion: ["motion"],
        },
      },
    },
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "node",
  },
});
