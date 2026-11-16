// /help.
// Phụ trách: TV4 · [S3] Bot: /help /about · [S5] thêm /setup /clear và hỏi bằng mention
// Trợ giúp sử dụng bot, không gọi backend hoặc model. Giữ đồng bộ với registry trong index.ts.
import { EmbedBuilder, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "./index.ts";

export const HELP_TEXT =
  "**Hỏi đáp**\n" +
  "`/ask question:<câu hỏi>` — hỏi về Elden Ring ở bất kỳ kênh nào. Ví dụ: `/ask question:Marika là ai?`\n" +
  "`@INDEX BEAST <câu hỏi>` — nhắc tên bot để hỏi, không cần lệnh.\n" +
  "Ở kênh đã được admin bật bằng `/setup`, bot trả lời mọi tin nhắn mà không cần `/ask`.\n\n" +
  "**Ký ức & riêng tư**\n" +
  "`/clear user` — xóa ký ức hội thoại riêng của bạn trong server (admin có thể chọn `member`).\n" +
  "`/clear all` — admin xóa ký ức cả server, kể cả thread. `/clear user` không xóa thread dùng chung.\n\n" +
  "**Quản trị server** (cần quyền Manage Server)\n" +
  "`/setup enable channel:#kênh` — bật tự trả lời · `/setup disable channel:#kênh` — tắt · `/setup disable-all` — tắt mọi kênh.\n\n" +
  "**Khác**\n" +
  "`/ping` — độ trễ Discord và tình trạng API · `/about` — nhóm phát triển, nguồn và giấy phép · `/help` — trang này.\n\n" +
  "Bot giữ ngữ cảnh theo người dùng/kênh; trong thread dùng chung ngữ cảnh của thread. " +
  "Nội dung dài được chia thành các phần; nguồn nằm ở phần đầu. " +
  "Nút xem đầy đủ trên web (nếu có) mở bản chia sẻ chỉ đọc, hết hạn sau 24 giờ; ai có link đều xem được câu đó.\n\n" +
  "AI có thể mắc sai sót. Hãy kiểm tra các nguồn được dẫn; câu trả lời có thể tiết lộ nội dung trò chơi.";

export const help: Command = {
  data: new SlashCommandBuilder().setName("help").setDescription("Hướng dẫn dùng INDEX BEAST."),
  async execute(interaction) {
    await interaction.reply({
      embeds: [new EmbedBuilder().setColor(0xd9bc78).setTitle("INDEX BEAST · Hướng dẫn").setDescription(HELP_TEXT)],
      flags: MessageFlags.Ephemeral,
      allowedMentions: { parse: [] },
    });
  },
};
