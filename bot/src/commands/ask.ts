// /ask <question>: deferReply ngay, gọi API, editReply bằng embed có nguồn + nút feedback/hỏi tiếp.
// Phụ trách: TV4 · [S2] Bot /ask · [S3] Bot: câu trả lời thật

import { createHash, randomUUID } from "node:crypto";
import { ActionRowBuilder, ButtonBuilder, ButtonStyle, SlashCommandBuilder } from "discord.js";
import { ApiError, createApiClient } from "../api/client.ts";
import type { ChatRequest, ChatResponse } from "../api/types.ts";
import { MAX_MESSAGE_CHARS } from "../api/types.ts";
import { answerEmbeds } from "../utils/format.ts";
import { errorName, log } from "../utils/logger.ts";
import type { Command } from "./index.ts";
import { loadWebUrl } from "../config.ts";
import type { AnswerShareCreated } from "../api/types.ts";

export function createAskCommand(
  chat?: (body: ChatRequest) => Promise<ChatResponse>,
  sharing: {
    webUrl?: string;
    createShare?: (conversationId: string, messageId: string) => Promise<AnswerShareCreated>;
  } = {},
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
        const userHash = createHash("sha256").update(interaction.user.id).digest("hex");
        const externalRef = interaction.channel?.isThread()
          ? `discord:thread:${interaction.channelId}`
          : `discord:channel:${interaction.channelId}:${userHash}`;
        const response = await (chat ?? createApiClient(undefined, { requestId }).chat)({
          message: question,
          channel: "discord",
          external_ref: externalRef,
          options: { lang: "auto", spoilers: true, web_search: "auto" },
        });
        const [first, ...remaining] = answerEmbeds(question, response);
        const components: ActionRowBuilder<ButtonBuilder>[] = [];
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
            error instanceof ApiError
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
