// State một cuộc chat: gửi câu hỏi, nhận token/sources/done, huỷ giữa chừng.
// Phụ trách: TV4 · [S3] Web streaming SSE

import { useEffect, useRef, useState } from "react";
import type { Conversation } from "../api/types";
import { ApiError } from "../api/client";
import { replyEvents } from "../api/chat";
import type { ChatOptions } from "../api/chat";
import { createUuid } from "../lib/uuid.ts";
// S2 bổ sung JSON /chat, giữ nguyên luồng sự kiện SSE đã có cho S3.
export function useChatStream(update: (conversation: Conversation) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function send(base: Conversation, text: string, options: ChatOptions = {}) {
    if (controller.current) return;
    const abort = new AbortController();
    controller.current = abort;
    setBusy(true);
    setError("");
    const answerId = createUuid();
    let current: Conversation = {
      ...base,
      title: base.messages.length ? base.title : text.slice(0, 60),
      updatedAt: new Date().toISOString(),
      messages: [
        ...base.messages,
        { id: createUuid(), role: "user", content: text, sources: [] },
        { id: answerId, role: "assistant", content: "", sources: [], incomplete: true },
      ],
    };
    update(current);
    const changeAnswer = (patch: Partial<Conversation["messages"][number]>) => {
      current = { ...current, messages: current.messages.map((m) => (m.id === answerId ? { ...m, ...patch } : m)) };
      update(current);
    };
    try {
      const request = {
        conversation_id: base.serverId,
        message: text,
        channel: "web" as const,
        options: { lang: "vi" as const, spoilers: true },
      };
      const stream = replyEvents(request, base.mode, abort.signal, options);
      let content = "";
      for await (const event of stream) {
        if (event.type === "token") {
          content += event.token;
          changeAnswer({ content });
        } else if (event.type === "sources") changeAnswer({ sources: event.sources });
        else if (event.type === "done") {
          current = { ...current, serverId: event.data.conversation_id };
          changeAnswer({ serverId: event.data.message_id, grounded: event.data.grounded, incomplete: false });
        }
      }
    } catch (cause) {
      if (abort.signal.aborted) setError("Đã dừng. Câu trả lời chưa hoàn tất.");
      else if (cause instanceof Error && cause.name === "TimeoutError")
        setError("API phản hồi quá lâu. Vui lòng thử lại.");
      else if (cause instanceof ApiError)
        setError(cause.message + (cause.retryAfter ? ` Thử lại sau ${cause.retryAfter}.` : ""));
      else
        setError(
          cause instanceof Error && cause.message !== "Failed to fetch"
            ? cause.message
            : "Không kết nối được API. Kiểm tra backend rồi thử lại.",
        );
    } finally {
      controller.current = null;
      setBusy(false);
    }
  }
  return { send, busy, error, stop: () => controller.current?.abort(), clearError: () => setError("") };
}
