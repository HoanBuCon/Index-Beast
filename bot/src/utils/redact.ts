// Làm sạch văn bản người dùng Discord trước khi gửi backend/LLM; dùng chung cho /ask và tin nhắn thường
// (hỏi tiếp trong thread chỉ nhận lại chuỗi đã qua hai đường này).

// Không lưu ID Discord thô của người khác (NFR-PRIV-01): thay bằng chỗ giữ chỗ trung tính.
export function sanitizeMentions(text: string): string {
  return text
    .replace(/<@[!&]?\d+>/g, "@ai đó")
    .replace(/<#\d+>/g, "#kênh")
    .replace(/<a?:(\w+):\d+>/g, ":$1:");
}
