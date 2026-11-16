// TV4 · S5: client /discord/guilds/*, /health, cache kênh và rate limit; fetch giả, không mạng.
import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, createApiClient } from "../src/api/client.ts";
import { createGuildChannelCache } from "../src/utils/guildChannelCache.ts";
import { createUserRateLimiter } from "../src/utils/rateLimit.ts";
import { externalRef, userHash } from "../src/utils/identity.ts";
import { CHANNEL, GUILD } from "./helpers.ts";

const config = { baseUrl: "http://api.test/api/v1", serviceToken: "svc" };
function client(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetcher = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return handler(url, init);
  }) as unknown as typeof fetch;
  return { api: createApiClient(config, { fetcher }), calls };
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

test("guild channel endpoints use the contract paths, methods and service token", async () => {
  const { api, calls } = client((url, init) => {
    if (init.method === "PUT") return json({ channel_id: CHANNEL, enabled_at: "2026-11-16T00:00:00Z" });
    if (init.method === "DELETE") return json({ deleted: url.endsWith("/channels") ? 3 : 1 });
    return json({ guild_id: GUILD, channels: [{ channel_id: CHANNEL, enabled_at: "x" }], limit: 50 });
  });
  assert.deepEqual(await api.listGuildChannels(GUILD), [CHANNEL]);
  await api.enableGuildChannel(GUILD, CHANNEL);
  assert.equal(await api.disableGuildChannel(GUILD, CHANNEL), 1);
  assert.equal(await api.disableAllGuildChannels(GUILD), 3);
  const base = `http://api.test/api/v1/discord/guilds/${GUILD}/channels`;
  assert.deepEqual(
    calls.map((c) => [c.init.method ?? "GET", c.url]),
    [
      ["GET", base],
      ["PUT", `${base}/${CHANNEL}`],
      ["DELETE", `${base}/${CHANNEL}`],
      ["DELETE", base],
    ],
  );
  assert.ok(calls.every((c) => (c.init.headers as Record<string, string>)["X-Service-Token"] === "svc"));
});

test("clearMemory sends scope/user_hash, validates input and response", async () => {
  const hash = userHash("111111111111111111");
  const { api, calls } = client(() =>
    json({ guild_id: GUILD, scope: "user", conversations: 2, threads_kept: 1, vector_conversations: 2 }),
  );
  const result = await api.clearMemory(GUILD, { scope: "user", userHash: hash });
  assert.equal(result.threads_kept, 1);
  assert.equal(calls[0].url, `http://api.test/api/v1/discord/guilds/${GUILD}/memory/clear`);
  assert.deepEqual(JSON.parse(calls[0].init.body as string), { scope: "user", user_hash: hash });
  await api.clearMemory(GUILD, { scope: "all" });
  assert.deepEqual(JSON.parse(calls[1].init.body as string), { scope: "all" });
  await assert.rejects(api.clearMemory(GUILD, { scope: "user", userHash: "111111111111111111" }), ApiError);
  await assert.rejects(api.clearMemory("abc", { scope: "all" }), ApiError);
  const bad = client(() => json({ conversations: "2" }));
  await assert.rejects(bad.api.clearMemory(GUILD, { scope: "all" }));
});

test("409 channel cap maps to a friendly message", async () => {
  const { api } = client(() => json({ code: "conflict" }, 409));
  await assert.rejects(api.enableGuildChannel(GUILD, CHANNEL), /tối đa/);
});

test("health returns ok and degraded (503) bodies, other failures throw", async () => {
  let status = 200;
  const { api, calls } = client(() =>
    json({ status: status === 200 ? "ok" : "degraded", checks: { db: status === 200 } }, status),
  );
  const ok = await api.health();
  assert.equal(ok.status, "ok");
  assert.ok(ok.rtt_ms >= 0);
  assert.equal(calls[0].url, "http://api.test/api/v1/health");
  status = 503;
  const degraded = await api.health();
  assert.equal(degraded.status, "degraded");
  assert.deepEqual(degraded.checks, { db: false });
  status = 500;
  const broken = client(() => new Response("x", { status: 500 }));
  await assert.rejects(broken.api.health(), ApiError);
});

test("chat requests accept a numeric guild_id and reject a malformed one", async () => {
  const { api } = client(() => json({}));
  await assert.rejects(api.chat({ message: "q", channel: "discord", guild_id: "abc" }), /server/);
});

test("channel cache fetches once per TTL, shares in-flight loads, serves stale on failure and invalidates", async () => {
  let now = 0;
  let fetches = 0;
  let fail = false;
  const cache = createGuildChannelCache(
    async () => {
      fetches++;
      if (fail) throw new Error("down");
      return [CHANNEL];
    },
    { ttlMs: 1000, now: () => now },
  );
  const [a, b] = await Promise.all([cache.has(GUILD, CHANNEL), cache.has(GUILD, "x")]);
  assert.deepEqual([a, b, fetches], [true, false, 1]);
  assert.equal(await cache.has(GUILD, CHANNEL), true);
  assert.equal(fetches, 1);
  now = 1001;
  fail = true;
  assert.equal(await cache.has(GUILD, CHANNEL), true, "stale entry survives API failure");
  assert.equal(fetches, 2);
  fail = false;
  cache.invalidate(GUILD);
  await cache.has(GUILD, CHANNEL);
  assert.equal(fetches, 3);
  const cold = createGuildChannelCache(async () => {
    throw new Error("down");
  });
  await assert.rejects(cold.has(GUILD, CHANNEL));
});

test("rate limiter allows max per window, warns once, then denies and recovers", () => {
  let now = 0;
  const limiter = createUserRateLimiter({ max: 2, windowMs: 1000, now: () => now });
  assert.deepEqual(
    [limiter.check("u"), limiter.check("u"), limiter.check("u"), limiter.check("u")],
    ["allow", "allow", "warn", "deny"],
  );
  assert.equal(limiter.check("other"), "allow");
  now = 1001;
  assert.equal(limiter.check("u"), "allow");
});

test("external_ref keeps the documented formula", () => {
  assert.match(externalRef("5", false, "1"), /^discord:channel:5:[0-9a-f]{64}$/);
  assert.equal(externalRef("5", true, "1"), "discord:thread:5");
});
