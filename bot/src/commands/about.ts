// /about: nguồn & giấy phép CC BY-SA.
// Phụ trách: TV4 · [S3] Bot: /help /about
// Giới thiệu và giấy phép theo docs/data-sources.md.
import { EmbedBuilder, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "./index.ts";

export const about: Command = {
  data: new SlashCommandBuilder().setName("about").setDescription("Về INDEX BEAST, nguồn dữ liệu và giấy phép."),
  async execute(interaction) {
    await interaction.reply({
      embeds: [
        new EmbedBuilder()
          .setColor(0xd9bc78)
          .setTitle("INDEX BEAST · 4 Hollows")
          .setDescription(
            "Dự án hỏi đáp Elden Ring của nhóm 4 Hollows, dùng chung backend cho website và Discord.\n\n" +
              "Nguồn văn bản chính: [Elden Ring Wiki](https://eldenring.wiki.gg/), đóng góp bởi cộng đồng wiki. " +
              "Theo khảo sát nguồn của dự án, văn bản được ghi nhận theo " +
              "[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/): ghi công, dẫn nguồn/giấy phép, " +
              "nêu thay đổi và chia sẻ phần phái sinh theo cùng giấy phép. Câu trả lời là bản tổng hợp do AI tạo, " +
              "không phải bản sao nguyên văn đã được cộng đồng xác nhận.\n\n" +
              "[Elden Ring Fan APIs](https://eldenring.fanapis.com/) là nguồn thực thể được khảo sát. " +
              "Không mặc định áp dụng giấy phép văn bản cho hình ảnh hoặc dữ liệu nguồn khác; xem điều kiện tại nguồn.\n\n" +
              "Fan project độc lập, không liên kết hoặc được bảo trợ bởi FromSoftware hay Bandai Namco. " +
              "AI có thể mắc sai sót; hãy xem các liên kết nguồn trong câu trả lời.",
          ),
      ],
      flags: MessageFlags.Ephemeral,
      allowedMentions: { parse: [] },
    });
  },
};
