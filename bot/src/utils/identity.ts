// Băm người dùng và dựng external_ref cho hội thoại Discord; dùng chung bởi /ask, /clear và trả lời tin nhắn.
// Công thức phải giữ nguyên: backend xóa ký ức theo đuôi `:<user_hash>` của external_ref.

import { createHash } from "node:crypto";

// Bút danh sha256 hex 64 ký tự (không phải ẩn danh, xem docs/api/discord-guild-tv4.md).
export function userHash(userId: string): string {
  return createHash("sha256").update(userId).digest("hex");
}

export function externalRef(channelId: string, isThread: boolean, userId: string): string {
  return isThread ? `discord:thread:${channelId}` : `discord:channel:${channelId}:${userHash(userId)}`;
}
