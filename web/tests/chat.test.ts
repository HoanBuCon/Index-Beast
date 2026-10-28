// Test luồng JSON S2 bằng fetch giả, không cần backend hoặc secret thật.
// Phụ trách: TV4 · [S2] UI chat cơ bản
import assert from "node:assert/strict";
import test from "node:test";
import { chat, ApiError } from "../src/api/client.ts";
import { replyEvents } from "../src/api/chat.ts";
import { demoChat } from "../src/api/demo.ts";
import { retryInput } from "../src/hooks/chatState.ts";
import type { Conversation } from "../src/api/types";

const request = {
  conversation_id: null,
  message: "Godrick là ai?",
  channel: "web" as const,
  options: { lang: "auto" as const, spoilers: true },
};
const response = {
  conversation_id: "conversation-1",
  message_id: "answer-1",
  answer: "**Câu trả lời mock** [1]",
  sources: [{ index: 1, title: "Nguồn mock", url: "https://example.org" }],
  grounded: true,
};

test("JSON sends POST /chat, body and request ID, then maps answer and sources into UI events", async (t) => {
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.equal(url, "/api/v1/chat");
    assert.equal(init.method, "POST");
    assert.deepEqual(JSON.parse(init.body as string), request);
    assert.ok(new Headers(init.headers).get("X-Request-ID"));
    return Response.json(response);
  });
  const events = [];
  for await (const event of replyEvents(request, "api", new AbortController().signal)) events.push(event);
  assert.deepEqual(events, [
    { type: "token", token: response.answer },
    { type: "sources", sources: response.sources },
    { type: "done", data: { conversation_id: "conversation-1", message_id: "answer-1", grounded: true } },
  ]);
});

test("JSON validates data before render", async (t) => {
  for (const invalid of [
    null,
    {},
    { ...response, answer: " " },
    { ...response, sources: [null] },
    { ...response, latency_ms: -1 },
  ]) {
    const mock = t.mock.method(globalThis, "fetch", async () => Response.json(invalid));
    await assert.rejects(chat(request), /Dữ liệu câu trả lời không hợp lệ/);
    mock.mock.restore();
  }
});

test("non-JSON and provider failures remain errors rather than falling back to demo", async (t) => {
  const mock = t.mock.method(globalThis, "fetch", async () => new Response("<html>not JSON</html>"));
  await assert.rejects(chat(request), /JSON không hợp lệ/);
  mock.mock.restore();
  t.mock.method(globalThis, "fetch", async () => new Response("private details", { status: 500 }));
  await assert.rejects(
    async () => {
      for await (const event of replyEvents(request, "api", new AbortController().signal)) void event;
    },
    (error: unknown) => error instanceof ApiError && error.status === 500 && !error.message.includes("private"),
  );
});

test("cancel aborts an in-flight JSON fetch", async (t) => {
  const abort = new AbortController();
  t.mock.method(
    globalThis,
    "fetch",
    (_url: string, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        const signal = init.signal!;
        signal.addEventListener("abort", () => reject(signal.reason), { once: true });
      }),
  );
  const pending = chat(request, abort.signal);
  abort.abort();
  await assert.rejects(pending, { name: "AbortError" });
});

test("retry retains earlier history and sends the failed question once", async (t) => {
  const conversation: Conversation = {
    id: "local",
    title: "Question",
    mode: "api",
    serverId: "conversation-1",
    updatedAt: "2026-10-28",
    messages: [
      { id: "u1", role: "user", content: "Earlier", sources: [] },
      { id: "a1", role: "assistant", content: "Earlier answer", sources: [] },
      { id: "u2", role: "user", content: request.message, sources: [] },
      { id: "a2", role: "assistant", content: "", sources: [], incomplete: true },
    ],
  };
  const input = retryInput(conversation)!;
  assert.equal(input.text, request.message);
  assert.deepEqual(
    input.base.messages.map((m) => m.id),
    ["u1", "a1"],
  );
  assert.equal(input.base.serverId, "conversation-1");
  assert.equal(conversation.messages.length, 4);
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () =>
    ++calls === 1 ? new Response(null, { status: 503 }) : Response.json(response),
  );
  await assert.rejects(chat(request));
  assert.deepEqual(await chat({ ...request, conversation_id: input.base.serverId }), response);
  assert.equal(calls, 2);
});

test("frontend JSON demo handles success, failure and cancellation without fetch", async (t) => {
  t.mock.method(globalThis, "fetch", () => {
    throw new Error("Demo must not call backend");
  });
  const result = await demoChat(request, new AbortController().signal, "success");
  assert.match(result.answer, /phản hồi JSON minh họa của frontend/);
  assert.equal(result.grounded, false);
  await assert.rejects(demoChat(request, new AbortController().signal, "error"), /Lỗi minh họa/);
  const abort = new AbortController();
  const pending = demoChat(request, abort.signal, "slow");
  abort.abort();
  await assert.rejects(pending, { name: "AbortError" });
});
