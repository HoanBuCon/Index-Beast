import assert from "node:assert/strict";
import test from "node:test";
import { readClarification } from "../src/api/clarification.ts";
import { replyEvents } from "../src/api/chat.ts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const clarification = {
  id: "33333333-3333-4333-8333-333333333333",
  status: "pending",
  question: "PvE or PvP?",
  expires_at: "2099-01-01T00:00:00Z",
  fields: [{ key: "goal", label: "Goal", input_type: "choice", options: ["PvE", "PvP"] }],
};

test("clarification is optional, bounded and rejects malformed metadata", () => {
  assert.equal(readClarification(undefined), null);
  assert.deepEqual(readClarification(clarification), clarification);
  for (const change of [{ id: "wrong" }, { fields: [] }, { fields: [1] }, { expires_at: "invalid" }])
    assert.throws(() => readClarification({ ...clarification, ...change }));
});

test("JSON carries structured question and follow-up ID without changing old requests", async (t) => {
  const response = {
    conversation_id: "11111111-1111-4111-8111-111111111111",
    message_id: "22222222-2222-4222-8222-222222222222",
    answer: "PvE or PvP?",
    sources: [],
    grounded: false,
    latency_ms: 1,
    clarification,
  };
  let sent: Record<string, unknown> = {};
  t.mock.method(globalThis, "fetch", async (_url: string, init: RequestInit) => {
    sent = JSON.parse(String(init.body));
    return new Response(JSON.stringify(response), { status: 200 });
  });
  const frames = [];
  for await (const event of replyEvents({ message: "PvE", channel: "web" }, "api", new AbortController().signal, {
    clarificationId: clarification.id,
    webSearch: "off",
  }))
    frames.push(event);
  assert.equal(sent.clarification_id, clarification.id);
  const source = frames.find((frame) => frame.type === "sources");
  assert.deepEqual(source?.type === "sources" ? source.clarification : null, clarification);
  assert.equal(frames.at(-1)?.type, "done");
});

test("temporary question card renders choices, a continue button and expiration state", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: "custom" });
  try {
    const { default: Form } = await server.ssrLoadModule("/src/components/chat/ClarificationForm.tsx");
    const { default: MessageList } = await server.ssrLoadModule("/src/components/chat/MessageList.tsx");
    const html = renderToStaticMarkup(createElement(Form, { question: clarification, disabled: false, onAnswer() {} }));
    assert.match(html, /<select/);
    assert.match(html, /PvE/);
    assert.match(html, /Tiếp tục/);
    const expired = renderToStaticMarkup(
      createElement(Form, {
        question: { ...clarification, expires_at: "2000-01-01T00:00:00Z" },
        disabled: false,
        onAnswer() {},
      }),
    );
    assert.match(expired, /Đã hết hạn/);
    // Rebase integration: preserve TV4's removal of source/feedback panels and TV3's active question.
    const message = renderToStaticMarkup(
      createElement(MessageList, {
        messages: [
          {
            id: "reply",
            role: "assistant",
            content: "Yêu cầu bổ sung [1].",
            sources: [{ index: 1, title: "Test source", url: "https://example.test/source" }],
            serverId: "22222222-2222-4222-8222-222222222222",
            clarification,
          },
        ],
        busy: false,
        demo: false,
        onClarification() {},
      }),
    );
    assert.match(message, /Tiếp tục/);
    assert.match(message, /class="citation-link"/);
    assert.doesNotMatch(message, /Dấu vết trong kho lưu trữ|Câu trả lời có hữu ích/);
  } finally {
    await server.close();
  }
});
