// /ask <question>: deferReply ngay, gọi API, editReply bằng embed có nguồn + nút hỏi tiếp (feedback đang Deferred).
// Phụ trách: TV4 · [S2] Bot /ask · [S3] Bot: câu trả lời thật

import { randomUUID } from "node:crypto";
import { ActionRowBuilder, ButtonBuilder, ButtonStyle, ChannelType, SlashCommandBuilder } from "discord.js";
import { ApiError, createApiClient } from "../api/client.ts";
import type { ChatRequest, ChatResponse } from "../api/types.ts";
import { MAX_MESSAGE_CHARS } from "../api/types.ts";
import { answerEmbeds } from "../utils/format.ts";
import { externalRef } from "../utils/identity.ts";
import { errorName, log } from "../utils/logger.ts";
import type { Command } from "./index.ts";
import { loadWebUrl } from "../config.ts";
import type { AnswerShareCreated } from "../api/types.ts";
import { FollowupError, followupThreads } from "../interactions/followup.ts";
import type { FollowupThreads } from "../interactions/followup.ts";

export function createAskCommand(
  chat?: (body: ChatRequest) => Promise<ChatResponse>,
  sharing: {
    webUrl?: string;
    createShare?: (conversationId: string, messageId: string) => Promise<AnswerShareCreated>;
  } = {},
  followup: FollowupThreads = followupThreads,
): Command {
  return {
    data: new SlashCommandBuilder()
      .setName("ask")
      .setDescription("Đặt câu hỏi về Elden Ring.")
      .addStringOption((option) =>
        option
          .setName("question")
          .setDescription("Câu hỏi của bạn")
          .setRequired(true)
          .setMinLength(1)
          .setMaxLength(MAX_MESSAGE_CHARS),
      ),
    async execute(interaction) {
      // Luôn xác nhận interaction trước khi đọc cấu hình hoặc thực hiện I/O backend.
      await interaction.deferReply();
      const requestId = randomUUID();
      try {
        const question = interaction.options.getString("question", true).trim();
        if (!question || [...question].length > MAX_MESSAGE_CHARS) {
          await interaction.editReply({
            content: `Câu hỏi cần có từ 1 đến ${MAX_MESSAGE_CHARS} ký tự.`,
            allowedMentions: { parse: [] },
          });
          return;
        }
        if (interaction.channel?.isThread() && (interaction.channel.archived || interaction.channel.locked)) {
          throw new FollowupError("Thread đã lưu trữ hoặc bị khóa. Hãy gửi /ask ở kênh chính.");
        }
        const response = await followup.chat(
          {
            message: question,
            channel: "discord",
            external_ref: externalRef(
              interaction.channelId,
              interaction.channel?.isThread() ?? false,
              interaction.user.id,
            ),
            ...(interaction.guildId ? { guild_id: interaction.guildId } : {}),
            options: { lang: "auto", web_search: "auto" },
          },
          chat ?? createApiClient(undefined, { requestId }).chat,
        );
        const [first, ...remaining] = answerEmbeds(question, response);
        const components: ActionRowBuilder<ButtonBuilder>[] = [];
        if (interaction.guildId && interaction.channel?.type === ChannelType.GuildText) {
          components.push(
            new ActionRowBuilder<ButtonBuilder>().addComponents(
              followup.button({
                guildId: interaction.guildId,
                channelId: interaction.channelId,
                question,
                answer: response.answer,
              }),
            ),
          );
        }
        const webUrl = loadWebUrl({ WEB_URL: sharing.webUrl ?? process.env.WEB_URL });
        const createShare =
          sharing.createShare ?? (!chat ? createApiClient(undefined, { requestId }).createAnswerShare : undefined);
        if (webUrl && createShare) {
          try {
            const share = await createShare(response.conversation_id, response.message_id);
            if (!/^[A-Za-z0-9_-]{43}$/.test(share.token)) throw new Error("Invalid share token");
            const url = new URL("/answer", webUrl);
            url.hash = share.token;
            components.push(
              new ActionRowBuilder<ButtonBuilder>().addComponents(
                new ButtonBuilder()
                  .setStyle(ButtonStyle.Link)
                  .setLabel("Xem đầy đủ trên web · 24 giờ")
                  .setURL(url.href),
              ),
            );
            const footer = first.data.footer?.text;
            first.setFooter({ text: `${footer ? `${footer} ` : ""}Ai có link có thể đọc câu trả lời trong 24 giờ.` });
          } catch (error) {
            // Link phụ lỗi không được làm mất câu trả lời đã nhận từ backend.
            log("warn", "Chưa tạo được link xem đầy đủ.", { request_id: requestId, error: errorName(error) });
          }
        }
        await interaction.editReply({ embeds: [first], components, allowedMentions: { parse: [] } });
        for (const embed of remaining) {
          await interaction.followUp({ embeds: [embed], allowedMentions: { parse: [] } });
        }
      } catch (error) {
        log("error", "Lệnh ask chưa hoàn tất.", {
          request_id: requestId,
          interaction_id: interaction.id,
          error: errorName(error),
        });
        await interaction.editReply({
          content:
            error instanceof ApiError || error instanceof FollowupError
              ? error.message
              : "Chưa xử lý được câu hỏi. Vui lòng kiểm tra cấu hình bot hoặc thử lại sau.",
          embeds: [],
          allowedMentions: { parse: [] },
        });
      }
    },
  };
}

export const ask = createAskCommand();
