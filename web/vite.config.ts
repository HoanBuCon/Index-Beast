import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Cổng dự án = cổng gốc + 10000, không dùng mặc định của công cụ (docs/quy_uoc.md → "Quy ước cổng")
const DEFAULT_API_PORT = "18000";
const DEFAULT_WEB_PORT = "15173";

export default defineConfig(({ mode }) => {
  // Đọc API_PORT, WEB_PORT từ .env ở gốc repo (cùng biến với `make api`); prefix "" để đọc cả biến không có VITE_.
  // Các giá trị này chỉ dùng cho dev server, không đưa vào bundle gửi trình duyệt.
  const env = loadEnv(mode, "..", "");
  const apiPort = env.API_PORT || DEFAULT_API_PORT;
  const webPort = Number(env.WEB_PORT || DEFAULT_WEB_PORT);

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: webPort,
      strictPort: true, // cổng bận thì báo lỗi, không tự nhảy sang cổng khác làm lệch CORS_ORIGINS
      // Dev: chuyển /api sang FastAPI chạy local. Production: Caddy làm việc này.
      // Dùng 127.0.0.1: "localhost" có thể phân giải sang IPv6 (::1) trong khi uvicorn chỉ nghe IPv4.
      proxy: { "/api": `http://127.0.0.1:${apiPort}` },
    },
  };
});
