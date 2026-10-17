import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Dev: chuyển /api sang FastAPI chạy local. Production: Caddy làm việc này.
    proxy: { "/api": "http://localhost:8000" },
  },
});
