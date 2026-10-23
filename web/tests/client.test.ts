// SSE phải chịu được chia packet/UTF-8 và báo stream dở dang; không gọi backend thật.
// Phụ trách: TV4 · [S3] Web streaming SSE
import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, chatStream, parseSSE, sendFeedback } from "../src/api/client.ts";

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
  options: { lang: "auto" as const, spoilers: true },
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
      new Response(body('event: done\ndata: {"conversation_id":"c","message_id":"m","grounded":true}\n\n'), {
        headers: { "Content-Type": "text/event-stream" },
      }),
  );
  const events = [];
  for await (const event of chatStream(request, new AbortController().signal)) events.push(event);
  assert.deepEqual(events, [{ type: "done", data: { conversation_id: "c", message_id: "m", grounded: true } }]);
});
test("429 preserves Retry-After without exposing provider body", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("private-provider-error", { status: 429, headers: { "Retry-After": "30" } }),
  );
  await assert.rejects(
    sendFeedback("message", -1, "reason"),
    (error: unknown) =>
      error instanceof ApiError &&
      error.status === 429 &&
      error.retryAfter === "30" &&
      !error.message.includes("private"),
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
