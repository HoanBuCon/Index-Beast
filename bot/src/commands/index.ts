// Registry: tên lệnh → định nghĩa + handler.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import type { ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";
import { ping } from "./ping.ts";

export interface Command {
  data: SlashCommandBuilder;
  execute(interaction: ChatInputCommandInteraction): Promise<void>;
}

export const commands: ReadonlyMap<string, Command> = new Map([[ping.data.name, ping]]);
