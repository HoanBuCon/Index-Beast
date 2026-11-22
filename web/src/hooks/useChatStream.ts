// State một cuộc chat: gửi câu hỏi, nhận token/sources/done, huỷ giữa chừng.
// Phụ trách: TV4 · [S3] Web streaming SSE

import { useEffect, useRef, useState } from "react";
import type { Conversation } from "../api/types";
import { ApiError, describeApiError } from "../api/client";
import { replyEvents } from "../api/chat";
import type { ChatOptions } from "../api/chat";
import { createUuid } from "../lib/uuid.ts";
import { answerSources } from "./chatState.ts";
// turnId chỉ thuộc đầu vào của hook (dùng lại ID lượt khi thử lại), không đi vào option của transport.
export interface SendOptions extends ChatOptions {
  turnId?: string;
}
// S2 bổ sung JSON /chat, giữ nguyên luồng sự kiện SSE đã có cho S3.
// identity: định danh người xem (id tài khoản hoặc "guest"); đổi định danh thì hủy luồng đang chạy và bỏ cập nhật muộn.
export function useChatStream(update: (conversation: Conversation) => void, identity = "guest") {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    generation.current += 1;
    controller.current?.abort();
  }, [identity]);
  async function send(base: Conversation, text: string, options: SendOptions = {}) {
    if (controller.current) return false;
    const abort = new AbortController();
    controller.current = abort;
    const mine = generation.current;
    const emit = (conversation: Conversation) => {
      if (mine === generation.current) update(conversation);
    };
    setBusy(true);
    setError("");
    const answerId = createUuid();
    const userId = options.turnId ?? createUuid();
    let completed = false;
    let current: Conversation = {
      ...base,
      title: base.messages.length ? base.title : text.slice(0, 60),
      updatedAt: new Date().toISOString(),
      messages: [
        ...base.messages,
        { id: userId, role: "user", content: text, sources: [], clarificationId: options.clarificationId },
        { id: answerId, role: "assistant", content: "", sources: [], incomplete: true },
      ],
    };
    emit(current);
    const changeAnswer = (patch: Partial<Conversation["messages"][number]>) => {
      current = { ...current, messages: current.messages.map((m) => (m.id === answerId ? { ...m, ...patch } : m)) };
      emit(current);
    };
    try {
      const request = {
        conversation_id: base.serverId,
        ...(base.serverToken ? { conversation_token: base.serverToken } : {}),
        turn_id: userId,
        message: text,
        channel: "web" as const,
        options: { lang: "vi" as const },
      };
      const stream = replyEvents(request, base.mode, abort.signal, options);
      let content = "";
      for await (const event of stream) {
        if (event.type === "token") {
          content += event.token;
          changeAnswer({ content });
        } else if (event.type === "sources")
          changeAnswer({ ...answerSources(event), clarification: event.clarification ?? null });
        else if (event.type === "done") {
          completed = true;
          current = {
            ...current,
            serverId: event.data.conversation_id,
            ...(event.data.conversation_token ? { serverToken: event.data.conversation_token } : {}),
          };
          changeAnswer({ serverId: event.data.message_id, grounded: event.data.grounded, incomplete: false });
        }
      }
      if (!completed) throw new Error("Câu trả lời chưa hoàn tất. Vui lòng thử lại.");
    } catch (cause) {
      if (abort.signal.aborted) setError("Đã dừng. Câu trả lời chưa hoàn tất.");
      else if (cause instanceof Error && cause.name === "TimeoutError")
        setError("API phản hồi quá lâu. Vui lòng thử lại.");
      else if (cause instanceof ApiError) setError(describeApiError(cause));
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
    return completed;
  }
  return { send, busy, error, stop: () => controller.current?.abort(), clearError: () => setError("") };
}
