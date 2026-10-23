// Đọc biến môi trường (DISCORD_TOKEN, BOT_API_URL, API_SERVICE_TOKEN, WEB_URL), báo lỗi sớm nếu thiếu.
// BOT_API_URL để trống khi dev → dùng http://127.0.0.1:${API_PORT ?? 18000} (cùng cổng với `make api`).
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

// S1 chỉ xác thực thông tin Discord; cấu hình backend sẽ được dùng khi triển khai /ask ở S2.

export function loadConfig(env: NodeJS.ProcessEnv = process.env) {
  const token = env.DISCORD_TOKEN?.trim();
  const clientId = env.DISCORD_CLIENT_ID?.trim();
  if (!token || token === "change-me") throw new Error("Cần điền DISCORD_TOKEN trong .env.");
  if (!clientId || !/^\d{17,20}$/.test(clientId)) throw new Error("DISCORD_CLIENT_ID phải là Application ID.");
  // Bot dùng chung cho mọi server đã cài đặt; không cần DISCORD_GUILD_ID.
  return { token, clientId };
}
