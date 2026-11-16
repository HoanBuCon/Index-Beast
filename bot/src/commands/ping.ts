// /ping: độ trễ websocket Discord + vòng đi về tới /api/v1/health của backend.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot · [S5] thêm health API

import { MessageFlags, SlashCommandBuilder } from "discord.js";
import type { ApiClient } from "../api/client.ts";
import { ApiError } from "../api/client.ts";
import { defaultApi } from "../runtime.ts";
import { errorName, log } from "../utils/logger.ts";
import type { Command } from "./index.ts";

export function createPingCommand(api: () => Pick<ApiClient, "health"> = defaultApi): Command {
  return {
    data: new SlashCommandBuilder().setName("ping").setDescription("Kiểm tra độ trễ Discord và tình trạng API."),
    async execute(interaction) {
      await interaction.deferReply({ flags: MessageFlags.Ephemeral });
      const ws = interaction.client.ws.ping;
      const lines = [`Pong! Websocket Discord: ${ws >= 0 ? `${Math.round(ws)} ms` : "chưa đo được"}.`];
      try {
        const health = await api().health();
        const failed = Object.entries(health.checks)
          .filter(([, ok]) => !ok)
          .map(([name]) => name);
        lines.push(
          health.status === "ok"
            ? `API: ổn (${health.rtt_ms} ms).`
            : `API: suy giảm (${health.rtt_ms} ms)${failed.length ? `, lỗi: ${failed.join(", ")}` : ""}.`,
        );
      } catch (error) {
        log("warn", "Ping không gọi được health API.", { error: errorName(error) });
        lines.push(
          `API: không truy cập được${error instanceof ApiError && error.status ? ` (HTTP ${error.status})` : ""}.`,
        );
      }
      await interaction.editReply({ content: lines.join("\n"), allowedMentions: { parse: [] } });
    },
  };
}

export const ping = createPingCommand();
