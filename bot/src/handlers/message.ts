// Trả lời tin nhắn thường: khi được mention (@bot câu hỏi) hoặc ở kênh admin đã bật bằng /setup. FR-BOT-08, FR-BOT-09.
// Cần intent GuildMessages + MessageContent (bật "Message Content Intent" trong Discord Developer Portal).
// Phụ trách: TV4 · [S5] Bot: lệnh cơ bản (làm hộ bởi agent của TV1)

import { ActionRowBuilder, ChannelType } from "discord.js";
import type { ButtonBuilder } from "discord.js";
import type { Message } from "discord.js";
import { ApiError, createApiClient } from "../api/client.ts";
import type { ChatRequest, ChatResponse } from "../api/types.ts";
import { MAX_MESSAGE_CHARS } from "../api/types.ts";
import { defaultChannelCache } from "../runtime.ts";
import { answerEmbeds } from "../utils/format.ts";
import type { GuildChannelCache } from "../utils/guildChannelCache.ts";
import { externalRef } from "../utils/identity.ts";
import { errorName, log } from "../utils/logger.ts";
import { sanitizeMentions } from "../utils/redact.ts";
import { createUserRateLimiter } from "../utils/rateLimit.ts";
import type { UserRateLimiter } from "../utils/rateLimit.ts";
import { FollowupError, followupThreads } from "../interactions/followup.ts";
import type { FollowupThreads } from "../interactions/followup.ts";

// Không bao giờ ping ai: tên người dùng/role trong câu trả lời chỉ là chữ.
const NO_MENTIONS = { parse: [] as never[], repliedUser: false };

export interface MessageHandlerDeps {
  cache?: Pick<GuildChannelCache, "has">;
  limiter?: Pick<UserRateLimiter, "check">;
  chat?: (body: ChatRequest) => Promise<ChatResponse>;
  followup?: FollowupThreads;
}

export function createMessageHandler(deps: MessageHandlerDeps = {}) {
  const limiter = deps.limiter ?? createUserRateLimiter();
  const followup = deps.followup ?? followupThreads;
  return async function handleMessage(message: Message): Promise<void> {
    // Bỏ bot/webhook/tin hệ thống và DM; chỉ phục vụ trong server.
    if (message.author.bot || message.webhookId || message.system || !message.guildId) return;
    const botId = message.client.user?.id;
    if (!botId) return;
    // Chỉ mention tường minh trong nội dung; reply-ping tới tin của bot (message.mentions) không tính, tránh "cảm ơn" gọi LLM.
    const botMention = new RegExp(`<@!?${botId}>`, "g");
    const mentioned = botMention.test(message.content);
    const isThread = message.channel.isThread();
    if (!mentioned && !(isThread && followup.has(message.guildId, message.channelId))) {
      // Không có mention: chỉ trả lời ở kênh /setup (hoặc thread con của kênh đó). Tin trống/đính kèm thuần bị bỏ.
      if (!message.content.trim()) return;
      try {
        const cache = deps.cache ?? defaultChannelCache();
        const parentId = isThread ? message.channel.parentId : null;
        const enabled =
          (await cache.has(message.guildId, message.channelId)) ||
          (parentId !== null && (await cache.has(message.guildId, parentId)));
        if (!enabled) return;
      } catch (error) {
        log("warn", "Không đọc được danh sách kênh /setup.", { error: errorName(error) });
        return;
      }
    }
    const reply = (content: string) =>
      message.reply({ content, allowedMentions: NO_MENTIONS }).catch((error: unknown) => {
        log("warn", "Không gửi được phản hồi tin nhắn.", { error: errorName(error) });
      });
    const question = sanitizeMentions(message.content.replace(botMention, "")).trim();
    if (!question) {
      if (mentioned) await reply("Bạn muốn hỏi gì về Elden Ring? Hãy gõ câu hỏi sau khi nhắc tên tôi.");
      return;
    }
    if ([...question].length > MAX_MESSAGE_CHARS) {
      // Ở kênh tự trả lời, tin dài thường là chat thường: chỉ báo khi người dùng chủ động mention.
      if (mentioned) await reply(`Câu hỏi cần có từ 1 đến ${MAX_MESSAGE_CHARS} ký tự.`);
      return;
    }
    const verdict = limiter.check(message.author.id);
    if (verdict === "deny") return;
    if (verdict === "warn") {
      await reply("Bạn đang gửi quá nhanh. Vui lòng đợi một chút trước khi hỏi tiếp.");
      return;
    }
    const requestId = crypto.randomUUID();
    try {
      if (message.channel.isThread() && (message.channel.archived || message.channel.locked)) {
        throw new FollowupError("Thread đã lưu trữ hoặc bị khóa. Hãy gửi /ask ở kênh chính.");
      }
      if ("sendTyping" in message.channel) await message.channel.sendTyping().catch(() => {});
      const response = await followup.chat(
        {
          message: question,
          channel: "discord",
          external_ref: externalRef(message.channelId, isThread, message.author.id),
          guild_id: message.guildId,
          options: { lang: "auto", web_search: "auto" },
        },
        deps.chat ?? createApiClient(undefined, { requestId }).chat,
      );
      const [first, ...remaining] = answerEmbeds(question, response);
      const components =
        message.channel.type === ChannelType.GuildText
          ? [
              new ActionRowBuilder<ButtonBuilder>().addComponents(
                followup.button({
                  guildId: message.guildId,
                  channelId: message.channelId,
                  question,
                  answer: response.answer,
                }),
              ),
            ]
          : [];
      await message.reply({ embeds: [first], components, allowedMentions: NO_MENTIONS });
      for (const embed of remaining) {
        if ("send" in message.channel) await message.channel.send({ embeds: [embed], allowedMentions: { parse: [] } });
      }
    } catch (error) {
      log("error", "Không trả lời được tin nhắn.", { request_id: requestId, error: errorName(error) });
      await reply(
        error instanceof ApiError || error instanceof FollowupError
          ? error.message
          : "Chưa xử lý được câu hỏi. Vui lòng thử lại sau.",
      );
    }
  };
}
