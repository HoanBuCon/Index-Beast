// Registry: tên lệnh → định nghĩa + handler.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import type { ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";
import { ping } from "./ping.ts";
import { ask } from "./ask.ts";

export interface Command {
  data: Pick<SlashCommandBuilder, "name" | "toJSON">;
  execute(interaction: ChatInputCommandInteraction): Promise<void>;
}

export const commands: ReadonlyMap<string, Command> = new Map([
  [ping.data.name, ping],
  [ask.data.name, ask],
]);
