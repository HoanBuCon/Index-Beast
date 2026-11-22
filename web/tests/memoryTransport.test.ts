// TV3 additive capability transport only; no UI redesign or real backend calls.
import assert from "node:assert/strict";
import test from "node:test";
import { replyEvents } from "../src/api/chat.ts";
import { getConversation, sendFeedback } from "../src/api/client.ts";
import { readConversations, saveConversations } from "../src/lib/storage.ts";
import type { Conversation } from "../src/api/types";

const cid = "11111111-1111-4111-8111-111111111111";
const mid = "22222222-2222-4222-8222-222222222222";
const token = "synthetic-capability-for-offline-tests-123456";
const request = {
  message: "Ranni là ai?",
  channel: "web" as const,
  conversation_id: cid,
  conversation_token: token,
  turn_id: mid,
};
const response = {
  conversation_id: cid,
  conversation_token: token,
  message_id: mid,
  answer: "Ranni [1].",
  sources: [],
  grounded: false,
  latency_ms: 1,
};

test("JSON capability survives adapter and protected history/feedback use a header", async (t) => {
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.ok(!url.includes(token));
    if (url.endsWith("/chat")) {
      const body = JSON.parse(init.body as string);
      assert.equal(body.conversation_token, token);
      assert.equal(body.turn_id, mid);
      return Response.json(response);
    }
    assert.equal(new Headers(init.headers).get("X-Conversation-Token"), token);
    if (url.endsWith("/feedback")) return new Response(null, { status: 204 });
    return Response.json({ id: cid, channel: "web", created_at: "2026-11-06", messages: [] });
  });
  const events = [];
  for await (const event of replyEvents(request, "api", new AbortController().signal)) events.push(event);
  assert.equal(events.at(-1)?.type, "done");
  const done = events.at(-1);
  assert.ok(done?.type === "done");
  assert.equal(done.data.conversation_token, token);
  assert.equal((await getConversation(cid, undefined, token)).id, cid);
  await sendFeedback(mid, 1, "", token);
});

test("SSE done preserves capability and rejects malformed optional tokens", async (t) => {
  const mock = t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(`event: done\ndata: ${JSON.stringify(response)}\n\n`, {
        headers: { "Content-Type": "text/event-stream" },
      }),
  );
  const events = [];
  for await (const event of replyEvents(request, "api-stream", new AbortController().signal)) events.push(event);
  const done = events.at(-1);
  assert.ok(done?.type === "done");
  assert.equal(done.data.conversation_token, token);
  mock.mock.restore();
  t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(`event: done\ndata: ${JSON.stringify({ ...response, conversation_token: "?" })}\n\n`, {
        headers: { "Content-Type": "text/event-stream" },
      }),
  );
  await assert.rejects(async () => {
    for await (const event of replyEvents(request, "api-stream", new AbortController().signal)) void event;
  });
});

test("local storage restores scoped capability while still accepting legacy conversations", (t) => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    },
  });
  t.after(() => {
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else Reflect.deleteProperty(globalThis, "localStorage");
  });
  const conversation: Conversation = {
    id: "browser",
    serverId: cid,
    serverToken: token,
    title: "Ranni",
    mode: "api-stream",
    messages: [],
    updatedAt: "2026-11-06",
  };
  assert.ok(saveConversations([conversation]));
  assert.equal(readConversations()[0].serverToken, token);
  const { serverToken: _, ...legacy } = conversation;
  assert.ok(saveConversations([legacy]));
  assert.equal(readConversations().length, 1);
  assert.ok(saveConversations([{ ...conversation, serverToken: "?" }]));
  assert.equal(readConversations().length, 0);
});
