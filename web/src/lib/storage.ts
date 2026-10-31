// Đọc/ghi localStorage có try/catch.
// Phụ trách: TV4 · [S4]

import type { Conversation } from "../api/types";
import { isSource } from "../api/types.ts";
import { readChatImages } from "../api/images.ts";
const KEY = "indexbeast.conversations.v1";
export function readConversations(): Conversation[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    if (!Array.isArray(value)) return [];
    // Kiểm tra trước khi render dữ liệu trình duyệt cũ hoặc bị sửa thủ công.
    return value
      .filter(
        (c): c is Conversation =>
          c &&
          typeof c.id === "string" &&
          typeof c.title === "string" &&
          (c.mode === "demo" || c.mode === "api" || c.mode === "api-stream") &&
          (c.serverId === null || typeof c.serverId === "string") &&
          typeof c.updatedAt === "string" &&
          Array.isArray(c.messages) &&
          c.messages.every((m: unknown) => {
            if (!m || typeof m !== "object") return false;
            const item = m as Record<string, unknown>;
            return (
              typeof item.id === "string" &&
              typeof item.content === "string" &&
              (item.role === "user" || item.role === "assistant") &&
              Array.isArray(item.sources) &&
              item.sources.every(isSource)
            );
          }),
      )
      .slice(0, 30)
      .map((conversation) => ({
        ...conversation,
        messages: conversation.messages.map((message) =>
          message.images === undefined
            ? message
            : { ...message, images: readChatImages(message.images, message.sources) },
        ),
      }));
  } catch {
    return [];
  }
}
export function saveConversations(conversations: Conversation[]): boolean {
  try {
    localStorage.setItem(KEY, JSON.stringify(conversations.slice(0, 30)));
    return true;
  } catch {
    return false;
  }
}
