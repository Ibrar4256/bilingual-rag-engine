import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://localhost:8000",
      "/admin": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/search": "http://localhost:8000",
      "/match": "http://localhost:8000",
      "/ask": "http://localhost:8000",
      "/agent": "http://localhost:8000",
    },
  },
});
