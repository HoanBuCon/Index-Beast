// /clear: xóa ký ức hội thoại của bot trong server. FR-BOT-10.
//   /clear user [member:@ai] — chính mình (mặc định) hoặc người khác (cần Manage Server)
//   /clear all               — cả server, kể cả thread dùng chung (cần Manage Server)
// Phụ trách: TV4 · [S5] Bot: lệnh cơ bản (làm hộ bởi agent của TV1)

import { InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { ApiClient } from "../api/client.ts";
import { ApiError } from "../api/client.ts";
import type { MemoryClearResult } from "../api/types.ts";
import { defaultApi } from "../runtime.ts";
import { userHash } from "../utils/identity.ts";
import { errorName, log } from "../utils/logger.ts";
import { isGuildAdmin } from "../utils/permissions.ts";
import type { Command } from "./index.ts";

// Văn bản kết quả; threads_kept > 0 sau /clear user phải được nói rõ (hợp đồng docs/api/discord-guild-tv4.md).
export function clearSummary(result: MemoryClearResult, subject: string): string {
  const { conversations, threads_kept: threads } = result;
  if (result.scope === "all") {
    return conversations
      ? `Đã xóa ${conversations} cuộc hội thoại Discord của server (gồm cả thread).`
      : "Server không có dữ liệu hội thoại nào để xóa.";
  }
  const note = threads
    ? ` Các cuộc trò chuyện trong thread dùng chung (${threads} thread của server) được giữ lại; chỉ \`/clear all\` mới xóa thread.`
    : "";
  if (!conversations && !threads) return `Không có dữ liệu của ${subject} để xóa.`;
  if (!conversations) return `Không có hội thoại riêng của ${subject} để xóa.${note}`;
  return `Đã xóa ${conversations} cuộc hội thoại riêng của ${subject}.${note}`;
}

export function createClearCommand(api: () => Pick<ApiClient, "clearMemory"> = defaultApi): Command {
  return {
    data: new SlashCommandBuilder()
      .setName("clear")
      .setDescription("Xóa ký ức hội thoại mà bot lưu trong server này.")
      .setContexts(InteractionContextType.Guild)
      .addSubcommand((sub) =>
        sub
          .setName("user")
          .setDescription("Xóa ký ức của bạn (hoặc của một thành viên nếu bạn là admin).")
          .addUserOption((option) =>
            option.setName("member").setDescription("Thành viên cần xóa; bỏ trống để xóa của chính bạn"),
          ),
      )
      .addSubcommand((sub) => sub.setName("all").setDescription("Xóa ký ức của cả server (chỉ admin).")),
    async execute(interaction) {
      await interaction.deferReply({ flags: MessageFlags.Ephemeral });
      const reply = (content: string) => interaction.editReply({ content, allowedMentions: { parse: [] } });
      const guildId = interaction.guildId;
      if (!guildId) {
        await reply("`/clear` chỉ dùng trong server.");
        return;
      }
      try {
        if (interaction.options.getSubcommand() === "all") {
          if (!isGuildAdmin(interaction)) {
            await reply("Chỉ thành viên có quyền **Manage Server** mới dùng được `/clear all`.");
            return;
          }
          await reply(clearSummary(await api().clearMemory(guildId, { scope: "all" }), "server"));
          return;
        }
        const target = interaction.options.getUser("member") ?? interaction.user;
        const self = target.id === interaction.user.id;
        if (target.bot) {
          await reply("Bot không có ký ức hội thoại để xóa.");
          return;
        }
        if (!self && !isGuildAdmin(interaction)) {
          await reply("Bạn chỉ xóa được ký ức của chính mình. Xóa của người khác cần quyền **Manage Server**.");
          return;
        }
        const result = await api().clearMemory(guildId, { scope: "user", userHash: userHash(target.id) });
        await reply(clearSummary(result, self ? "bạn" : `<@${target.id}>`));
      } catch (error) {
        log("error", "Lệnh clear chưa hoàn tất.", { interaction_id: interaction.id, error: errorName(error) });
        await reply(error instanceof ApiError ? error.message : "Chưa xóa được ký ức. Vui lòng thử lại sau.");
      }
    },
  };
}

export const clear = createClearCommand();
