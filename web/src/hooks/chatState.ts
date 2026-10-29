// Thử lại thay thế lượt bị lỗi, không nhân đôi câu hỏi trong lịch sử frontend.
// Phụ trách: TV4 · [S2] UI chat cơ bản
import type { Conversation } from "../api/types";
export function retryInput(conversation: Conversation) {
  const last = conversation.messages.findLastIndex((message) => message.role === "user");
  if (last < 0) return null;
  return {
    base: { ...conversation, messages: conversation.messages.slice(0, last) },
    text: conversation.messages[last].content,
  };
}
