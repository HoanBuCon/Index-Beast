// TV4 · S3: lệnh trợ giúp/ghi nguồn không gọi Discord gateway hoặc backend.
import assert from "node:assert/strict";
import test from "node:test";
import { MessageFlags } from "discord.js";
import type { ChatInputCommandInteraction, InteractionReplyOptions } from "discord.js";
import { commands } from "../src/commands/index.ts";

test("global registry includes help/about with private, bounded and attributed replies", async () => {
  for (const name of ["help", "about"]) {
    const command = commands.get(name)!;
    assert.equal(command.data.toJSON().name, name);
    let reply: InteractionReplyOptions | undefined;
    await command.execute({
      reply: async (payload: InteractionReplyOptions) => {
        reply = payload;
      },
    } as unknown as ChatInputCommandInteraction);
    assert.equal(reply!.flags, MessageFlags.Ephemeral);
    assert.deepEqual(reply!.allowedMentions, { parse: [] });
    const embed = JSON.parse(JSON.stringify(reply!.embeds![0]));
    assert.ok(embed.description.length <= 4096);
    if (name === "help") assert.match(embed.description, /\/ask[\s\S]*\/ping[\s\S]*\/about/);
    else {
      assert.match(embed.description, /https:\/\/eldenring.wiki.gg\//);
      assert.match(embed.description, /https:\/\/creativecommons.org\/licenses\/by-sa\/4.0\//);
      assert.match(embed.description, /FromSoftware[\s\S]*Bandai Namco/);
    }
  }
});
