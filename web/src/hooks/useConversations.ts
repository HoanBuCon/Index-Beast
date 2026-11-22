// Danh sách cuộc trò chuyện lưu localStorage (khách).
// Phụ trách: TV4 · [S4] Web: feedback, lịch sử, câu hỏi gợi ý

import { useEffect, useMemo, useState } from "react";
import type { Conversation } from "../api/types";
import { readConversations, saveConversations } from "../lib/storage";
import { viewerConversations } from "../lib/accountData";
import type { Viewer } from "../lib/accountData";
// viewer: chỉ trả về hội thoại khách hoặc của người dùng hiện tại; bản của chủ khác bị xóa khỏi localStorage
// ngay khi auth đã biết (hết phiên, đổi tài khoản). Khi auth đang tải thì chỉ ẩn, chưa xóa.
export function useConversations(viewer: Viewer = { loading: false, userId: null }) {
  const [stored, setConversations] = useState(readConversations);
  const conversations = useMemo(() => viewerConversations(stored, viewer), [stored, viewer.loading, viewer.userId]);
  useEffect(() => {
    if (viewer.loading) return;
    setConversations((previous) => {
      const kept = viewerConversations(previous, viewer);
      return kept.length === previous.length ? previous : kept;
    });
  }, [viewer.loading, viewer.userId]);
  const [storageError, setStorageError] = useState(false);
  useEffect(() => {
    setStorageError(!saveConversations(stored));
  }, [stored]);
  function update(conversation: Conversation) {
    setConversations((previous) => [conversation, ...previous.filter((c) => c.id !== conversation.id)].slice(0, 30));
  }
  function remove(id: string) {
    setConversations((previous) => previous.filter((c) => c.id !== id));
  }
  return { conversations, update, remove, storageError };
}
