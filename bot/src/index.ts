// Điểm vào: tạo Client discord.js, lắng nghe interactionCreate, chuyển tới command/interaction tương ứng.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import { Client, Events, GatewayIntentBits, MessageFlags } from "discord.js";
import { commands } from "./commands/index.ts";
import { loadConfig } from "./config.ts";
import { errorName, log } from "./utils/logger.ts";

const client = new Client({ intents: [GatewayIntentBits.Guilds] });

client.once(Events.ClientReady, (readyClient) => {
  log("info", "Bot đã online.", { user: readyClient.user.tag });
});

client.on(Events.Error, (error) => log("error", "Discord client gặp lỗi.", { error: errorName(error) }));

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  try {
    const command = commands.get(interaction.commandName);
    if (!command) {
      await interaction.reply({ content: "Lệnh chưa được hỗ trợ.", flags: MessageFlags.Ephemeral });
      return;
    }
    await command.execute(interaction);
  } catch (error) {
    log("error", "Không xử lý được lệnh.", { request_id: interaction.id, error: errorName(error) });
    try {
      if (interaction.deferred || interaction.replied) {
        await interaction.editReply("Có lỗi khi xử lý lệnh. Vui lòng thử lại.");
      } else {
        await interaction.reply({ content: "Có lỗi khi xử lý lệnh. Vui lòng thử lại.", flags: MessageFlags.Ephemeral });
      }
    } catch {
      log("error", "Không gửi được thông báo lỗi.", { request_id: interaction.id });
    }
  }
});

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => {
    log("info", "Đang dừng bot.");
    client.destroy();
  });
}

try {
  const config = loadConfig();
  await client.login(config.token);
} catch (error) {
  log("error", "Không khởi động được bot. Kiểm tra DISCORD_TOKEN, CLIENT_ID và GUILD_ID.", { error: errorName(error) });
  client.destroy();
  process.exitCode = 1;
}
