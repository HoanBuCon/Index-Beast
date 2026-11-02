// TV4 · S2: ràng buộc frontend được đối chiếu với OpenAPI của TV1, chỉ đọc hợp đồng.
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { chat } from "../src/api/client.ts";
import { isSource, MAX_MESSAGE_CHARS, MAX_FEEDBACK_CHARS } from "../src/api/types.ts";

test("frontend limits match the checked-in OpenAPI v1 contract", () => {
  const document = JSON.parse(readFileSync(new URL("../../docs/api/openapi.json", import.meta.url), "utf8"));
  const schemas = document.components.schemas;
  assert.equal(MAX_MESSAGE_CHARS, schemas.ChatRequest.properties.message.maxLength);
  const reason = schemas.FeedbackRequest.properties.reason;
  assert.equal(MAX_FEEDBACK_CHARS, reason.anyOf.find((s: { type: string }) => s.type === "string").maxLength);
  assert.ok(schemas.ChatResponse.required.includes("latency_ms"));
  assert.ok(schemas.Source.properties.section.anyOf.some((s: { type: string }) => s.type === "null"));
  for (const route of ["/chat", "/chat/stream", "/feedback", "/conversations/{conversation_id}"]) {
    assert.ok(document.paths[`/api/v1${route}`]);
  }
});
test("source accepts API null fields but rejects malformed fields", () => {
  const source = {
    index: 1,
    title: "Ranni",
    url: "https://eldenring.wiki.gg/wiki/Ranni_the_Witch",
    section: null,
    text: null,
    origin: "corpus",
  };
  assert.ok(isSource(source));
  assert.equal(isSource({ ...source, text: 42 }), false);
  assert.equal(isSource({ ...source, origin: null }), false);
});
test("invalid question is rejected locally without calling API", async (t) => {
  t.mock.method(globalThis, "fetch", () => {
    throw new Error("must not send invalid text");
  });
  for (const message of [" ", "a".repeat(MAX_MESSAGE_CHARS + 1)]) {
    await assert.rejects(chat({ message, channel: "web" }), /2000/);
  }
});
