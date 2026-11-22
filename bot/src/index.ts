// Điểm vào: tạo Client discord.js, lắng nghe interactionCreate, chuyển tới command/interaction tương ứng.
// Phụ trách: TV4 · [S1] Khởi tạo Discord bot

import { Client, Events, GatewayIntentBits, MessageFlags } from "discord.js";
import { commands } from "./commands/index.ts";
import { createMessageHandler } from "./handlers/message.ts";
import { loadConfig } from "./config.ts";
import { errorName, log } from "./utils/logger.ts";
import { followupThreads } from "./interactions/followup.ts";

// MessageContent là intent đặc quyền: phải bật trong Discord Developer Portal (Bot → Privileged Gateway Intents),
// nếu không client.login báo "Used disallowed intents". Cần cho @mention và trả lời kênh /setup.
const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent],
});
const handleMessage = createMessageHandler();

client.once(Events.ClientReady, (readyClient) => {
  log("info", "Bot đã online.", { user: readyClient.user.tag });
});

client.on(Events.Error, (error) => log("error", "Discord client gặp lỗi.", { error: errorName(error) }));

client.on(Events.MessageCreate, async (message) => {
  try {
    await handleMessage(message);
  } catch (error) {
    log("error", "Không xử lý được tin nhắn.", { error: errorName(error) });
  }
});

client.on(Events.InteractionCreate, async (interaction) => {
  if (interaction.isButton()) {
    if (interaction.customId.startsWith("followup:")) {
      try {
        await followupThreads.handle(interaction);
      } catch (error) {
        log("warn", "Không gửi được phản hồi nút Hỏi tiếp.", { error: errorName(error) });
      }
    }
    return;
  }
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
  log(
    "error",
    error instanceof Error && error.message === "Used disallowed intents"
      ? "Discord chưa cho phép Message Content Intent. Bật trong Developer Portal → Bot → Privileged Gateway Intents rồi chạy lại."
      : "Không khởi động được bot. Kiểm tra DISCORD_TOKEN và kết nối Discord.",
    { error: errorName(error) },
  );
  client.destroy();
  process.exitCode = 1;
}
