// TV4 · S2: mock Discord interaction và API; không đăng ký lệnh hoặc kết nối Gateway thật.
import assert from "node:assert/strict";
import test from "node:test";
import type { ChatInputCommandInteraction, InteractionEditReplyOptions } from "discord.js";
import { createAskCommand } from "../src/commands/ask.ts";
import { commands } from "../src/commands/index.ts";
import { ApiError } from "../src/api/client.ts";
import { answerEmbed } from "../src/utils/format.ts";

const response = {
  conversation_id: "12345678-1234-4234-8234-123456789012",
  message_id: "23456789-1234-4234-8234-123456789012",
  answer: "Câu trả lời [1].",
  grounded: true,
  latency_ms: 12,
  sources: [{ index: 1, title: "Marika", url: "https://example.test/Marika" }],
};
function interaction(question: string, thread = false) {
  const calls: string[] = [];
  const replies: InteractionEditReplyOptions[] = [];
  const value = {
    id: "333333333333333333",
    user: { id: "111111111111111111" },
    channelId: "222222222222222222",
    channel: { isThread: () => thread },
    options: { getString: () => question },
    deferReply: async () => {
      calls.push("defer");
    },
    editReply: async (payload: InteractionEditReplyOptions) => {
      calls.push("edit");
      replies.push(payload);
    },
  };
  return { value: value as unknown as ChatInputCommandInteraction, calls, replies };
}

test("registry keeps ping and exposes ask with a required bounded question", () => {
  assert.ok(commands.has("ping"));
  const data = commands.get("ask")!.data.toJSON();
  assert.equal(data.name, "ask");
  assert.equal(data.options?.[0].name, "question");
  assert.equal(data.options?.[0].required, true);
});

test("ask defers before API, hashes user reference and edits an embed with sources", async () => {
  const mock = interaction("  Marika là ai?  ");
  const command = createAskCommand(async (body) => {
    assert.deepEqual(mock.calls, ["defer"]);
    mock.calls.push("api");
    assert.equal(body.message, "Marika là ai?");
    assert.equal(body.channel, "discord");
    assert.match(body.external_ref!, /^discord:channel:222222222222222222:[a-f0-9]{64}$/);
    assert.ok(!body.external_ref!.includes("111111111111111111"));
    return response;
  });
  await command.execute(mock.value);
  assert.deepEqual(mock.calls, ["defer", "api", "edit"]);
  assert.deepEqual(mock.replies[0].allowedMentions, { parse: [] });
  const embed = JSON.parse(JSON.stringify(mock.replies[0].embeds?.[0]));
  assert.equal(embed.description, response.answer);
  assert.ok(embed.fields[0].value.includes(response.sources[0].url));
});

test("ask thread reference uses channel ID without raw user identity", async () => {
  const mock = interaction("Marika?", true);
  await createAskCommand(async (body) => {
    assert.equal(body.external_ref, "discord:thread:222222222222222222");
    return response;
  }).execute(mock.value);
});

test("blank and oversized questions never call backend", async () => {
  for (const question of ["  ", "x".repeat(2001)]) {
    const mock = interaction(question);
    await createAskCommand(async () => {
      assert.fail("must not fetch");
    }).execute(mock.value);
    assert.match(mock.replies[0].content!, /2000/);
  }
});

test("ask renders friendly API errors and hides unexpected SDK/provider details", async () => {
  for (const error of [new ApiError("Dịch vụ trả lời quá lâu.", 408), new Error("PRIVATE_SECRET")]) {
    const mock = interaction("Marika?");
    await createAskCommand(async () => {
      throw error;
    }).execute(mock.value);
    assert.ok(!mock.replies[0].content!.includes("PRIVATE_SECRET"));
    if (error instanceof ApiError) assert.equal(mock.replies[0].content, error.message);
    assert.deepEqual(mock.calls, ["defer", "edit"]);
  }
});

test("embed stays below Discord limits for long answers and source lists; rejects unsafe links", () => {
  const sources = Array.from({ length: 40 }, (_, i) => ({
    index: i + 1,
    title: "Tên nguồn ".repeat(30),
    url: `https://example.test/${i}`,
  }));
  sources.unshift({ index: 50, title: "Unsafe", url: "javascript:alert(1)" });
  const embed = answerEmbed("Q".repeat(2000), { ...response, answer: "😀".repeat(4000), sources }).toJSON();
  assert.ok(embed.title!.length <= 256);
  assert.ok(embed.description!.length <= 4096);
  assert.ok(!/[\uD800-\uDBFF]…$/.test(embed.description!));
  assert.ok(embed.fields!.every((field) => field.value.length <= 1024));
  assert.ok(!JSON.stringify(embed).includes("javascript:"));
  const total =
    embed.title!.length +
    embed.description!.length +
    (embed.footer?.text.length ?? 0) +
    embed.fields!.reduce((n, f) => n + f.name.length + f.value.length, 0);
  assert.ok(total <= 6000);
  assert.match(embed.footer!.text, /rút gọn/);
});
