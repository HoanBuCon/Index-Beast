// Gọi POST /api/v1/chat với X-Service-Token, X-Request-ID; external_ref = discord:thread:<id> / discord:channel:<id>:<user-hash>.
// Phụ trách: TV4 · [S2] Bot /ask gọi API

import type {
  ChatRequest,
  ChatResponse,
  ConversationOut,
  FeedbackRequest,
  StreamEvent,
  AnswerShareCreated,
  GuildChannel,
  HealthResult,
  MemoryClearResult,
} from "./types.ts";
import { isSnowflake, isSource, isUuid, MAX_MESSAGE_CHARS, MAX_FEEDBACK_CHARS } from "./types.ts";
import { loadApiConfig } from "../config.ts";

export class ApiError extends Error {
  status: number;
  retryAfter?: string;
  code?: string;
  constructor(message: string, status = 0, retryAfter?: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
    this.code = code;
  }
}

// Thông điệp hạn mức ngày dài bất thường là dấu hiệu thân không đáng tin; Discord giới hạn 2000 ký tự.
const MAX_QUOTA_MESSAGE_CHARS = 500;

// Đọc thân JSON của 429 an toàn: lỗi parse/đọc -> bỏ qua. Chỉ trả quotaMessage cho code quota_exceeded.
async function readRateLimitBody(response: Response): Promise<{ code?: string; quotaMessage?: string }> {
  try {
    const data: unknown = JSON.parse(await response.text());
    if (!data || typeof data !== "object" || Array.isArray(data)) return {};
    const { code, message } = data as Record<string, unknown>;
    if (code !== "quota_exceeded" && code !== "rate_limited") return {};
    const text = typeof message === "string" ? message.trim() : "";
    return {
      code,
      quotaMessage: code === "quota_exceeded" && text && [...text].length <= MAX_QUOTA_MESSAGE_CHARS ? text : undefined,
    };
  } catch {
    await response.body?.cancel().catch(() => {});
    return {};
  }
}

function validateQuestion(body: ChatRequest) {
  if (typeof body.message !== "string" || !body.message.trim() || [...body.message.trim()].length > MAX_MESSAGE_CHARS) {
    throw new ApiError(`Câu hỏi cần có từ 1 đến ${MAX_MESSAGE_CHARS} ký tự.`, 422);
  }
  if (
    !["web", "discord"].includes(body.channel) ||
    (body.conversation_id != null && !isUuid(body.conversation_id)) ||
    (body.external_ref != null && [...body.external_ref].length > 128)
  ) {
    throw new ApiError("Thông tin hội thoại không hợp lệ.", 422);
  }
  if (body.guild_id != null && !isSnowflake(body.guild_id)) throw new ApiError("Mã server không hợp lệ.", 422);
}

export type ApiClient = ReturnType<typeof createApiClient>;

// Sao chép và thích nghi client công khai của web: URL tuyệt đối, service token và fetch tiêm được cho test.
// Không import web/, không sửa OpenAPI; không tự retry POST để tránh gửi câu hỏi hai lần.
export function createApiClient(
  config: ReturnType<typeof loadApiConfig> = loadApiConfig(),
  {
    fetcher = fetch,
    // Lớn hơn CHAT_TIMEOUT_SECONDS (45 s) của backend: backend báo 504 trước, bot không bỏ cuộc khi API còn chạy.
    timeoutMs = 60_000,
    requestId,
  }: { fetcher?: typeof fetch; timeoutMs?: number; requestId?: string } = {},
) {
  if (!Number.isInteger(timeoutMs) || timeoutMs <= 0) throw new Error("Timeout API phải là số nguyên dương.");
  if (requestId !== undefined && !isUuid(requestId)) throw new Error("Request ID phải là UUID.");
  function friendly(error: unknown): Error {
    if (error instanceof ApiError) return error;
    if (error instanceof Error && error.name === "TimeoutError")
      return new ApiError("Dịch vụ trả lời quá lâu. Vui lòng thử lại sau.", 408);
    if (error instanceof Error && error.name === "AbortError") return new ApiError("Đã hủy yêu cầu.", 499);
    if (error instanceof TypeError) return new ApiError("Không kết nối được dịch vụ. Vui lòng thử lại sau.");
    // Không đưa raw lỗi fetch/SDK ra Discord.
    return new ApiError("Dữ liệu API không hợp lệ hoặc kết nối bị ngắt. Vui lòng thử lại.", 502);
  }
  async function safe<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      throw friendly(error);
    }
  }
  async function request(path: string, init: RequestInit = {}, acceptStatuses: number[] = []) {
    const response = await fetcher(`${config.baseUrl}${path}`, {
      ...init,
      signal: init.signal
        ? AbortSignal.any([init.signal, AbortSignal.timeout(timeoutMs)])
        : AbortSignal.timeout(timeoutMs),
      redirect: "error",
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": requestId ?? crypto.randomUUID(),
        ...(config.serviceToken ? { "X-Service-Token": config.serviceToken } : {}),
        ...init.headers,
      },
    });
    if (!response.ok && !acceptStatuses.includes(response.status)) {
      // 429: chỉ tin `message` khi backend báo hết hạn mức ngày (quota_exceeded); còn lại giữ câu cũ.
      let code: string | undefined;
      let quotaMessage: string | undefined;
      if (response.status === 429) {
        ({ code, quotaMessage } = await readRateLimitBody(response));
      }
      const message =
        response.status === 429
          ? (quotaMessage ?? "Bạn đang gửi quá nhanh. Vui lòng đợi trước khi thử lại.")
          : response.status === 409
            ? "Server đã bật tối đa số kênh cho phép (50). Hãy tắt bớt kênh trước."
            : response.status === 404
              ? "Không tìm thấy hội thoại hoặc chức năng API. Thử tạo cuộc trò chuyện mới hoặc kiểm tra backend."
              : response.status === 422
                ? "Dữ liệu gửi lên không hợp lệ. Kiểm tra nội dung và độ dài câu hỏi."
                : response.status === 401 || response.status === 403
                  ? "Không có quyền truy cập. Kiểm tra cấu hình dịch vụ của bot."
                  : "Không kết nối được dịch vụ. Vui lòng thử lại sau.";
      // Thân 429 đã đọc xong (stream đóng); các mã khác hủy stream, không đọc nội dung backend.
      await response.body?.cancel().catch(() => {});
      throw new ApiError(message, response.status, response.headers.get("Retry-After") ?? undefined, code);
    }
    return response;
  }
  async function chat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
    validateQuestion(body);
    // S2: JSON /chat độc lập với SSE. Timeout áp dụng cả khi đọc body phản hồi.
    const timeout = AbortSignal.timeout(timeoutMs);
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
  async function* parseSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<{ event: string; data: string }> {
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
  async function* chatStream(body: ChatRequest, signal: AbortSignal): AsyncGenerator<StreamEvent> {
    validateQuestion(body);
    const response = await request("/chat/stream", { method: "POST", body: JSON.stringify(body), signal });
    if (!response.body || !response.headers.get("Content-Type")?.includes("text/event-stream")) {
      await response.body?.cancel().catch(() => {});
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
        if (!Array.isArray(data.sources) || !data.sources.every(isSource))
          throw new Error("Dữ liệu nguồn không hợp lệ.");
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
  async function sendFeedback(messageId: string, rating: number, reason: string) {
    if (!isUuid(messageId) || (rating !== 1 && rating !== -1) || [...reason].length > MAX_FEEDBACK_CHARS) {
      throw new Error("Phản hồi không hợp lệ: kiểm tra mã câu trả lời, đánh giá và độ dài lý do.");
    }
    const body: FeedbackRequest = { message_id: messageId, rating, reason };
    const response = await request("/feedback", { method: "POST", body: JSON.stringify(body) });
    if (response.status !== 204) throw new ApiError("API phản hồi chưa khớp hợp đồng.", 502);
  }
  async function getConversation(id: string, signal?: AbortSignal): Promise<ConversationOut> {
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

  async function createAnswerShare(conversationId: string, messageId: string): Promise<AnswerShareCreated> {
    if (!isUuid(conversationId) || !isUuid(messageId)) throw new Error("Mã câu trả lời không hợp lệ.");
    const response = await request("/answer-shares", {
      method: "POST",
      body: JSON.stringify({ conversation_id: conversationId, message_id: messageId }),
      signal: AbortSignal.timeout(5000),
    });
    const data = await response.json();
    if (
      !data ||
      typeof data.token !== "string" ||
      !/^[A-Za-z0-9_-]{43}$/.test(data.token) ||
      typeof data.expires_at !== "string" ||
      !Number.isFinite(Date.parse(data.expires_at))
    )
      throw new Error("Dữ liệu link chia sẻ không hợp lệ.");
    return { token: data.token, expires_at: data.expires_at };
  }

  // --- /discord/guilds/{guild_id}: chỉ nhận service token; bot tự kiểm quyền admin trước khi gọi ghi/xóa. ---
  const guildPath = (guildId: string) => {
    if (!isSnowflake(guildId)) throw new ApiError("Mã server không hợp lệ.", 422);
    return `/discord/guilds/${guildId}`;
  };
  const channelPath = (guildId: string, channelId: string) => {
    if (!isSnowflake(channelId)) throw new ApiError("Mã kênh không hợp lệ.", 422);
    return `${guildPath(guildId)}/channels/${channelId}`;
  };
  const isCount = (value: unknown): value is number => Number.isInteger(value) && Number(value) >= 0;
  async function listGuildChannels(guildId: string): Promise<string[]> {
    const data = await (await request(`${guildPath(guildId)}/channels`)).json();
    if (!Array.isArray(data?.channels) || !data.channels.every((c: GuildChannel) => isSnowflake(c?.channel_id)))
      throw new Error("Dữ liệu kênh không hợp lệ.");
    return data.channels.map((c: GuildChannel) => c.channel_id);
  }
  async function enableGuildChannel(guildId: string, channelId: string): Promise<void> {
    const data = await (await request(channelPath(guildId, channelId), { method: "PUT" })).json();
    if (data?.channel_id !== channelId) throw new Error("Dữ liệu kênh không hợp lệ.");
  }
  async function deleteChannels(path: string): Promise<number> {
    const data = await (await request(path, { method: "DELETE" })).json();
    if (!isCount(data?.deleted)) throw new Error("Dữ liệu kênh không hợp lệ.");
    return data.deleted;
  }
  async function clearMemory(
    guildId: string,
    target: { scope: "all" } | { scope: "user"; userHash: string },
  ): Promise<MemoryClearResult> {
    if (target.scope === "user" && !/^[0-9a-f]{64}$/.test(target.userHash))
      throw new ApiError("Mã người dùng không hợp lệ.", 422);
    const body = target.scope === "all" ? { scope: "all" } : { scope: "user", user_hash: target.userHash };
    const data = await (
      await request(`${guildPath(guildId)}/memory/clear`, { method: "POST", body: JSON.stringify(body) })
    ).json();
    if (!isCount(data?.conversations) || !isCount(data?.threads_kept) || !isCount(data?.vector_conversations))
      throw new Error("Dữ liệu xóa ký ức không hợp lệ.");
    return data;
  }
  // 503 vẫn có thân {status:"degraded", checks}; các lỗi khác (mạng, 401...) ném ApiError.
  async function health(): Promise<HealthResult> {
    const started = performance.now();
    const response = await request("/health", { signal: AbortSignal.timeout(5000) }, [503]);
    const data = await response.json().catch(() => undefined);
    const rtt = Math.round(performance.now() - started);
    if (!["ok", "degraded"].includes(data?.status) || !data.checks || typeof data.checks !== "object")
      throw new Error("Dữ liệu health không hợp lệ.");
    return { status: data.status, checks: data.checks, http_status: response.status, rtt_ms: rtt };
  }

  return {
    listGuildChannels: (guildId: string) => safe(() => listGuildChannels(guildId)),
    enableGuildChannel: (guildId: string, channelId: string) => safe(() => enableGuildChannel(guildId, channelId)),
    disableGuildChannel: (guildId: string, channelId: string) =>
      safe(() => deleteChannels(channelPath(guildId, channelId))),
    disableAllGuildChannels: (guildId: string) => safe(() => deleteChannels(`${guildPath(guildId)}/channels`)),
    clearMemory: (guildId: string, target: Parameters<typeof clearMemory>[1]) =>
      safe(() => clearMemory(guildId, target)),
    health: () => safe(health),
    createAnswerShare: (conversationId: string, messageId: string) =>
      safe(() => createAnswerShare(conversationId, messageId)),
    chat: (body: ChatRequest, signal?: AbortSignal) => safe(() => chat(body, signal)),
    sendFeedback: (messageId: string, rating: number, reason: string) =>
      safe(() => sendFeedback(messageId, rating, reason)),
    getConversation: (id: string, signal?: AbortSignal) => safe(() => getConversation(id, signal)),
    async *chatStream(body: ChatRequest, signal: AbortSignal): AsyncGenerator<StreamEvent> {
      try {
        yield* chatStream(body, signal);
      } catch (error) {
        throw friendly(error);
      }
    },
  };
}
