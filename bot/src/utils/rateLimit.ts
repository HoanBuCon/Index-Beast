// Giới hạn tin nhắn trả lời tự động theo người dùng (cửa sổ trượt, trong RAM).
// "warn" chỉ trả về lần vượt đầu tiên của cửa sổ để bot nhắc một lần thay vì trả lời mọi tin spam.

const MAX_TRACKED = 1000;

export function createUserRateLimiter({
  max = 5,
  windowMs = 60_000,
  now = () => Date.now(),
}: { max?: number; windowMs?: number; now?: () => number } = {}) {
  const hits = new Map<string, { times: number[]; warned: boolean }>();
  // Dọn người dùng đã hết cửa sổ để Map không phình mãi; chạy ngay trong check khi Map lớn, không cần timer.
  function sweep() {
    const t = now();
    for (const [id, entry] of hits) if (entry.times.every((time) => t - time >= windowMs)) hits.delete(id);
  }
  return {
    check(userId: string): "allow" | "warn" | "deny" {
      if (hits.size > MAX_TRACKED) sweep();
      const t = now();
      const entry = hits.get(userId) ?? { times: [], warned: false };
      entry.times = entry.times.filter((time) => t - time < windowMs);
      if (entry.times.length < max) {
        entry.times.push(t);
        entry.warned = false;
        hits.set(userId, entry);
        return "allow";
      }
      hits.set(userId, entry);
      if (entry.warned) return "deny";
      entry.warned = true;
      return "warn";
    },
    sweep,
    size: () => hits.size,
  };
}
export type UserRateLimiter = ReturnType<typeof createUserRateLimiter>;
