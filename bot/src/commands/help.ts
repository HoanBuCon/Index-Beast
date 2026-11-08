// /help.
// Phụ trách: TV4 · [S3] Bot: /help /about
// Trợ giúp sử dụng bot, không gọi backend hoặc model.
import { EmbedBuilder, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "./index.ts";

export const help: Command = {
  data: new SlashCommandBuilder().setName("help").setDescription("Hướng dẫn dùng INDEX BEAST."),
  async execute(interaction) {
    await interaction.reply({
      embeds: [
        new EmbedBuilder()
          .setColor(0xd9bc78)
          .setTitle("INDEX BEAST · Hướng dẫn")
          .setDescription(
            "`/ask question:<câu hỏi>` — hỏi về Elden Ring.\n" +
              "Ví dụ: `/ask question:Marika là ai?`\n\n" +
              "Bot giữ ngữ cảnh theo người dùng/kênh; trong thread dùng chung ngữ cảnh của thread. " +
              "Bạn có thể gửi câu trả lời bổ sung bằng một lệnh `/ask` tiếp theo. " +
              "Nội dung dài được chia thành các phần; nguồn nằm ở phần đầu. " +
              "Nút xem đầy đủ trên web (nếu có) mở bản chia sẻ chỉ đọc, hết hạn sau 24 giờ; ai có link đều xem được câu đó.\n\n" +
              "`/ping` — kiểm tra bot online.\n`/about` — nhóm phát triển, nguồn và giấy phép.\n\n" +
              "AI có thể mắc sai sót. Hãy kiểm tra các nguồn được dẫn; câu trả lời có thể tiết lộ nội dung trò chơi.",
          ),
      ],
      flags: MessageFlags.Ephemeral,
      allowedMentions: { parse: [] },
    });
  },
};
