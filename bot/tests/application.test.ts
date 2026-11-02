// DISCORD_CLIENT_ID không bắt buộc: Application ID lấy từ Discord khi để trống.
// Phụ trách: TV1 · [S3] Bot không cần DISCORD_CLIENT_ID/DISCORD_GUILD_ID

import assert from "node:assert/strict";
import test from "node:test";
import { loadConfig } from "../src/config.ts";
import { resolveApplicationId } from "../src/utils/application.ts";

test("client and guild ids are optional", () => {
  assert.deepEqual(loadConfig({ DISCORD_TOKEN: "token" }), { token: "token", clientId: undefined });
  assert.deepEqual(loadConfig({ DISCORD_TOKEN: "token", DISCORD_CLIENT_ID: " " }), {
    token: "token",
    clientId: undefined,
  });
});

test("a malformed client id is still rejected", () => {
  assert.throws(() => loadConfig({ DISCORD_TOKEN: "token", DISCORD_CLIENT_ID: "abc" }), /Application ID/);
});

test("configured application id is used without calling Discord", async () => {
  const rest = { get: async () => assert.fail("must not call Discord") };
  assert.equal(await resolveApplicationId(rest, "123456789012345678"), "123456789012345678");
});

test("missing application id is read from the current application", async () => {
  const routes: string[] = [];
  const rest = {
    get: async (route: string) => {
      routes.push(route);
      return { id: "987654321098765432" };
    },
  };
  assert.equal(await resolveApplicationId(rest), "987654321098765432");
  assert.deepEqual(routes, ["/applications/@me"]);
});

test("invalid response from Discord fails clearly", async () => {
  await assert.rejects(resolveApplicationId({ get: async () => ({}) }), /Application ID/);
});
