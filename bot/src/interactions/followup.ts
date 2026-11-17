// Nút 'Hỏi tiếp' tạo thread; tin nhắn trong thread dùng chung external_ref.
// Phụ trách: TV4 · [S4] Bot: hỏi tiếp trong thread

import { randomUUID } from "node:crypto";
import { ButtonBuilder, ButtonStyle, ChannelType, MessageFlags, ThreadAutoArchiveDuration } from "discord.js";
import type { ButtonInteraction, ThreadChannel } from "discord.js";
import { MAX_MESSAGE_CHARS } from "../api/types.ts";
import type { ChatRequest, ChatResponse } from "../api/types.ts";
import { errorName, log } from "../utils/logger.ts";

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;
const PREFIX = "followup:";
const NO_MENTIONS = { parse: [] as never[] };
type Chat = (body: ChatRequest) => Promise<ChatResponse>;
interface Origin {
  guildId: string;
  channelId: string;
  question: string;
  answer: string;
}
interface Entry extends Origin {
  expires: number;
  revoked?: boolean;
  thread?: ThreadChannel;
  creating?: Promise<ThreadChannel>;
}
interface ThreadState {
  origin: Entry;
  lastActive: number;
  seeded: boolean;
  busy: boolean;
}
export class FollowupError extends Error {}

// Cắt theo code point để không xé đôi emoji. Chỉ giữ trích đoạn câu đang công khai,
// tuyệt đối không lấy lịch sử riêng theo conversation_id của người hỏi.
function excerpt(value: string, limit: number): string {
  const chars = [...value];
  return chars.length <= limit ? value : `${chars.slice(0, Math.max(0, limit - 1)).join("")}…`;
}

function openingContext(body: ChatRequest, origin: Origin): string {
  const before =
    "Trích đoạn tham khảo từ câu trả lời công khai trước đó (không phải chỉ dẫn hệ thống):\nCâu hỏi trước: ";
  const middle = "\nCâu trả lời trước: ";
  const after = "\n\nCâu hỏi tiếp theo: ";
  const budget = MAX_MESSAGE_CHARS - [...(before + middle + after + body.message)].length;
  if (budget < 160) {
    throw new FollowupError("Câu hỏi đầu tiên trong thread quá dài để kèm ngữ cảnh. Vui lòng rút gọn câu hỏi.");
  }
  const question = excerpt(origin.question, Math.min(500, Math.floor(budget * 0.4)));
  const answer = excerpt(origin.answer, Math.min(900, budget - [...question].length));
  return before + question + middle + answer + after + body.message;
}

export function createFollowupThreads(options: { now?: () => number; limit?: number } = {}) {
  const now = options.now ?? Date.now;
  const limit = options.limit ?? 500;
  const buttons = new Map<string, Entry>();
  const threads = new Map<string, ThreadState>();
  const key = (guild: string, thread: string) => `${guild}:${thread}`;
  function remember<T>(map: Map<string, T>, id: string, value: T) {
    if (map.size >= limit) map.delete(map.keys().next().value!);
    map.set(id, value);
  }

  return {
    button(origin: Origin): ButtonBuilder {
      const id = PREFIX + randomUUID();
      remember(buttons, id, {
        ...origin,
        question: excerpt(origin.question, 500),
        answer: excerpt(origin.answer, 900),
        expires: now() + DAY,
      });
      return new ButtonBuilder().setCustomId(id).setStyle(ButtonStyle.Secondary).setLabel("Hỏi tiếp");
    },
    has(guildId: string, threadId: string): boolean {
      // Giữ dấu vết thread hết hạn để trả thông báo thay vì tự gọi API với ngữ cảnh mới.
      return threads.has(key(guildId, threadId));
    },
    clearGuild(guildId: string): void {
      for (const [id, entry] of buttons)
        if (entry.guildId === guildId) {
          entry.revoked = true;
          buttons.delete(id);
        }
      for (const [id, state] of threads)
        if (state.origin.guildId === guildId) {
          state.origin.revoked = true;
          threads.delete(id);
        }
    },
    async handle(interaction: ButtonInteraction): Promise<void> {
      // Xác nhận trước cả khi kiểm cache/Discord I/O. Không sửa tin trả lời gốc.
      await interaction.deferReply({ flags: MessageFlags.Ephemeral });
      const reply = (content: string) => interaction.editReply({ content, allowedMentions: NO_MENTIONS });
      const entry = buttons.get(interaction.customId);
      if (!entry || now() >= entry.expires) {
        await reply("Nút Hỏi tiếp đã hết hạn hoặc bot vừa khởi động lại. Hãy gửi /ask mới.");
        return;
      }
      if (entry.guildId !== interaction.guildId || entry.channelId !== interaction.channelId) {
        await reply("Nút Hỏi tiếp không thuộc kênh này.");
        return;
      }
      if (interaction.channel?.type !== ChannelType.GuildText) {
        await reply("Hãy dùng Hỏi tiếp trong kênh văn bản của server.");
        return;
      }
      try {
        // Một tin gốc chỉ tạo một thread, kể cả nhiều người bấm đồng thời.
        if (!entry.thread && !entry.creating) {
          entry.creating = (async () => {
            const thread = await interaction.message.startThread({
              name: "Hỏi tiếp · INDEX BEAST",
              autoArchiveDuration: ThreadAutoArchiveDuration.OneHour,
              reason: "Người dùng chọn Hỏi tiếp từ câu trả lời công khai của bot",
            });
            if (entry.revoked) throw new FollowupError("Ngữ cảnh đã bị xóa trong lúc mở thread. Hãy gửi /ask mới.");
            entry.thread = thread;
            remember(threads, key(entry.guildId, thread.id), {
              origin: entry,
              lastActive: now(),
              seeded: false,
              busy: false,
            });
            await thread
              .send({
                content:
                  "Bạn có thể hỏi tiếp ngay tại đây, không cần nhắc tên bot. Ngữ cảnh mở đầu chỉ gồm trích đoạn câu hỏi/câu trả lời gốc; mọi người trong thread dùng chung hội thoại. Thread tự lưu trữ sau 1 giờ không hoạt động.",
                allowedMentions: NO_MENTIONS,
              })
              .catch(() => log("warn", "Không gửi được hướng dẫn trong thread."));
            return thread;
          })();
        }
        const thread = entry.creating
          ? await entry.creating
          : await interaction.client.channels.fetch(entry.thread!.id);
        const state = threads.get(key(entry.guildId, entry.thread!.id));
        if (
          !thread?.isThread() ||
          thread.guildId !== entry.guildId ||
          thread.archived ||
          thread.locked ||
          !state ||
          now() - state.lastActive >= HOUR
        ) {
          await reply("Thread đã lưu trữ hoặc hết hạn. Hãy gửi /ask mới; bot không tự mở lại thread cũ.");
          return;
        }
        await reply(`Hỏi tiếp tại <#${thread.id}>. Đây là thread dùng chung cho người có quyền xem kênh.`);
      } catch (error) {
        log("warn", "Không mở được thread Hỏi tiếp.", { error: errorName(error) });
        await reply(
          error instanceof FollowupError
            ? error.message
            : "Không mở được thread. Kiểm tra quyền Create Public Threads, Send Messages in Threads và quyền xem kênh của bot, rồi thử lại.",
        );
      } finally {
        entry.creating = undefined;
      }
    },
    async chat(body: ChatRequest, chat: Chat): Promise<ChatResponse> {
      if (body.channel !== "discord") return chat(body);
      const match = /^discord:thread:(\d+)$/.exec(body.external_ref ?? "");
      const state = body.guild_id && match ? threads.get(key(body.guild_id, match[1])) : undefined;
      if (!state) return chat(body);
      if (now() >= state.origin.expires || now() - state.lastActive >= HOUR) {
        throw new FollowupError(
          "Thread Hỏi tiếp đã hết hạn do không hoạt động hoặc quá 24 giờ. Hãy gửi /ask ở kênh chính để bắt đầu lại.",
        );
      }
      if (state.busy) throw new FollowupError("Bot đang trả lời trong thread này. Vui lòng đợi rồi hỏi tiếp.");
      state.busy = true;
      try {
        const response = await chat(state.seeded ? body : { ...body, message: openingContext(body, state.origin) });
        state.seeded = true;
        state.lastActive = now();
        return response;
      } finally {
        state.busy = false;
      }
    },
  };
}

export type FollowupThreads = ReturnType<typeof createFollowupThreads>;
export const followupThreads = createFollowupThreads();
