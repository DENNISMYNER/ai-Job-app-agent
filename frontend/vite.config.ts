/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

// The dev server proxies /api to the local FastAPI backend (same-origin => no CORS/CSRF surface).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { port: 5173, proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], css: false, exclude: ["e2e/**", "node_modules/**"] },
});
