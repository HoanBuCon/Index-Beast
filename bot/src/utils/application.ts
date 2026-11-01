// Application ID cho đăng ký slash command: dùng DISCORD_CLIENT_ID nếu có, nếu không hỏi Discord bằng token bot.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot (TV1 bổ sung: DISCORD_CLIENT_ID không bắt buộc)

import { Routes } from "discord.js";

export interface ApplicationReader {
  get(route: `/${string}`): Promise<unknown>;
}

export async function resolveApplicationId(rest: ApplicationReader, configured?: string): Promise<string> {
  if (configured) return configured;
  const application = (await rest.get(Routes.currentApplication())) as { id?: unknown };
  if (typeof application?.id !== "string" || !/^\d{17,20}$/.test(application.id)) {
    throw new Error("Discord không trả về Application ID hợp lệ.");
  }
  return application.id;
}
