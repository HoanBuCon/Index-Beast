// Quyền admin server: backend chỉ tin service token, nên bot phải kiểm tra trước khi gọi API ghi/xóa.

import { PermissionFlagsBits } from "discord.js";
import type { ChatInputCommandInteraction } from "discord.js";

// Administrator ngầm có mọi quyền nên `has(ManageGuild)` đã bao gồm. Ngoài server (DM) không có quyền.
export function isGuildAdmin(interaction: ChatInputCommandInteraction): boolean {
  return Boolean(interaction.guildId && interaction.memberPermissions?.has(PermissionFlagsBits.ManageGuild));
}
