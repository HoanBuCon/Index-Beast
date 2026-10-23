// Đăng ký slash command toàn cục cho mọi server đã cài bot.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import { REST, Routes } from "discord.js";
import { commands } from "./commands/index.ts";
import { loadConfig } from "./config.ts";
import { errorName, log } from "./utils/logger.ts";

try {
  const config = loadConfig();
  const rest = new REST({ version: "10" }).setToken(config.token);
  const route = Routes.applicationCommands(config.clientId);
  // Bulk PUT thay thế danh sách lệnh của ứng dụng trong phạm vi đã chọn.
  await rest.put(route, { body: [...commands.values()].map((command) => command.data.toJSON()) });
  log("info", "Đã đăng ký slash commands.", { scope: "global" });
} catch (error) {
  log("error", "Không đăng ký được lệnh. Kiểm tra cấu hình, kết nối và quyền cài bot.", { error: errorName(error) });
  process.exitCode = 1;
}
