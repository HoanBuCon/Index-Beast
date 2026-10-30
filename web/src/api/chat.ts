// Chuyển JSON S2 và SSE S3 về cùng sự kiện để tái sử dụng UI, lịch sử và nguồn.
// Phụ trách: TV4 · [S2] UI chat cơ bản
import type { ChatRequest, Conversation, StreamEvent } from "./types";
import { chat, chatStream } from "./client.ts";
import { demoChat } from "./demo.ts";
import type { DemoScenario } from "./demo";

export interface ChatOptions {
  scenario?: DemoScenario;
}
export async function* replyEvents(
  body: ChatRequest,
  mode: Conversation["mode"],
  signal: AbortSignal,
  options: ChatOptions = {},
): AsyncGenerator<StreamEvent> {
  if (mode === "api-stream") {
    yield* chatStream(body, signal);
    return;
  }
  const reply = mode === "demo" ? await demoChat(body, signal, options.scenario) : await chat(body, signal);
  signal.throwIfAborted();
  yield { type: "token", token: reply.answer };
  yield { type: "sources", sources: reply.sources };
  yield {
    type: "done",
    data: {
      conversation_id: reply.conversation_id,
      message_id: reply.message_id,
      grounded: reply.grounded,
      latency_ms: reply.latency_ms,
    },
  };
}
