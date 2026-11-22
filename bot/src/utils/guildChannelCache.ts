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
  // Mỗi invalidate tăng phiên bản của guild: lần tải bắt đầu trước đó không được ghi đè cấu hình mới.
  const generations = new Map<string, number>();
  const generation = (guildId: string) => generations.get(guildId) ?? 0;
  async function load(guildId: string): Promise<Set<string>> {
    const started = generation(guildId);
    const channels = new Set(await fetchChannels(guildId));
    // Server chưa bật kênh nào là trường hợp phổ biến nhất: cache lâu hơn; /setup invalidate nên vẫn tức thì trên cùng bản bot.
    if (generation(guildId) === started) {
      entries.set(guildId, { channels, expires: now() + (channels.size ? ttlMs : emptyTtlMs) });
    }
    return channels;
  }
  return {
    // Lỗi API: dùng bản cũ nếu có (hết hạn vẫn tốt hơn im lặng), nếu chưa có thì ném lỗi cho caller.
    async has(guildId: string, channelId: string): Promise<boolean> {
      const started = generation(guildId);
      const entry = entries.get(guildId);
      if (entry && entry.expires > now()) return entry.channels.has(channelId);
      let pending = inflight.get(guildId);
      if (!pending) {
        const created: Promise<Set<string>> = load(guildId).finally(() => {
          if (inflight.get(guildId) === created) inflight.delete(guildId);
        });
        pending = created;
        inflight.set(guildId, pending);
      }
      try {
        const channels = await pending;
        // /setup đổi cấu hình trong lúc chờ: kết quả này đã cũ, đọc lại.
        return generation(guildId) === started ? channels.has(channelId) : this.has(guildId, channelId);
      } catch (error) {
        if (generation(guildId) !== started) return this.has(guildId, channelId);
        if (entry) {
          // Gia hạn ngắn để API sập không kéo theo một GET cho mỗi tin nhắn.
          entry.expires = now() + failureBackoffMs;
          return entry.channels.has(channelId);
        }
        throw error;
      }
    },
    invalidate(guildId: string) {
      generations.set(guildId, generation(guildId) + 1);
      entries.delete(guildId);
      inflight.delete(guildId);
    },
  };
}
export type GuildChannelCache = ReturnType<typeof createGuildChannelCache>;
