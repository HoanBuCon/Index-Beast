// TV4 · Hỏi tiếp: Discord/API giả, không Gateway hoặc LLM thật.
import assert from "node:assert/strict";
import test from "node:test";
import { ChannelType } from "discord.js";
import type { ButtonInteraction, MessageCreateOptions } from "discord.js";
import { createFollowupThreads, FollowupError } from "../src/interactions/followup.ts";
import type { ChatRequest } from "../src/api/types.ts";

const origin = {
  guildId: "100",
  channelId: "200",
  question: "Marika là ai?",
  answer: "Marika có quan hệ với Radagon.",
};
const response = {
  conversation_id: "conversation",
  message_id: "message",
  answer: "Trả lời",
  sources: [],
  grounded: false,
  latency_ms: 1,
};
function button(id: string, threadId = "400") {
  const calls: string[] = [];
  const replies: string[] = [];
  const thread = {
    id: threadId,
    guildId: "100",
    archived: false,
    locked: false,
    isThread: () => true,
    send: async (payload: MessageCreateOptions) => {
      calls.push("send");
      assert.deepEqual(payload.allowedMentions, { parse: [] });
    },
  };
  const value = {
    customId: id,
    guildId: "100",
    channelId: "200",
    user: { id: "300" },
    channel: { type: ChannelType.GuildText },
    message: {
      startThread: async (opts: { autoArchiveDuration: number }) => {
        calls.push("create");
        assert.equal(opts.autoArchiveDuration, 60);
        return thread;
      },
    },
    client: { channels: { fetch: async () => thread } },
    deferReply: async () => {
      calls.push("defer");
    },
    editReply: async (payload: { content: string }) => {
      replies.push(payload.content);
    },
  };
  return { value: value as unknown as ButtonInteraction, calls, replies, thread };
}
function request(message = "Ông ta là ai?"): ChatRequest {
  return { message, channel: "discord", guild_id: "100", external_ref: "discord:thread:400" };
}

test("button defers first, creates only one thread even for concurrent clicks, then reuses it", async () => {
  const flow = createFollowupThreads();
  const mock = button(flow.button(origin).data.custom_id!);
  await Promise.all([flow.handle(mock.value), flow.handle(mock.value)]);
  assert.equal(mock.calls[0], "defer");
  assert.equal(mock.calls.filter((c) => c === "create").length, 1);
  assert.match(mock.replies[0], /<#400>/);
  await flow.handle(mock.value);
  assert.equal(mock.calls.filter((c) => c === "create").length, 1);
  assert.equal(flow.has("100", "400"), true);
  assert.equal(flow.has("other-guild", "400"), false);
});

test("rejects unknown/expired/cross-channel buttons and archived threads without creating a replacement", async () => {
  let now = 0;
  const flow = createFollowupThreads({ now: () => now });
  const id = flow.button(origin).data.custom_id!;
  const wrong = button(id);
  wrong.value.channelId = "other";
  await flow.handle(wrong.value);
  assert.ok(!wrong.calls.includes("create"));
  const wrongGuild = button(id);
  wrongGuild.value.guildId = "other-guild";
  await flow.handle(wrongGuild.value);
  assert.ok(!wrongGuild.calls.includes("create"));
  await flow.handle(button("followup:invalid").value);
  const mock = button(id);
  await flow.handle(mock.value);
  mock.thread.archived = true;
  await flow.handle(mock.value);
  assert.match(mock.replies.at(-1)!, /lưu trữ|hết hạn/);
  now = 24 * 60 * 60 * 1000 + 1;
  const expired = button(id);
  await flow.handle(expired.value);
  assert.ok(!expired.calls.includes("create"));
  assert.match(expired.replies[0], /hết hạn/);
});

test("seeds only the first successful thread turn, preserves identity/options, and isolates other threads", async () => {
  const flow = createFollowupThreads();
  await flow.handle(button(flow.button(origin).data.custom_id!).value);
  const bodies: ChatRequest[] = [];
  const chat = async (body: ChatRequest) => {
    bodies.push(body);
    return response;
  };
  await assert.rejects(
    flow.chat(request(), async () => {
      throw new Error("offline");
    }),
  );
  await flow.chat(request(), chat);
  assert.match(bodies[0].message, /Marika là ai/);
  assert.match(bodies[0].message, /Radagon/);
  assert.match(bodies[0].message, /Ông ta là ai/);
  assert.equal(bodies[0].external_ref, "discord:thread:400");
  assert.equal(bodies[0].conversation_id, undefined);
  await flow.chat(request("Hỏi tiếp nữa"), chat);
  assert.equal(bodies[1].message, "Hỏi tiếp nữa");
  const other = { ...request(), external_ref: "discord:thread:999" };
  await flow.chat(other, chat);
  assert.deepEqual(bodies[2], other);
  await flow.handle(
    button(flow.button({ ...origin, question: "Godrick?", answer: "Godrick được ghép." }).data.custom_id!, "999").value,
  );
  await flow.chat(other, chat);
  assert.match(bodies[3].message, /Godrick/);
  assert.ok(!bodies[3].message.includes("Marika"));
  await flow.chat(request("Cuộc trò chuyện trước vẫn riêng biệt"), chat);
  assert.equal(bodies[4].message, "Cuộc trò chuyện trước vẫn riêng biệt");
});

test("bounds Unicode context, blocks overlapping turns, expires inactive threads, and clears guild state", async () => {
  let now = 0;
  const flow = createFollowupThreads({ now: () => now });
  await flow.handle(button(flow.button({ ...origin, answer: "😀".repeat(4000) }).data.custom_id!).value);
  let release!: () => void;
  const pending = flow.chat(request(), async (body) => {
    assert.ok([...body.message].length <= 2000);
    assert.ok(!body.message.includes("\uFFFD"));
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    return response;
  });
  await assert.rejects(
    flow.chat(request(), async () => response),
    FollowupError,
  );
  release();
  await pending;
  now = 60 * 60 * 1000 + 1;
  await assert.rejects(
    flow.chat(request(), async () => response),
    /hết hạn/,
  );
  flow.clearGuild("100");
  assert.equal(flow.has("100", "400"), false);
});

test("missing thread permissions is a friendly retryable error and does not leak SDK details", async () => {
  const flow = createFollowupThreads();
  const mock = button(flow.button(origin).data.custom_id!);
  const start = mock.value.message.startThread;
  mock.value.message.startThread = async () => {
    throw new Error("PRIVATE_DETAIL");
  };
  await flow.handle(mock.value);
  assert.match(mock.replies[0], /quyền/);
  assert.ok(!mock.replies[0].includes("PRIVATE_DETAIL"));
  mock.value.message.startThread = start;
  await flow.handle(mock.value);
  assert.match(mock.replies.at(-1)!, /<#400>/);
});

test("first oversized followup is refused without calling backend, and a shorter retry still has context", async () => {
  const flow = createFollowupThreads();
  await flow.handle(button(flow.button(origin).data.custom_id!).value);
  await assert.rejects(
    flow.chat(request("a".repeat(2000)), async () => {
      assert.fail("must not call backend");
    }),
    /rút gọn/,
  );
  await flow.chat(request(), async (body) => {
    assert.match(body.message, /Marika/);
    return response;
  });
});

test("bounded cache evicts old buttons; clearing a guild invalidates its buttons while keeping another guild", async () => {
  const flow = createFollowupThreads({ limit: 2 });
  const old = flow.button(origin).data.custom_id!;
  const current = flow.button(origin).data.custom_id!;
  const other = flow.button({ ...origin, guildId: "101" }).data.custom_id!;
  const expired = button(old);
  await flow.handle(expired.value);
  assert.match(expired.replies[0], /hết hạn/);
  flow.clearGuild("100");
  const cleared = button(current);
  await flow.handle(cleared.value);
  assert.match(cleared.replies[0], /hết hạn/);
  const different = button(other);
  await flow.handle(different.value);
  assert.match(different.replies[0], /không thuộc kênh/);
});

test("clear all during thread creation cannot restore the deleted opening context", async () => {
  const flow = createFollowupThreads();
  const mock = button(flow.button(origin).data.custom_id!);
  let finish!: (thread: unknown) => void;
  mock.value.message.startThread = () =>
    new Promise((resolve) => {
      finish = resolve as (thread: unknown) => void;
    });
  const pending = flow.handle(mock.value);
  // handle() acknowledges first, then reaches the Discord REST request.
  await Promise.resolve();
  flow.clearGuild("100");
  finish(mock.thread);
  await pending;
  assert.equal(flow.has("100", "400"), false);
  assert.match(mock.replies.at(-1)!, /xóa|hết hạn/);
});
