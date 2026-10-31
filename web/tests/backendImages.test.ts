// Backend image contract → parser → shared message patch → storage/render. No LLM calls.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { readChatImages } from "../src/api/images.ts";
import { chat, getConversation } from "../src/api/client.ts";
import { replyEvents } from "../src/api/chat.ts";
import { answerSources } from "../src/hooks/chatState.ts";
import { readConversations, saveConversations } from "../src/lib/storage.ts";
import { backendIllustrations } from "../src/components/chat/answerMedia.ts";
import type { Conversation } from "../src/api/types";

const source = { index: 2, title: "Bloodhound's Fang", url: "https://eldenring.wiki.gg/wiki/Bloodhound%27s_Fang" };
const image = {
  id: "a".repeat(64),
  url: `/api/v1/images/${"a".repeat(64)}`,
  source_url: source.url,
  source_indices: [2],
  alt: "Ảnh thanh kiếm",
  caption: "Chú thích từ dữ liệu",
  attribution: null,
  license: null,
  license_status: "unknown_review_required",
  game_scope: "elden_ring",
  release_scope: "unknown",
};
const response = {
  conversation_id: "11111111-1111-4111-8111-111111111111",
  message_id: "22222222-2222-4222-8222-222222222222",
  answer: "Bloodhound's Fang [2].",
  sources: [source],
  images: [image],
  grounded: true,
  latency_ms: 1,
};
const request = { message: "Bloodhound's Fang?", channel: "web" as const };

test("optional media preserves metadata, limits/deduplicates and only accepts cited local image IDs", () => {
  assert.deepEqual(readChatImages(undefined, [source]), []);
  assert.deepEqual(readChatImages(null, [source]), []);
  assert.deepEqual(readChatImages([image], [source]), [image]);
  assert.deepEqual(readChatImages([image, image], [source]), [image]);
  assert.deepEqual(readChatImages([image], []), []);
  const entries = Array.from({ length: 4 }, (_, i) => ({
    ...image,
    id: String(i).repeat(64),
    url: `/api/v1/images/${String(i).repeat(64)}`,
  }));
  assert.equal(readChatImages(entries, [source]).length, 3);
  for (const bad of [
    null,
    { ...image, id: "not-hash" },
    { ...image, url: "https://tracker.example/a.png" },
    { ...image, url: "/api/v1/images/../../secret" },
    { ...image, url: "data:image/svg+xml,test" },
    { ...image, source_url: "javascript:alert(1)" },
    { ...image, source_url: "https://name:password@example.org" },
    { ...image, file_page_url: "//tracker.example/image" },
    { ...image, source_indices: [] },
    { ...image, source_indices: [1] },
    { ...image, source_indices: [2, 3] },
    { ...image, caption: { html: "unsafe" } },
  ])
    assert.deepEqual(readChatImages([bad], [source]), [], JSON.stringify(bad));
});

test("JSON and SSE retain the same server images in the sources event and message state", async (t) => {
  for (const mode of ["api", "api-stream"] as const) {
    const done = {
      conversation_id: response.conversation_id,
      message_id: response.message_id,
      grounded: true,
      latency_ms: 1,
    };
    const sse = `event: token\ndata: ${JSON.stringify({ token: response.answer })}\n\nevent: sources\ndata: ${JSON.stringify({ sources: response.sources, images: response.images })}\n\nevent: done\ndata: ${JSON.stringify(done)}\n\n`;
    const mock = t.mock.method(globalThis, "fetch", async () =>
      mode === "api"
        ? Response.json(response)
        : new Response(sse, { headers: { "Content-Type": "text/event-stream" } }),
    );
    const events = [];
    for await (const event of replyEvents(request, mode, new AbortController().signal)) events.push(event);
    const sources = events.find((event) => event.type === "sources")!;
    assert.equal(sources.type, "sources");
    if (sources.type === "sources") assert.deepEqual(answerSources(sources), { sources: [source], images: [image] });
    assert.equal(events.at(-1)?.type, "done");
    mock.mock.restore();
  }
});

test("bad optional images do not break JSON text or server conversation history", async (t) => {
  const mock = t.mock.method(globalThis, "fetch", async () =>
    Response.json({ ...response, images: [{ ...image, url: "javascript:alert(1)" }] }),
  );
  const answer = await chat(request);
  assert.equal(answer.answer, response.answer);
  assert.deepEqual(answer.images, []);
  mock.mock.restore();
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({
      id: response.conversation_id,
      channel: "web",
      created_at: "2026-10-31",
      messages: [
        {
          id: response.message_id,
          role: "assistant",
          content: response.answer,
          sources: [source],
          images: [image],
          grounded: true,
          created_at: "2026-10-31",
        },
      ],
    }),
  );
  assert.deepEqual((await getConversation(response.conversation_id)).messages[0].images, [image]);
});

test("browser history round-trips server images and reads legacy conversations without media", (t) => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  let stored = "[]";
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: () => stored,
      setItem: (_key: string, value: string) => {
        stored = value;
      },
    },
  });
  t.after(() => {
    if (descriptor) Object.defineProperty(globalThis, "localStorage", descriptor);
    else Reflect.deleteProperty(globalThis, "localStorage");
  });
  const conversation: Conversation = {
    id: "local",
    title: "Test",
    mode: "api",
    serverId: response.conversation_id,
    updatedAt: "2026-10-31",
    messages: [
      { id: "answer", role: "assistant", content: response.answer, sources: [source], images: [image], grounded: true },
    ],
  };
  assert.equal(saveConversations([conversation]), true);
  assert.deepEqual(readConversations(), [conversation]);
  stored = JSON.stringify([
    {
      ...conversation,
      messages: [{ ...conversation.messages[0], images: [{ ...image, url: "//tracker.example/image" }] }],
    },
  ]);
  assert.deepEqual(readConversations()[0].messages[0].images, []);
  stored = JSON.stringify([
    { ...conversation, messages: [{ id: "old", role: "assistant", content: "Old answer", sources: [] }] },
  ]);
  assert.equal(readConversations()[0].messages[0].images, undefined);
});

test("backend adapter uses metadata/citations without guessing entity kind or approving unknown rights", () => {
  const [result] = backendIllustrations([image], [source]);
  assert.equal(result.kind, "related");
  assert.equal(result.src, image.url);
  assert.equal(result.source.url, source.url);
  assert.equal(result.alt, image.alt);
  assert.match(result.source.label, /\[2\]/);
  assert.match(result.source.credit, /chưa được xác minh/);
  assert.equal(
    backendIllustrations([{ ...image, alt: null, caption: null }], [source])[0].alt,
    `Ảnh từ nguồn ${source.title}`,
  );
});

test("normal chat renders real backend images after completion without fixture props", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: MessageList } = await server.ssrLoadModule("/src/components/chat/MessageList.tsx");
    const message = {
      id: "answer",
      role: "assistant",
      content: response.answer,
      grounded: true,
      sources: [source],
      images: [image],
    };
    const render = (patch = {}) =>
      renderToStaticMarkup(
        createElement(MessageList, { messages: [{ ...message, ...patch }], busy: false, demo: false }),
      );
    const markup = render();
    assert.match(markup, new RegExp(`src="${image.url}"`));
    assert.match(markup, /Ảnh từ nguồn trích dẫn/);
    assert.match(markup, /Chú thích từ dữ liệu/);
    assert.match(markup, /citation-link/);
    assert.match(markup, /Nguồn ảnh \[2\]/);
    assert.doesNotMatch(markup, /fixture-character|preview-answer/);
    for (const patch of [{ incomplete: true }, { role: "user" }, { grounded: false }, { images: [] }])
      assert.doesNotMatch(render(patch), /answer-illustrations/);
    assert.doesNotMatch(render({ images: [{ ...image, url: "javascript:alert(1)" }] }), /answer-illustrations/);
  } finally {
    await server.close();
  }
});
