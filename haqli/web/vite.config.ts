import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8002",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:8002",
        ws: true,
      },
      "/healthz": "http://127.0.0.1:8002",
      "/readyz": "http://127.0.0.1:8002",
    },
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
});
