// Kiểm tra S1 không kết nối Discord hoặc đọc .env.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import assert from "node:assert/strict";
import test from "node:test";
import type { ChatInputCommandInteraction } from "discord.js";
import { commands } from "../src/commands/index.ts";
import { loadConfig } from "../src/config.ts";

test("missing configuration fails without reading the real environment", () => {
  assert.throws(() => loadConfig({}), /DISCORD_TOKEN/);
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
