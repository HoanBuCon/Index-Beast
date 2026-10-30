// Đọc biến môi trường (DISCORD_TOKEN, BOT_API_URL, API_SERVICE_TOKEN, WEB_URL), báo lỗi sớm nếu thiếu.
// BOT_API_URL để trống khi dev → dùng http://127.0.0.1:${API_PORT ?? 18000} (cùng cổng với `make api`).
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

// S1 chỉ xác thực thông tin Discord; cấu hình backend sẽ được dùng khi triển khai /ask ở S2.

// S2 tách cấu hình API để test client không cần token Discord hoặc đọc .env thật.
export function loadApiConfig(env: NodeJS.ProcessEnv = process.env) {
  const port = env.API_PORT?.trim() || "18000";
  const suppliedUrl = env.BOT_API_URL?.trim();
  if (!suppliedUrl && (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535)) {
    throw new Error("API_PORT phải là cổng từ 1 đến 65535.");
  }
  let url: URL;
  try {
    url = new URL(suppliedUrl || `http://127.0.0.1:${port}`);
  } catch {
    throw new Error("BOT_API_URL không hợp lệ.");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    !["", "/api/v1"].includes(url.pathname.replace(/\/+$/, ""))
  )
    throw new Error("BOT_API_URL cần là URL HTTP(S) gốc hoặc kết thúc bằng /api/v1, không chứa thông tin đăng nhập.");
  const serviceToken = env.API_SERVICE_TOKEN?.trim();
  return {
    baseUrl: `${url.origin}/api/v1`,
    serviceToken: serviceToken && serviceToken !== "change-me" ? serviceToken : undefined,
  };
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env) {
  const token = env.DISCORD_TOKEN?.trim();
  const clientId = env.DISCORD_CLIENT_ID?.trim();
  if (!token || token === "change-me") throw new Error("Cần điền DISCORD_TOKEN trong .env.");
  if (!clientId || !/^\d{17,20}$/.test(clientId)) throw new Error("DISCORD_CLIENT_ID phải là Application ID.");
  // Bot dùng chung cho mọi server đã cài đặt; không cần DISCORD_GUILD_ID.
  return { token, clientId };
}
