// Cache RAM danh sách kênh /setup theo server (TTL ngắn) để không gọi API cho từng tin nhắn.
// Bot không giữ trạng thái bền: mất cache chỉ tốn một lần GET. /setup gọi invalidate để thấy thay đổi ngay.

export function createGuildChannelCache(
  fetchChannels: (guildId: string) => Promise<string[]>,
  {
    ttlMs = 30_000,
    emptyTtlMs = 300_000,
    failureBackoffMs = 10_000,
    now = () => Date.now(),
  }: { ttlMs?: number; emptyTtlMs?: number; failureBackoffMs?: number; now?: () => number } = {},
) {
  const entries = new Map<string, { channels: Set<string>; expires: number }>();
  const inflight = new Map<string, Promise<Set<string>>>();
  async function load(guildId: string): Promise<Set<string>> {
    const channels = new Set(await fetchChannels(guildId));
    // Server chưa bật kênh nào là trường hợp phổ biến nhất: cache lâu hơn; /setup invalidate nên vẫn tức thì trên cùng bản bot.
    entries.set(guildId, { channels, expires: now() + (channels.size ? ttlMs : emptyTtlMs) });
    return channels;
  }
  return {
    // Lỗi API: dùng bản cũ nếu có (hết hạn vẫn tốt hơn im lặng), nếu chưa có thì ném lỗi cho caller.
    async has(guildId: string, channelId: string): Promise<boolean> {
      const entry = entries.get(guildId);
      if (entry && entry.expires > now()) return entry.channels.has(channelId);
      let pending = inflight.get(guildId);
      if (!pending) {
        pending = load(guildId).finally(() => inflight.delete(guildId));
        inflight.set(guildId, pending);
      }
      try {
        return (await pending).has(channelId);
      } catch (error) {
        if (entry) {
          // Gia hạn ngắn để API sập không kéo theo một GET cho mỗi tin nhắn.
          entry.expires = now() + failureBackoffMs;
          return entry.channels.has(channelId);
        }
        throw error;
      }
    },
    invalidate(guildId: string) {
      entries.delete(guildId);
    },
  };
}
export type GuildChannelCache = ReturnType<typeof createGuildChannelCache>;
