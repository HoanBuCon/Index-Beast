// /ping: kiểm tra bot đã kết nối và xử lý được interaction.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import { SlashCommandBuilder } from "discord.js";
import type { Command } from "./index.ts";

export const ping: Command = {
  data: new SlashCommandBuilder().setName("ping").setDescription("Kiểm tra kết nối bot."),
  async execute(interaction) {
    await interaction.reply("Pong!");
  },
};
