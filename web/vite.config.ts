import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const DEFAULT_API_PORT = "8001";

export default defineConfig(({ mode }) => {
  // Đọc API_PORT từ .env ở gốc repo (cùng biến với `make api`); prefix "" để đọc cả biến không có tiền tố VITE_.
  // Giá trị này chỉ dùng cho proxy lúc dev, không đưa vào bundle gửi trình duyệt.
  const apiPort = loadEnv(mode, "..", "").API_PORT || DEFAULT_API_PORT;

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      // Dev: chuyển /api sang FastAPI chạy local. Production: Caddy làm việc này.
      // Dùng 127.0.0.1: "localhost" có thể phân giải sang IPv6 (::1) trong khi uvicorn chỉ nghe IPv4.
      proxy: { "/api": `http://127.0.0.1:${apiPort}` },
    },
  };
});
