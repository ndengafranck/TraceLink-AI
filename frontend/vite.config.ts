import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser talks to /api on this server; Vite forwards it to FastAPI.
// Same origin, so the backend needs no CORS settings.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: backend, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } },
  },
  preview: {
    port: 5173,
    proxy: { "/api": { target: backend, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
