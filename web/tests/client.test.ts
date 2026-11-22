// SSE phải chịu được chia packet/UTF-8 và báo stream dở dang; không gọi backend thật.
// Phụ trách: TV4 · [S3] Web streaming SSE
import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, chatStream, describeApiError, parseSSE, sendFeedback } from "../src/api/client.ts";

function body(text: string, split = false) {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream<Uint8Array>({
    start(controller) {
      if (split) for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
      else controller.enqueue(bytes);
      controller.close();
    },
  });
}
test("SSE preserves Vietnamese across bytes and CRLF boundaries", async () => {
  const frames = [];
  for await (const frame of parseSSE(
    body(': keepalive\r\nevent: token\r\ndata: {"token":"Truyền thuyết"}\r\n\r\nevent: done\ndata: {}\n\n', true),
  ))
    frames.push(frame);
  assert.deepEqual(frames, [
    { event: "token", data: '{"token":"Truyền thuyết"}' },
    { event: "done", data: "{}" },
  ]);
});
test("SSE joins data lines and ignores unterminated event", async () => {
  const frames = [];
  for await (const frame of parseSSE(body("data: first\ndata: second\n\ndata: unfinished"))) frames.push(frame);
  assert.deepEqual(frames, [{ event: "message", data: "first\nsecond" }]);
});
const request = {
  conversation_id: null,
  message: "Lore?",
  channel: "web" as const,
  options: { lang: "auto" as const },
};
test("chat rejects partial output without done", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(body('event: token\ndata: {"token":"Partial"}\n\n'), {
        headers: { "Content-Type": "text/event-stream" },
      }),
  );
  const tokens = [];
  await assert.rejects(async () => {
    for await (const event of chatStream(request, new AbortController().signal)) tokens.push(event);
  }, /Kết nối bị ngắt/);
  assert.deepEqual(tokens, [{ type: "token", token: "Partial" }]);
});
test("done validates message and conversation IDs", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(
        body(
          'event: done\ndata: {"conversation_id":"11111111-1111-4111-8111-111111111111","message_id":"22222222-2222-4222-8222-222222222222","grounded":true,"latency_ms":1}\n\n',
        ),
        {
          headers: { "Content-Type": "text/event-stream" },
        },
      ),
  );
  const events = [];
  for await (const event of chatStream(request, new AbortController().signal)) events.push(event);
  assert.deepEqual(events, [
    {
      type: "done",
      data: {
        conversation_id: "11111111-1111-4111-8111-111111111111",
        message_id: "22222222-2222-4222-8222-222222222222",
        grounded: true,
        latency_ms: 1,
      },
    },
  ]);
});
test("429 preserves Retry-After without exposing provider body", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("private-provider-error", { status: 429, headers: { "Retry-After": "30" } }),
  );
  await assert.rejects(
    sendFeedback("22222222-2222-4222-8222-222222222222", -1, "reason"),
    (error: unknown) =>
      error instanceof ApiError &&
      error.status === 429 &&
      error.retryAfter === "30" &&
      !error.message.includes("private"),
  );
});

const quotaMessage = "Đã hết lượt hỏi của khách hôm nay. Đăng nhập bằng Discord để hỏi 30 câu mỗi ngày.";
function quotaResponse(code: string, message: string) {
  return new Response(JSON.stringify({ code, message, request_id: "r" }), {
    status: 429,
    headers: { "Retry-After": "41000", "Content-Type": "application/json" },
  });
}
test("429 quota_exceeded passes server message and code, without retry suffix", async (t) => {
  t.mock.method(globalThis, "fetch", async () => quotaResponse("quota_exceeded", quotaMessage));
  await assert.rejects(
    sendFeedback("22222222-2222-4222-8222-222222222222", -1, "reason"),
    (error: unknown) =>
      error instanceof ApiError &&
      error.message === quotaMessage &&
      error.code === "quota_exceeded" &&
      describeApiError(error) === quotaMessage,
  );
});
test("429 quota_exceeded also applies to the stream request", async (t) => {
  t.mock.method(globalThis, "fetch", async () => quotaResponse("quota_exceeded", quotaMessage));
  await assert.rejects(
    async () => {
      for await (const event of chatStream(request, new AbortController().signal)) void event;
    },
    (error: unknown) => error instanceof ApiError && error.message === quotaMessage,
  );
});
test("429 with non-JSON body falls back to the default text", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("<html>429</html>", { status: 429 }));
  await assert.rejects(
    sendFeedback("22222222-2222-4222-8222-222222222222", -1, "reason"),
    (error: unknown) => error instanceof ApiError && /quá nhanh/.test(error.message) && error.code === undefined,
  );
});
test("429 rate_limited keeps the default text and shows seconds", async (t) => {
  t.mock.method(globalThis, "fetch", async () => quotaResponse("rate_limited", "bất kỳ"));
  await assert.rejects(
    sendFeedback("22222222-2222-4222-8222-222222222222", -1, "reason"),
    (error: unknown) =>
      error instanceof ApiError &&
      /quá nhanh/.test(error.message) &&
      describeApiError(new ApiError(error.message, 429, "12", "rate_limited")).endsWith("Thử lại sau 12 giây."),
  );
});

test("malformed sources fail before UI render", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(body('event: sources\ndata: {"sources":[null]}\n\n'), {
        headers: { "Content-Type": "text/event-stream" },
      }),
  );
  await assert.rejects(async () => {
    for await (const event of chatStream(request, new AbortController().signal)) void event;
  }, /nguồn không hợp lệ/);
});

test("stopping SSE consumer releases its reader", async () => {
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("data: hello\n\n"));
    },
    cancel() {
      cancelled = true;
    },
  });
  for await (const frame of parseSSE(stream)) {
    assert.equal(frame.data, "hello");
    break;
  }
  assert.equal(cancelled, true);
});
