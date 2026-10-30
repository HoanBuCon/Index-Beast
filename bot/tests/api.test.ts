// TV4 · S2: test độc lập bằng fetch giả, không đọc .env, không gọi mạng/LLM.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createApiClient, ApiError } from "../src/api/client.ts";
import { loadApiConfig } from "../src/config.ts";
import { MAX_MESSAGE_CHARS, MAX_FEEDBACK_CHARS } from "../src/api/types.ts";

const conversationId = "12345678-1234-4234-8234-123456789012";
const messageId = "23456789-1234-4234-8234-123456789012";
const answer = {
  conversation_id: conversationId,
  message_id: messageId,
  answer: "Câu trả lời [1].",
  grounded: true,
  latency_ms: 12,
  sources: [{ index: 1, title: "Marika", url: "https://example.test/wiki/Marika", section: null, text: null }],
};
const question = { message: "Marika là ai?", channel: "discord" as const };
const config = loadApiConfig({ BOT_API_URL: "http://backend.test:18000" });
const json = (data: unknown) => new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
function client(fetcher: typeof fetch, timeoutMs = 1000) {
  return createApiClient(config, { fetcher, timeoutMs });
}

test("API config supports host/container URL and rejects unsafe or malformed configuration", () => {
  assert.equal(loadApiConfig({}).baseUrl, "http://127.0.0.1:18000/api/v1");
  assert.equal(loadApiConfig({ API_PORT: "19000" }).baseUrl, "http://127.0.0.1:19000/api/v1");
  assert.equal(loadApiConfig({ BOT_API_URL: "http://api:18000/api/v1/" }).baseUrl, "http://api:18000/api/v1");
  for (const url of [
    "file:///tmp/a",
    "http://user:password@api:18000",
    "http://api:18000/wrong",
    "http://api:18000/?token=x",
  ]) {
    assert.throws(() => loadApiConfig({ BOT_API_URL: url }), /BOT_API_URL/);
  }
  assert.throws(() => loadApiConfig({ API_PORT: "65536" }), /API_PORT/);
  assert.equal(loadApiConfig({ API_SERVICE_TOKEN: "change-me" }).serviceToken, undefined);
});

test("bot request limits match checked-in OpenAPI", () => {
  const api = JSON.parse(readFileSync(new URL("../../docs/api/openapi.json", import.meta.url), "utf8"));
  assert.equal(MAX_MESSAGE_CHARS, api.components.schemas.ChatRequest.properties.message.maxLength);
  assert.equal(MAX_FEEDBACK_CHARS, api.components.schemas.FeedbackRequest.properties.reason.anyOf[0].maxLength);
});

test("JSON client posts the contract, absolute URL, UUID request ID and optional service token", async () => {
  const api = createApiClient(
    { ...config, serviceToken: "unit-test-only" },
    {
      fetcher: async (url, init) => {
        assert.equal(url, "http://backend.test:18000/api/v1/chat");
        assert.equal(init?.method, "POST");
        assert.deepEqual(JSON.parse(String(init?.body)), question);
        const headers = new Headers(init?.headers);
        assert.match(headers.get("X-Request-ID")!, /^[0-9a-f-]{36}$/);
        assert.equal(headers.get("X-Service-Token"), "unit-test-only");
        assert.equal(init?.redirect, "error");
        return json(answer);
      },
    },
  );
  assert.deepEqual(await api.chat(question), answer);
});

test("invalid questions fail locally without fetch", async () => {
  let calls = 0;
  const api = client(async () => {
    calls++;
    return json(answer);
  });
  for (const message of ["   ", "a".repeat(2001)]) {
    await assert.rejects(api.chat({ ...question, message }), /2000/);
  }
  await assert.rejects(api.chat({ ...question, conversation_id: "invalid" }), /hội thoại/);
  assert.equal(calls, 0);
});

test("client carries a caller UUID for bot-to-API correlation", async () => {
  const api = createApiClient(config, {
    requestId: messageId,
    fetcher: async (_url, init) => {
      assert.equal(new Headers(init?.headers).get("X-Request-ID"), messageId);
      return json(answer);
    },
  });
  await api.chat(question);
  assert.throws(() => createApiClient(config, { requestId: "bad-id" }), /UUID/);
});

test("HTTP errors preserve status and Retry-After without revealing backend body", async () => {
  for (const status of [401, 403, 404, 422, 429, 500]) {
    const api = client(
      async () => new Response("PRIVATE_PROVIDER_DETAIL", { status, headers: { "Retry-After": "7" } }),
    );
    await assert.rejects(api.chat(question), (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, status);
      assert.equal(error.retryAfter, "7");
      assert.ok(!error.message.includes("PRIVATE_PROVIDER_DETAIL"));
      return true;
    });
  }
});

test("malformed JSON, UUID, latency and sources cannot reach the bot renderer", async () => {
  for (const value of [
    { ...answer, message_id: "x" },
    { ...answer, latency_ms: -1 },
    { ...answer, sources: [null] },
    { ...answer, answer: "" },
  ]) {
    await assert.rejects(client(async () => json(value)).chat(question), ApiError);
  }
  await assert.rejects(client(async () => new Response("not JSON")).chat(question), ApiError);
  await assert.rejects(
    client(async () => {
      throw new TypeError("PRIVATE_TOKEN");
    }).chat(question),
    (error: Error) => !error.message.includes("PRIVATE_TOKEN"),
  );
});

test("timeout and caller cancellation are distinct friendly errors", async () => {
  const blocked: typeof fetch = async (_url, init) =>
    new Promise((_resolve, reject) => {
      const signal = init!.signal!;
      if (signal.aborted) reject(signal.reason);
      else signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    });
  // AbortSignal.timeout không giữ event loop; timer của test được dọn trong finally.
  const keepAlive = setTimeout(() => {}, 1000);
  try {
    await assert.rejects(client(blocked, 15).chat(question), (e: ApiError) => e.status === 408);
    const controller = new AbortController();
    const promise = client(blocked).chat(question, controller.signal);
    controller.abort();
    await assert.rejects(promise, (e: ApiError) => e.status === 499);
  } finally {
    clearTimeout(keepAlive);
  }
});

test("feedback validates before fetch and sends the expected contract", async () => {
  let calls = 0;
  const api = client(async (url, init) => {
    calls++;
    assert.ok(String(url).endsWith("/feedback"));
    assert.deepEqual(JSON.parse(String(init?.body)), { message_id: messageId, rating: -1, reason: "Thiếu nguồn" });
    return new Response(null, { status: 204 });
  });
  await assert.rejects(api.sendFeedback(messageId, 0, ""));
  await assert.rejects(api.sendFeedback(messageId, 1, "x".repeat(501)));
  await api.sendFeedback(messageId, -1, "Thiếu nguồn");
  assert.equal(calls, 1);
});

test("conversation client validates UUID and returned messages", async () => {
  const data = {
    id: conversationId,
    channel: "discord",
    created_at: "2026-10-30T00:00:00Z",
    messages: [
      { id: messageId, role: "assistant", content: "Trả lời", sources: [], created_at: "2026-10-30T00:00:00Z" },
    ],
  };
  assert.deepEqual(await client(async () => json(data)).getConversation(conversationId), data);
  await assert.rejects(client(async () => json(data)).getConversation("bad-id"));
  await assert.rejects(client(async () => json({ ...data, messages: [null] })).getConversation(conversationId));
});

test("SSE tolerates UTF-8 byte/CRLF boundaries and requires a valid done event", async () => {
  const text = `event: token\r\ndata: {"token":"Tiếng Việt"}\r\n\r\nevent: sources\r\ndata: {"sources":[]}\r\n\r\nevent: done\r\ndata: ${JSON.stringify(answer)}\r\n\r\n`;
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  const api = client(
    async () =>
      new Response(
        new ReadableStream({
          pull(controller) {
            if (offset < bytes.length) controller.enqueue(bytes.slice(offset, ++offset));
            else controller.close();
          },
        }),
        { headers: { "Content-Type": "text/event-stream" } },
      ),
  );
  const events = [];
  for await (const event of api.chatStream(question, new AbortController().signal)) events.push(event);
  assert.equal(events[0].type, "token");
  assert.equal(events.at(-1)?.type, "done");
  // Stream có thể đã đóng trước khi reader.cancel; cả đóng và hủy đều phải nhả reader.
  assert.equal(events[0].type === "token" && events[0].token, "Tiếng Việt");
  const partial = client(
    async () =>
      new Response('event: token\ndata: {"token":"x"}\n\n', { headers: { "Content-Type": "text/event-stream" } }),
  );
  await assert.rejects(async () => {
    for await (const _ of partial.chatStream(question, new AbortController().signal)) {
      /* consume */
    }
  });
});

test("stopping SSE early cancels the reader; invalid done/error frames fail", async () => {
  let cancelled = false;
  const api = client(
    async () =>
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('event: token\ndata: {"token":"x"}\n\n'));
          },
          cancel() {
            cancelled = true;
          },
        }),
        { headers: { "Content-Type": "text/event-stream" } },
      ),
  );
  for await (const _ of api.chatStream(question, new AbortController().signal)) break;
  assert.equal(cancelled, true);
  for (const frame of ["event: done\ndata: {}\n\n", 'event: error\ndata: {"message":"PRIVATE_ERROR"}\n\n']) {
    const invalid = client(async () => new Response(frame, { headers: { "Content-Type": "text/event-stream" } }));
    await assert.rejects(
      async () => {
        for await (const _ of invalid.chatStream(question, new AbortController().signal)) {
          /* consume */
        }
      },
      (e: Error) => !e.message.includes("PRIVATE_ERROR"),
    );
  }
});

test("JSON timeout includes response body reads", async () => {
  const api = client(
    async (_url, init) =>
      new Response(
        new ReadableStream({
          start(controller) {
            init!.signal!.addEventListener("abort", () => controller.error(init!.signal!.reason), { once: true });
          },
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    15,
  );
  const keepAlive = setTimeout(() => {}, 1000);
  try {
    await assert.rejects(api.chat(question), (e: ApiError) => e.status === 408);
  } finally {
    clearTimeout(keepAlive);
  }
});
