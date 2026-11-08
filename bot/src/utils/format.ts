// Cắt câu trả lời theo giới hạn embed (4.096 ký tự), field nguồn, link 'xem đầy đủ trên web'.
// Phụ trách: TV4 · [S3] Bot: câu trả lời thật, chia nhỏ
// S3: chia đủ nội dung bằng answerEmbeds; handler ask gắn link bản chia sẻ một câu trả lời có hạn dùng.

import { EmbedBuilder, escapeMarkdown } from "discord.js";
import type { ChatResponse } from "../api/types.ts";

// S2 rút gọn một embed; S3 dùng answerEmbeds bên dưới để chia đủ nội dung thành nhiều phần.
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
    .setDescription(cut(response.answer, 3600));
  // grounded=false gồm cả chào hỏi và câu hỏi lại, nên không gắn nhãn "thiếu bằng chứng"; câu trả lời đã tự nói rõ.
  const footer = [
    response.grounded ? "Nguồn tham khảo bên dưới." : "",
    shortened ? "Nội dung đã được rút gọn để vừa Discord." : "",
  ]
    .filter(Boolean)
    .join(" ");
  if (footer) embed.setFooter({ text: footer });
  if (lines.length) embed.addFields({ name: "Nguồn tham khảo · ghi nguồn theo liên kết", value: lines.join("\n") });
  return embed;
}

// Mỗi phần ở một tin riêng để không vượt tổng 6.000 ký tự embed/tin.
export function answerEmbeds(question: string, response: ChatResponse) {
  const parts: string[] = [];
  let rest = response.answer;
  while (rest.length > 3600) {
    let end = 3600;
    const boundary = rest.lastIndexOf("\n", end);
    if (boundary > 2400) end = boundary + 1;
    if (/[\uD800-\uDBFF]/.test(rest[end - 1] ?? "")) end -= 1;
    parts.push(rest.slice(0, end));
    rest = rest.slice(end);
  }
  if (rest || !parts.length) parts.push(rest);
  return parts.map((part, index) => {
    const embed =
      index === 0
        ? answerEmbed(question, { ...response, answer: part })
        : new EmbedBuilder().setColor(0xd9bc78).setTitle("INDEX BEAST · Tiếp theo").setDescription(part);
    if (parts.length > 1) {
      const footer = embed.data.footer?.text;
      embed.setFooter({ text: `${footer ? `${footer} ` : ""}Phần ${index + 1}/${parts.length}` });
    }
    return embed;
  });
}
