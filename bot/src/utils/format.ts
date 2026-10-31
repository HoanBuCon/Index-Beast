// Cắt câu trả lời theo giới hạn embed (4.096 ký tự), field nguồn, link 'xem đầy đủ trên web'.
// Phụ trách: TV4 · [S3] Bot: câu trả lời thật, chia nhỏ

import { EmbedBuilder, escapeMarkdown } from "discord.js";
import type { ChatResponse } from "../api/types.ts";

// S2 chỉ rút gọn một embed; lưu ngữ cảnh, chia nhiều tin và link xem đầy đủ thuộc S3.
function cut(text: string, limit: number) {
  if (text.length <= limit) return text;
  let end = limit - 1;
  if (/[\uD800-\uDBFF]/.test(text[end - 1] ?? "")) end -= 1;
  return `${text.slice(0, end)}…`;
}

export function answerEmbed(question: string, response: ChatResponse) {
  const lines: string[] = [];
  let used = 0;
  for (const source of response.sources) {
    let url: URL;
    try {
      url = new URL(source.url);
    } catch {
      continue;
    }
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) continue;
    const title = escapeMarkdown(cut(source.title.replace(/[\r\n]/g, " "), 100));
    const href = url.href.replace(/\(/g, "%28").replace(/\)/g, "%29");
    const line = `[${source.index}] [${title}](${href})${source.origin === "web" ? " · web" : ""}`;
    if (used + line.length + 1 > 1000) continue;
    lines.push(line);
    used += line.length + 1;
  }
  const shortened = response.answer.length > 3600 || lines.length < response.sources.length;
  const embed = new EmbedBuilder()
    .setColor(0xd9bc78)
    .setTitle(cut(question, 200))
    .setDescription(cut(response.answer, 3600))
    .setFooter({
      text: `${response.grounded ? "Nguồn tham khảo bên dưới." : "Chưa tìm được đủ bằng chứng."}${shortened ? " Nội dung đã được rút gọn để vừa Discord." : ""}`,
    });
  if (lines.length) embed.addFields({ name: "Nguồn tham khảo · ghi nguồn theo liên kết", value: lines.join("\n") });
  return embed;
}
