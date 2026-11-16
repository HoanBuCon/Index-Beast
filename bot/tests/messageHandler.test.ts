// TV4 · S5: trả lời tin nhắn (mention và kênh /setup) với cache, rate limit và API giả.
import assert from "node:assert/strict";
import test from "node:test";
import { createMessageHandler } from "../src/handlers/message.ts";
import type { ChatRequest } from "../src/api/types.ts";
import { ApiError } from "../src/api/client.ts";
import { BOT_ID, CHANNEL, GUILD, fakeMessage } from "./helpers.ts";
import type { FakeMessageOptions } from "./helpers.ts";

const answer = {
  conversation_id: "12345678-1234-4234-8234-123456789012",
  message_id: "23456789-1234-4234-8234-123456789012",
  answer: "Trả lời [1].",
  grounded: true,
  latency_ms: 5,
  sources: [{ index: 1, title: "Marika", url: "https://example.test/Marika" }],
};
function setup(enabled: string[] = [CHANNEL], verdicts?: ("allow" | "warn" | "deny")[]) {
  const bodies: ChatRequest[] = [];
  const handler = createMessageHandler({
    cache: { has: async (_g, c) => enabled.includes(c) },
    limiter: { check: () => verdicts?.shift() ?? "allow" },
    chat: async (body) => {
      bodies.push(body);
      return answer;
    },
  });
  async function run(opts: FakeMessageOptions) {
    const mock = fakeMessage(opts);
    await handler(mock.value);
    return mock;
  }
  return { bodies, run };
}

test("enabled channel: answers without /ask, sends guild_id and per-user external_ref, mentions disabled", async () => {
  const { bodies, run } = setup();
  const mock = await run({ content: "  Marika là ai?  " });
  assert.equal(bodies.length, 1);
  assert.equal(bodies[0].message, "Marika là ai?");
  assert.equal(bodies[0].guild_id, GUILD);
  assert.equal(bodies[0].channel, "discord");
  assert.match(bodies[0].external_ref!, new RegExp(`^discord:channel:${CHANNEL}:[0-9a-f]{64}$`));
  assert.deepEqual(mock.replies[0].allowedMentions, { parse: [], repliedUser: false });
  assert.equal((mock.replies[0].embeds as unknown[]).length, 1);
});

test("channel not enabled and not mentioned: ignored", async () => {
  const { bodies, run } = setup([]);
  const mock = await run({ content: "xin chào" });
  assert.deepEqual([bodies.length, mock.replies.length], [0, 0]);
});

test("mention works anywhere, strips the bot mention and ignores @everyone/role pings by option", async () => {
  const { bodies, run } = setup([]);
  await run({ content: `<@${BOT_ID}> Marika là ai?`, mentioned: true });
  await run({ content: `<@!${BOT_ID}>   Radahn?`, mentioned: true });
  assert.deepEqual(
    bodies.map((b) => b.message),
    ["Marika là ai?", "Radahn?"],
  );
});

test("mention with no question gets a hint; empty auto-channel message is skipped silently", async () => {
  const { bodies, run } = setup();
  const hint = await run({ content: `<@${BOT_ID}>`, mentioned: true });
  assert.equal(hint.replies.length, 1);
  assert.match(String(hint.replies[0].content), /muốn hỏi/);
  const blank = await run({ content: "   " });
  assert.equal(blank.replies.length, 0);
  assert.equal(bodies.length, 0);
});

test("ignores bots, webhooks, system messages and DMs", async () => {
  const { bodies, run } = setup();
  for (const opts of [
    { content: "hi", bot: true },
    { content: "hi", webhookId: "99" },
    { content: "hi", system: true },
    { content: "hi", guildId: null, mentioned: true },
  ]) {
    await run(opts);
  }
  assert.equal(bodies.length, 0);
});

test("threads under an enabled channel share its enablement and use the thread external_ref", async () => {
  const { bodies, run } = setup([CHANNEL]);
  await run({ content: "Hỏi tiếp?", channelId: "777777777777777777", thread: { parentId: CHANNEL } });
  assert.equal(bodies[0].external_ref, "discord:thread:777777777777777777");
});

test("rate limit: warns once, then stays silent, never reaching the API", async () => {
  const { bodies, run } = setup([CHANNEL], ["allow", "warn", "deny"]);
  await run({ content: "một" });
  const warned = await run({ content: "hai" });
  const denied = await run({ content: "ba" });
  assert.equal(bodies.length, 1);
  assert.match(String(warned.replies[0].content), /quá nhanh/);
  assert.equal(denied.replies.length, 0);
});

test("oversized text is skipped in auto channels but reported to a mention", async () => {
  const { bodies, run } = setup();
  const long = "x".repeat(2001);
  assert.equal((await run({ content: long })).replies.length, 0);
  const mentioned = await run({ content: `<@${BOT_ID}> ${long}`, mentioned: true });
  assert.match(String(mentioned.replies[0].content), /2000/);
  assert.equal(bodies.length, 0);
});

test("API failures become friendly replies and hide raw errors; cache failure is silent", async () => {
  for (const error of [new ApiError("Dịch vụ trả lời quá lâu.", 408), new Error("PRIVATE_SECRET")]) {
    const handler = createMessageHandler({
      cache: { has: async () => true },
      limiter: { check: () => "allow" },
      chat: async () => {
        throw error;
      },
    });
    const mock = fakeMessage({ content: "Marika?" });
    await handler(mock.value);
    assert.ok(!String(mock.replies[0].content).includes("PRIVATE_SECRET"));
    if (error instanceof ApiError) assert.equal(mock.replies[0].content, error.message);
  }
  const down = createMessageHandler({
    cache: {
      has: async () => {
        throw new Error("down");
      },
    },
    limiter: { check: () => "allow" },
    chat: async () => assert.fail("must not chat"),
  });
  const mock = fakeMessage({ content: "Marika?" });
  await down(mock.value);
  assert.equal(mock.replies.length, 0);
});

test("long answers continue in follow-up messages without pings", async () => {
  const handler = createMessageHandler({
    cache: { has: async () => true },
    limiter: { check: () => "allow" },
    chat: async () => ({ ...answer, answer: "Cốt truyện 😀\n".repeat(900) }),
  });
  const mock = fakeMessage({ content: "Kể đi" });
  await handler(mock.value);
  assert.ok(mock.sent.length > 0);
  for (const payload of mock.sent) assert.deepEqual(payload.allowedMentions, { parse: [] });
});
