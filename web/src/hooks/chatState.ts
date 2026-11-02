// Thử lại thay thế lượt bị lỗi, không nhân đôi câu hỏi trong lịch sử frontend.
// Phụ trách: TV4 · [S2] UI chat cơ bản
import type { Conversation, StreamEvent } from "../api/types";
import { readChatImages } from "../api/images.ts";
export function answerSources(event: Extract<StreamEvent, { type: "sources" }>) {
  return { sources: event.sources, images: readChatImages(event.images, event.sources) };
}
export function retryInput(conversation: Conversation) {
  const last = conversation.messages.findLastIndex((message) => message.role === "user");
  if (last < 0) return null;
  return {
    base: { ...conversation, messages: conversation.messages.slice(0, last) },
    text: conversation.messages[last].content,
  };
}
