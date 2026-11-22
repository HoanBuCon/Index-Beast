// Giả lập interaction/message Discord cho test lệnh S5; không kết nối Gateway thật.
import type { ChatInputCommandInteraction, InteractionEditReplyOptions, Message } from "discord.js";
import { ChannelType, PermissionFlagsBits } from "discord.js";

export const GUILD = "1000000000000000001";
export const CHANNEL = "2000000000000000005";
export const BOT_ID = "900000000000000009";

export interface FakeInteractionOptions {
  sub: string;
  admin?: boolean;
  guildId?: string | null;
  userId?: string;
  channel?: { id: string };
  member?: { id: string; bot?: boolean };
  wsPing?: number;
}

export function fakeInteraction(opts: FakeInteractionOptions) {
  const calls: string[] = [];
  const edits: InteractionEditReplyOptions[] = [];
  const user = { id: opts.userId ?? "111111111111111111", bot: false };
  const value = {
    id: "333333333333333333",
    guildId: opts.guildId === undefined ? GUILD : opts.guildId,
    user,
    client: { ws: { ping: opts.wsPing ?? 42 } },
    memberPermissions: {
      has: (flag: bigint) => Boolean(opts.admin) && flag === PermissionFlagsBits.ManageGuild,
    },
    options: {
      getSubcommand: () => opts.sub,
      getChannel: () => opts.channel ?? { id: CHANNEL },
      getUser: () => opts.member ?? null,
    },
    deferReply: async () => {
      calls.push("defer");
    },
    editReply: async (payload: InteractionEditReplyOptions) => {
      calls.push("edit");
      edits.push(payload);
    },
  };
  return { value: value as unknown as ChatInputCommandInteraction, calls, edits };
}

export interface FakeMessageOptions {
  content: string;
  authorId?: string;
  bot?: boolean;
  webhookId?: string | null;
  system?: boolean;
  guildId?: string | null;
  channelId?: string;
  thread?: { parentId: string };
  mentioned?: boolean;
}

export function fakeMessage(opts: FakeMessageOptions) {
  const replies: Record<string, unknown>[] = [];
  const sent: Record<string, unknown>[] = [];
  const value = {
    content: opts.content,
    author: { id: opts.authorId ?? "111111111111111111", bot: opts.bot ?? false },
    webhookId: opts.webhookId ?? null,
    system: opts.system ?? false,
    guildId: opts.guildId === undefined ? GUILD : opts.guildId,
    channelId: opts.channelId ?? CHANNEL,
    client: { user: { id: BOT_ID } },
    mentions: { has: (id: string) => Boolean(opts.mentioned) && id === BOT_ID },
    channel: {
      type: opts.thread ? ChannelType.PublicThread : ChannelType.GuildText,
      isThread: () => Boolean(opts.thread),
      parentId: opts.thread?.parentId ?? null,
      sendTyping: async () => {},
      send: async (payload: Record<string, unknown>) => {
        sent.push(payload);
      },
    },
    reply: async (payload: Record<string, unknown>) => {
      replies.push(payload);
    },
  };
  return { value: value as unknown as Message, replies, sent };
}
