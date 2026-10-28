// fetch tới /api/v1; chatStream đọc SSE qua fetch + ReadableStream; sendFeedback; xử lý lỗi 429.
// Phụ trách: TV4 · [S2] File api.ts viết tay · [S3] Web streaming SSE

import type { AdminStats, ChatRequest, ChatResponse, ConversationOut, FeedbackRequest, StreamEvent } from "./types";
import { isSource, isUuid, MAX_MESSAGE_CHARS, MAX_FEEDBACK_CHARS } from "./types.ts";

export class ApiError extends Error {
  status: number;
  retryAfter?: string;
  constructor(message: string, status: number, retryAfter?: string) {
    super(message);
    this.status = status;
    this.retryAfter = retryAfter;
  }
}
async function request(path: string, init: RequestInit = {}) {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID(), ...init.headers },
  });
  if (!response.ok) {
    const message =
      response.status === 429
        ? "Bạn đang gửi quá nhanh. Vui lòng đợi trước khi thử lại."
        : response.status === 404
          ? "Không tìm thấy hội thoại hoặc chức năng API. Thử tạo cuộc trò chuyện mới hoặc kiểm tra backend."
          : response.status === 422
            ? "Dữ liệu gửi lên không hợp lệ. Kiểm tra nội dung và độ dài câu hỏi."
            : response.status === 401 || response.status === 403
              ? "Không có quyền truy cập. Kiểm tra token quản trị."
              : "Không kết nối được dịch vụ. Vui lòng thử lại sau.";
    throw new ApiError(message, response.status, response.headers.get("Retry-After") ?? undefined);
  }
  return response;
}
export async function chat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  if (!body.message.trim() || [...body.message.trim()].length > MAX_MESSAGE_CHARS) {
    throw new Error(`Câu hỏi cần có từ 1 đến ${MAX_MESSAGE_CHARS} ký tự.`);
  }
  // S2: JSON /chat độc lập với SSE. Timeout áp dụng cả khi đọc body phản hồi.
  const timeout = AbortSignal.timeout(30_000);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  const response = await request("/chat", { method: "POST", body: JSON.stringify(body), signal: combined });
  let data: unknown;
  try {
    data = await response.json();
  } catch (error) {
    if (combined.aborted) throw combined.reason;
    throw new Error("API trả về JSON không hợp lệ.");
  }
  if (!data || typeof data !== "object") throw new Error("Dữ liệu câu trả lời không hợp lệ.");
  const result = data as Record<string, unknown>;
  if (
    !isUuid(result.conversation_id) ||
    !isUuid(result.message_id) ||
    typeof result.answer !== "string" ||
    !result.answer.trim() ||
    typeof result.grounded !== "boolean" ||
    !Array.isArray(result.sources) ||
    !result.sources.every(isSource) ||
    typeof result.latency_ms !== "number" ||
    !Number.isFinite(result.latency_ms) ||
    result.latency_ms < 0
  ) {
    throw new Error("Dữ liệu câu trả lời không hợp lệ.");
  }
  return data as ChatResponse;
}

// SSE có thể tách giữa ký tự UTF-8, giữa CR/LF hoặc nhiều dòng data; không parse theo từng network chunk.
export async function* parseSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<{ event: string; data: string }> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "message";
  let data: string[] = [];
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      let match: RegExpExecArray | null;
      while ((match = /\r\n|\r|\n/.exec(buffer))) {
        if (!chunk.done && match[0] === "\r" && match.index === buffer.length - 1) break;
        const line = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        if (line === "") {
          if (data.length) yield { event, data: data.join("\n") };
          event = "message";
          data = [];
        } else if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (chunk.done) break;
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
export async function* chatStream(body: ChatRequest, signal: AbortSignal): AsyncGenerator<StreamEvent> {
  const response = await request("/chat/stream", { method: "POST", body: JSON.stringify(body), signal });
  if (!response.body || !response.headers.get("Content-Type")?.includes("text/event-stream")) {
    throw new Error("Dịch vụ chưa trả về luồng SSE hợp lệ.");
  }
  let complete = false;
  for await (const frame of parseSSE(response.body)) {
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(frame.data);
    } catch {
      throw new Error("Dữ liệu stream không hợp lệ.");
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Dữ liệu stream không hợp lệ.");
    const type = frame.event === "message" ? data.type : frame.event;
    if (type === "token" && typeof data.token === "string") yield { type, token: data.token };
    else if (type === "status" && typeof data.status === "string") yield { type, status: data.status };
    else if (type === "sources") {
      if (!Array.isArray(data.sources) || !data.sources.every(isSource)) throw new Error("Dữ liệu nguồn không hợp lệ.");
      yield { type, sources: data.sources };
    } else if (type === "error") throw new Error("Dịch vụ gặp lỗi khi sinh câu trả lời. Vui lòng thử lại.");
    else if (type === "done") {
      if (
        !isUuid(data.conversation_id) ||
        !isUuid(data.message_id) ||
        typeof data.grounded !== "boolean" ||
        typeof data.latency_ms !== "number" ||
        !Number.isFinite(data.latency_ms) ||
        data.latency_ms < 0
      ) {
        throw new Error("Thiếu thông tin hoàn tất câu trả lời.");
      }
      complete = true;
      yield {
        type,
        data: {
          conversation_id: data.conversation_id,
          message_id: data.message_id,
          grounded: data.grounded,
          latency_ms: data.latency_ms,
        },
      };
      break;
    }
  }
  if (!complete) throw new Error("Kết nối bị ngắt trước khi câu trả lời hoàn tất.");
}
export async function sendFeedback(messageId: string, rating: number, reason: string) {
  if (!isUuid(messageId) || (rating !== 1 && rating !== -1) || [...reason].length > MAX_FEEDBACK_CHARS) {
    throw new Error("Phản hồi không hợp lệ: kiểm tra mã câu trả lời, đánh giá và độ dài lý do.");
  }
  const body: FeedbackRequest = { message_id: messageId, rating, reason };
  await request("/feedback", { method: "POST", body: JSON.stringify(body) });
}
export async function getConversation(id: string, signal?: AbortSignal): Promise<ConversationOut> {
  if (!isUuid(id)) throw new Error("Mã hội thoại không hợp lệ.");
  const data = await (await request(`/conversations/${encodeURIComponent(id)}`, { signal })).json();
  if (
    !isUuid(data?.id) ||
    !["web", "discord"].includes(data.channel) ||
    typeof data.created_at !== "string" ||
    !Array.isArray(data.messages) ||
    !data.messages.every(
      (m: ConversationOut["messages"][number]) =>
        m &&
        isUuid(m.id) &&
        ["user", "assistant"].includes(m.role) &&
        typeof m.content === "string" &&
        Array.isArray(m.sources) &&
        m.sources.every(isSource) &&
        (m.grounded == null || typeof m.grounded === "boolean") &&
        typeof m.created_at === "string",
    )
  )
    throw new Error("Dữ liệu hội thoại không hợp lệ.");
  return data;
}
// Token admin chỉ giữ trong state của trang, không ghi vào localStorage hay bundle.
export async function getAdminStats(token: string, signal?: AbortSignal): Promise<AdminStats> {
  const data = await (await request("/admin/stats", { headers: { "X-Admin-Token": token }, signal })).json();
  if (
    !data ||
    !Array.isArray(data.conversations) ||
    !Array.isArray(data.feedback) ||
    !Array.isArray(data.ingestion_jobs) ||
    !Array.isArray(data.eval_runs) ||
    !data.conversations.every(
      (c: AdminStats["conversations"][number]) =>
        c && typeof c.id === "string" && typeof c.title === "string" && typeof c.created_at === "string",
    ) ||
    !data.feedback.every(
      (f: AdminStats["feedback"][number]) =>
        f &&
        typeof f.message_id === "string" &&
        typeof f.rating === "number" &&
        (f.reason === undefined || typeof f.reason === "string"),
    ) ||
    !data.ingestion_jobs.every(
      (j: AdminStats["ingestion_jobs"][number]) =>
        j && typeof j.id === "string" && typeof j.status === "string" && typeof j.pages_ok === "number",
    ) ||
    !data.eval_runs.every(
      (r: AdminStats["eval_runs"][number]) =>
        r &&
        typeof r.id === "string" &&
        r.metrics &&
        typeof r.metrics === "object" &&
        Object.values(r.metrics).every((v) => typeof v === "number"),
    )
  ) {
    throw new Error("Dữ liệu quản trị chưa khớp hợp đồng frontend. Cần xác nhận API với nhóm backend.");
  }
  return data;
}
export async function getTrace(token: string, messageId: string, signal?: AbortSignal): Promise<unknown> {
  return (
    await request(`/admin/trace/${encodeURIComponent(messageId)}`, { headers: { "X-Admin-Token": token }, signal })
  ).json();
}
