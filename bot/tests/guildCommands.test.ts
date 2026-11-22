// TV4 · S5: /setup, /clear, /ping, /help đồng bộ registry; interaction và API giả.
import assert from "node:assert/strict";
import test from "node:test";
import { createClearCommand, clearSummary } from "../src/commands/clear.ts";
import { commands } from "../src/commands/index.ts";
import { createPingCommand } from "../src/commands/ping.ts";
import { createSetupCommand } from "../src/commands/setup.ts";
import { help } from "../src/commands/help.ts";
import { userHash } from "../src/utils/identity.ts";
import { CHANNEL, GUILD, fakeInteraction } from "./helpers.ts";
import { followupThreads } from "../src/interactions/followup.ts";

function setupDeps() {
  const log: string[] = [];
  const api = {
    enableGuildChannel: async (g: string, c: string) => void log.push(`enable ${g} ${c}`),
    disableGuildChannel: async (g: string, c: string) => (log.push(`disable ${g} ${c}`), 1),
    disableAllGuildChannels: async (g: string) => (log.push(`disable-all ${g}`), 4),
  };
  const cache = { invalidate: (g: string) => void log.push(`invalidate ${g}`) };
  return {
    log,
    command: createSetupCommand(
      () => api,
      () => cache,
    ),
  };
}

test("registry exposes every documented command and help lists them all", () => {
  for (const name of ["ask", "ping", "help", "about", "setup", "clear"]) assert.ok(commands.has(name), name);
  assert.ok(!commands.has("config"));
  for (const name of commands.keys()) assert.match(helpText(), new RegExp(`/${name}`), `/help mentions /${name}`);
});
function helpText() {
  let text = "";
  void help.execute({
    reply: async (p: { embeds: { toJSON(): { description: string } }[] }) => {
      text = p.embeds[0].toJSON().description;
    },
  } as never);
  return text;
}

test("setup subcommands map to the API and refresh the cache; admin only", async () => {
  for (const [sub, expected] of [
    ["enable", `enable ${GUILD} ${CHANNEL}`],
    ["disable", `disable ${GUILD} ${CHANNEL}`],
    ["disable-all", `disable-all ${GUILD}`],
  ] as const) {
    const { log, command } = setupDeps();
    const mock = fakeInteraction({ sub, admin: true });
    await command.execute(mock.value);
    assert.deepEqual(log, [expected, `invalidate ${GUILD}`]);
    assert.deepEqual(mock.calls, ["defer", "edit"]);
    assert.deepEqual(mock.edits[0].allowedMentions, { parse: [] });
  }
  const { log, command } = setupDeps();
  const mock = fakeInteraction({ sub: "enable", admin: false });
  await command.execute(mock.value);
  assert.deepEqual(log, [], "non-admin never reaches the API");
  assert.match(mock.edits[0].content!, /Manage Server/);
});

test("setup defers replies privately and reports API errors without leaking details", async () => {
  const command = createSetupCommand(
    () => ({
      enableGuildChannel: async () => {
        throw new Error("PRIVATE_SECRET");
      },
      disableGuildChannel: async () => 0,
      disableAllGuildChannels: async () => 0,
    }),
    () => ({ invalidate() {} }),
  );
  const mock = fakeInteraction({ sub: "enable", admin: true });
  await command.execute(mock.value);
  assert.ok(!mock.edits[0].content!.includes("PRIVATE_SECRET"));
  const json = command.data.toJSON();
  assert.deepEqual(
    json.options?.map((o) => o.name),
    ["enable", "disable", "disable-all"],
  );
  assert.equal(json.default_member_permissions, "32");
});

function clearApi(result: Partial<Parameters<typeof clearSummary>[0]> = {}) {
  const calls: unknown[] = [];
  const api = {
    clearMemory: async (g: string, target: unknown) => {
      calls.push([g, target]);
      return {
        guild_id: g,
        scope: "user" as const,
        conversations: 2,
        threads_kept: 1,
        vector_conversations: 2,
        ...result,
      };
    },
  };
  return { calls, command: createClearCommand(() => api) };
}

test("a member clears their own memory and is told that threads are kept", async () => {
  const { calls, command } = clearApi();
  const mock = fakeInteraction({ sub: "user" });
  await command.execute(mock.value);
  assert.deepEqual(calls, [[GUILD, { scope: "user", userHash: userHash("111111111111111111") }]]);
  assert.match(mock.edits[0].content!, /Đã xóa 2/);
  assert.match(mock.edits[0].content!, /thread[\s\S]*clear all/);
});

test("clearing someone else or all requires admin; admin can do both", async () => {
  for (const [sub, member] of [
    ["user", { id: "222222222222222222" }],
    ["all", undefined],
  ] as const) {
    const denied = clearApi();
    const deniedMock = fakeInteraction({ sub, member });
    await denied.command.execute(deniedMock.value);
    assert.deepEqual(denied.calls, []);
    assert.match(deniedMock.edits[0].content!, /Manage Server|chính mình/);
    const allowed = clearApi({ scope: sub === "all" ? "all" : "user", threads_kept: 0 });
    const allowedMock = fakeInteraction({ sub, member, admin: true });
    await allowed.command.execute(allowedMock.value);
    assert.equal(allowed.calls.length, 1);
  }
  const target = clearApi();
  await target.command.execute(
    fakeInteraction({ sub: "user", member: { id: "222222222222222222" }, admin: true }).value,
  );
  assert.deepEqual(target.calls, [[GUILD, { scope: "user", userHash: userHash("222222222222222222") }]]);
});

test("clear refuses DMs and bot targets without calling the API", async () => {
  const { calls, command } = clearApi();
  const dm = fakeInteraction({ sub: "all", guildId: null, admin: true });
  await command.execute(dm.value);
  const bot = fakeInteraction({ sub: "user", member: { id: "5", bot: true }, admin: true });
  await command.execute(bot.value);
  assert.deepEqual(calls, []);
});

test("clear all invalidates pending followup buttons only after successful authorized deletion", async () => {
  const id = followupThreads.button({ guildId: GUILD, channelId: CHANNEL, question: "Marika?", answer: "Marika." }).data
    .custom_id!;
  let reply = "";
  const mockButton = {
    customId: id,
    guildId: GUILD,
    channelId: CHANNEL,
    deferReply: async () => {},
    editReply: async (p: { content: string }) => {
      reply = p.content;
    },
  };
  const allowed = clearApi({ scope: "all" });
  await allowed.command.execute(fakeInteraction({ sub: "all", admin: false }).value);
  await followupThreads.handle(mockButton as never);
  assert.ok(!reply.includes("hết hạn"), "unauthorized clear must keep the button");
  const failed = createClearCommand(() => ({
    clearMemory: async () => {
      throw new Error("offline");
    },
  }));
  await failed.execute(fakeInteraction({ sub: "all", admin: true }).value);
  await followupThreads.handle(mockButton as never);
  assert.ok(!reply.includes("hết hạn"), "failed clear must keep the button");
  await allowed.command.execute(fakeInteraction({ sub: "all", admin: true }).value);
  await followupThreads.handle(mockButton as never);
  assert.match(reply, /hết hạn/);
});

test("clearSummary covers empty, thread-only and all scopes", () => {
  const base = { guild_id: GUILD, scope: "user" as const, vector_conversations: 0 };
  assert.match(clearSummary({ ...base, conversations: 0, threads_kept: 0 }, "bạn"), /Không có dữ liệu/);
  assert.match(
    clearSummary({ ...base, conversations: 0, threads_kept: 2 }, "bạn"),
    /Không có hội thoại riêng[\s\S]*thread/,
  );
  assert.match(clearSummary({ ...base, scope: "all", conversations: 5, threads_kept: 0 }, "server"), /gồm cả thread/);
});

test("ping shows websocket latency and API health, and survives an API outage", async () => {
  const healthy = createPingCommand(() => ({
    health: async () => ({ status: "ok", checks: {}, http_status: 200, rtt_ms: 17 }),
  }));
  const mock = fakeInteraction({ sub: "", wsPing: 55 });
  await healthy.execute(mock.value);
  assert.match(mock.edits[0].content!, /55 ms[\s\S]*ổn \(17 ms\)/);
  const degraded = createPingCommand(() => ({
    health: async () => ({ status: "degraded", checks: { qdrant: false, db: true }, http_status: 503, rtt_ms: 9 }),
  }));
  const second = fakeInteraction({ sub: "" });
  await degraded.execute(second.value);
  assert.match(second.edits[0].content!, /suy giảm[\s\S]*qdrant/);
  const down = createPingCommand(() => ({
    health: async () => {
      throw new Error("PRIVATE_SECRET");
    },
  }));
  const third = fakeInteraction({ sub: "", wsPing: -1 });
  await down.execute(third.value);
  assert.match(third.edits[0].content!, /chưa đo được[\s\S]*không truy cập được/);
  assert.ok(!third.edits[0].content!.includes("PRIVATE_SECRET"));
});

test("clear rejects a bot target before any permission message", async () => {
  const { calls, command } = clearApi();
  const mock = fakeInteraction({ sub: "user", member: { id: "5", bot: true } });
  await command.execute(mock.value);
  assert.deepEqual(calls, []);
  assert.match(mock.edits[0].content!, /Bot không có ký ức/);
});
