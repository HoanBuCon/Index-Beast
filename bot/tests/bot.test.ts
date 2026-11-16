// Kiểm tra S1 không kết nối Discord hoặc đọc .env.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import assert from "node:assert/strict";
import test from "node:test";
import type { ChatInputCommandInteraction } from "discord.js";
import { commands } from "../src/commands/index.ts";
import { createPingCommand } from "../src/commands/ping.ts";
import { loadConfig } from "../src/config.ts";

test("missing configuration fails without reading the real environment", () => {
  assert.throws(() => loadConfig({}), /DISCORD_TOKEN/);
});

test("registered ping command is registered and replies privately with latency", async () => {
  const ping = commands.get("ping")!;
  assert.equal(ping.data.toJSON().name, "ping");
  const edits: { content?: string }[] = [];
  const interaction = {
    client: { ws: { ping: 30 } },
    deferReply: async () => {},
    editReply: async (payload: { content?: string }) => {
      edits.push(payload);
    },
  };
  // Không có backend thật: health lỗi mạng nhưng lệnh vẫn trả lời.
  await createPingCommand(() => ({
    health: async () => {
      throw new Error("offline");
    },
  })).execute(interaction as unknown as ChatInputCommandInteraction);
  assert.match(edits[0].content!, /Pong!/);
});
