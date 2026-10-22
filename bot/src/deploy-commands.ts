// Đăng ký slash command (guild khi dev, global khi production).
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import { REST, Routes } from "discord.js";
import { commands } from "./commands/index.ts";
import { loadConfig } from "./config.ts";
import { errorName, log } from "./utils/logger.ts";

try {
  const config = loadConfig();
  const rest = new REST({ version: "10" }).setToken(config.token);
  const route = config.isProd
    ? Routes.applicationCommands(config.clientId)
    : Routes.applicationGuildCommands(config.clientId, config.guildId!);
  // Bulk PUT thay thế danh sách lệnh của ứng dụng trong phạm vi đã chọn.
  await rest.put(route, { body: [...commands.values()].map((command) => command.data.toJSON()) });
  log("info", "Đã đăng ký slash commands.", { scope: config.isProd ? "global" : "guild" });
} catch (error) {
  log("error", "Không đăng ký được lệnh. Kiểm tra cấu hình, kết nối và quyền cài bot.", { error: errorName(error) });
  process.exitCode = 1;
}
