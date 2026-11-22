// TV4 · Share link tests use fake transport/interaction only.
import assert from "node:assert/strict";
import test from "node:test";
import type { ChatInputCommandInteraction, InteractionEditReplyOptions } from "discord.js";
import { createAskCommand } from "../src/commands/ask.ts";
import { createApiClient } from "../src/api/client.ts";
import { loadWebUrl } from "../src/config.ts";

const id = "11111111-1111-4111-8111-111111111111";
const mid = "22222222-2222-4222-8222-222222222222";
const share = { token: "s".repeat(43), expires_at: "2099-01-01T00:00:00Z" };
const answer = {
  conversation_id: id,
  message_id: mid,
  answer: "Câu trả lời đầy đủ.",
  sources: [],
  grounded: false,
  latency_ms: 1,
};

test("share creation validates target IDs and sends only the service-authenticated request", async () => {
  let calls = 0;
  const api = createApiClient(
    { baseUrl: "http://test/api/v1", serviceToken: "private-test-service" },
    {
      fetcher: async (url, init) => {
        calls++;
        assert.equal(url, "http://test/api/v1/answer-shares");
        assert.equal(new Headers(init?.headers).get("X-Service-Token"), "private-test-service");
        assert.deepEqual(JSON.parse(String(init?.body)), { conversation_id: id, message_id: mid });
        return Response.json(share);
      },
    },
  );
  assert.deepEqual(await api.createAnswerShare(id, mid), share);
  await assert.rejects(api.createAnswerShare("bad", mid));
  assert.equal(calls, 1);
  const bad = createApiClient(
    { baseUrl: "http://test/api/v1" },
    { fetcher: async () => Response.json({ ...share, token: "../private" }) },
  );
  await assert.rejects(bad.createAnswerShare(id, mid));
});

test("web origin validation prevents credentials, unexpected paths, query and non-HTTP links", () => {
  assert.equal(loadWebUrl({ WEB_URL: "https://web.test/" }), "https://web.test");
  for (const url of [
    "javascript:alert(1)",
    "https://u:p@web.test",
    "https://web.test/?key=private",
    "https://web.test/#private",
    "https://web.test/path",
  ])
    assert.equal(loadWebUrl({ WEB_URL: url }), undefined);
});

test("ask links the specific answer via fragment and keeps the answer if share service fails", async () => {
  for (const fails of [false, true]) {
    const replies: InteractionEditReplyOptions[] = [];
    const command = createAskCommand(async () => answer, {
      webUrl: "https://web.test",
      createShare: async (conversation, message) => {
        assert.equal(conversation, id);
        assert.equal(message, mid);
        if (fails) throw new Error("PRIVATE_PROVIDER_DETAIL");
        return share;
      },
    });
    await command.execute({
      user: { id: "test-user" },
      channelId: "test-channel",
      channel: { isThread: () => false },
      options: { getString: () => "Câu hỏi" },
      deferReply: async () => {},
      editReply: async (reply: InteractionEditReplyOptions) => {
        replies.push(reply);
      },
    } as unknown as ChatInputCommandInteraction);
    assert.equal(replies.length, 1);
    const payload = JSON.parse(JSON.stringify(replies[0]));
    assert.equal(payload.embeds[0].description, answer.answer);
    assert.doesNotMatch(JSON.stringify(payload), /PRIVATE_PROVIDER_DETAIL|private-test-service/);
    if (!fails) assert.equal(payload.components[0].components[0].url, `https://web.test/answer#${share.token}`);
    else assert.deepEqual(payload.components, []);
  }
});
