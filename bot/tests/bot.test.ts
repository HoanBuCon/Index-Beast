// Kiểm tra S1 không kết nối Discord hoặc đọc .env.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import assert from "node:assert/strict";
import test from "node:test";
import type { ChatInputCommandInteraction } from "discord.js";
import { commands } from "../src/commands/index.ts";
import { loadConfig } from "../src/config.ts";

const valid = {
  DISCORD_TOKEN: "fake-token",
  DISCORD_CLIENT_ID: "123456789012345678",
  DISCORD_GUILD_ID: "234567890123456789",
};

test("dev requires a token and valid application/server IDs", () => {
  assert.equal(loadConfig(valid).guildId, valid.DISCORD_GUILD_ID);
  for (const field of ["DISCORD_TOKEN", "DISCORD_CLIENT_ID", "DISCORD_GUILD_ID"] as const) {
    assert.throws(() => loadConfig({ ...valid, [field]: "" }), new RegExp(field));
  }
  assert.throws(() => loadConfig({ ...valid, DISCORD_GUILD_ID: "not-an-id" }), /DISCORD_GUILD_ID/);
});

test("production can register globally without a guild", () => {
  const config = loadConfig({ ...valid, ENVIRONMENT: "prod", DISCORD_GUILD_ID: "" });
  assert.equal(config.isProd, true);
  assert.equal(config.guildId, undefined);
});

test("registered ping command replies Pong!", async () => {
  const ping = commands.get("ping")!;
  assert.equal(ping.data.toJSON().name, "ping");
  const replies: string[] = [];
  const interaction = {
    reply: async (message: string) => {
      replies.push(message);
    },
  };
  await ping.execute(interaction as unknown as ChatInputCommandInteraction);
  assert.deepEqual(replies, ["Pong!"]);
});
