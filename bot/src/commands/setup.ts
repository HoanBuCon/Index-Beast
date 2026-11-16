// /setup (admin server): bật/tắt kênh để bot trả lời mọi tin nhắn không cần /ask. FR-BOT-09.
// Discord không cho nhận văn bản tự do như `/setup disable all`, nên dùng subcommand:
//   /setup enable channel:#kênh · /setup disable channel:#kênh · /setup disable-all
// Phụ trách: TV4 · [S5] Bot: lệnh cơ bản (làm hộ bởi agent của TV1)

import {
  ChannelType,
  InteractionContextType,
  MessageFlags,
  PermissionFlagsBits,
  SlashCommandBuilder,
} from "discord.js";
import type { ApiClient } from "../api/client.ts";
import { ApiError } from "../api/client.ts";
import { defaultApi, defaultChannelCache } from "../runtime.ts";
import type { GuildChannelCache } from "../utils/guildChannelCache.ts";
import { errorName, log } from "../utils/logger.ts";
import { isGuildAdmin } from "../utils/permissions.ts";
import type { Command } from "./index.ts";

const TEXT_CHANNELS = [ChannelType.GuildText, ChannelType.GuildAnnouncement] as const;

export function createSetupCommand(
  api: () => Pick<ApiClient, "enableGuildChannel" | "disableGuildChannel" | "disableAllGuildChannels"> = defaultApi,
  cache: () => Pick<GuildChannelCache, "invalidate"> = defaultChannelCache,
): Command {
  return {
    data: new SlashCommandBuilder()
      .setName("setup")
      .setDescription("Bật/tắt kênh để bot trả lời mọi tin nhắn (cần quyền Manage Server).")
      .setContexts(InteractionContextType.Guild)
      // Gợi ý ẩn lệnh với người thường; server vẫn có thể đổi quyền, nên handler kiểm tra lại.
      .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
      .addSubcommand((sub) =>
        sub
          .setName("enable")
          .setDescription("Bot trả lời mọi tin nhắn trong kênh này, không cần /ask.")
          .addChannelOption((option) =>
            option
              .setName("channel")
              .setDescription("Kênh cần bật")
              .setRequired(true)
              .addChannelTypes(...TEXT_CHANNELS),
          ),
      )
      .addSubcommand((sub) =>
        sub
          .setName("disable")
          .setDescription("Tắt tự trả lời ở một kênh.")
          .addChannelOption((option) =>
            option
              .setName("channel")
              .setDescription("Kênh cần tắt")
              .setRequired(true)
              .addChannelTypes(...TEXT_CHANNELS),
          ),
      )
      .addSubcommand((sub) => sub.setName("disable-all").setDescription("Tắt tự trả lời ở mọi kênh của server.")),
    async execute(interaction) {
      await interaction.deferReply({ flags: MessageFlags.Ephemeral });
      const reply = (content: string) => interaction.editReply({ content, allowedMentions: { parse: [] } });
      // Kiểm quyền ngay sau defer (không gọi backend trước khi biết người gõ là admin).
      if (!isGuildAdmin(interaction)) {
        await reply("Chỉ thành viên có quyền **Manage Server** mới dùng được `/setup`.");
        return;
      }
      const guildId = interaction.guildId!;
      try {
        const subcommand = interaction.options.getSubcommand();
        const client = api();
        if (subcommand === "enable") {
          const channel = interaction.options.getChannel("channel", true);
          await client.enableGuildChannel(guildId, channel.id);
          await reply(
            `Đã bật <#${channel.id}>: bot trả lời mọi tin nhắn ở đó (bỏ qua bot/webhook, mỗi người tối đa vài tin mỗi phút). ` +
              "Bot cần quyền xem kênh và gửi tin nhắn.",
          );
        } else if (subcommand === "disable") {
          const channel = interaction.options.getChannel("channel", true);
          const deleted = await client.disableGuildChannel(guildId, channel.id);
          await reply(deleted ? `Đã tắt <#${channel.id}>.` : `<#${channel.id}> vốn chưa được bật.`);
        } else {
          const deleted = await client.disableAllGuildChannels(guildId);
          await reply(deleted ? `Đã tắt ${deleted} kênh của server.` : "Server chưa bật kênh nào.");
        }
        cache().invalidate(guildId);
      } catch (error) {
        log("error", "Lệnh setup chưa hoàn tất.", { interaction_id: interaction.id, error: errorName(error) });
        // Có thể đã ghi một phần (mạng ngắt sau khi backend xử lý): làm mới cache cho chắc.
        cache().invalidate(guildId);
        await reply(error instanceof ApiError ? error.message : "Chưa cập nhật được kênh. Vui lòng thử lại sau.");
      }
    },
  };
}

export const setup = createSetupCommand();
