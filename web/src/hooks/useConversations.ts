// Danh sách cuộc trò chuyện lưu localStorage (khách).
// Phụ trách: TV4 · [S4] Web: feedback, lịch sử, câu hỏi gợi ý

import { useEffect, useState } from "react";
import type { Conversation } from "../api/types";
import { readConversations, saveConversations } from "../lib/storage";
export function useConversations() {
  const [conversations, setConversations] = useState(readConversations);
  const [storageError, setStorageError] = useState(false);
  useEffect(() => {
    setStorageError(!saveConversations(conversations));
  }, [conversations]);
  function update(conversation: Conversation) {
    setConversations((previous) => [conversation, ...previous.filter((c) => c.id !== conversation.id)].slice(0, 30));
  }
  function remove(id: string) {
    setConversations((previous) => previous.filter((c) => c.id !== id));
  }
  return { conversations, update, remove, storageError };
}
