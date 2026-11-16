// Nút 👍/👎 dưới câu trả lời hoàn tất; 👎 có ô lý do tuỳ chọn.
// Quyền gửi: người đã đăng nhập dùng cookie phiên, khách gửi kèm X-Conversation-Token (xem backend routes/feedback.py).
// Phụ trách: TV4 · [S4] Web: feedback, lịch sử, câu hỏi gợi ý · [S5] nối vào MessageList

import { useState } from "react";
import { sendFeedback } from "../../api/client";
import { MAX_FEEDBACK_CHARS } from "../../api/types";
export default function FeedbackButtons({
  messageId,
  demo,
  token,
}: {
  messageId: string;
  demo: boolean;
  token?: string;
}) {
  const [rating, setRating] = useState(0);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [status, setStatus] = useState("");
  async function submit(value: number, text: string) {
    setBusy(true);
    setStatus("");
    try {
      if (!demo) await sendFeedback(messageId, value, text.trim(), token);
      setSent(true);
      setStatus(demo ? "Đã thử phản hồi (chưa gửi lên server)." : "Đã gửi phản hồi. Cảm ơn bạn!");
    } catch {
      setStatus("Chưa gửi được phản hồi. Vui lòng thử lại.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="feedback">
      <span id={`fb-${messageId}`}>{"Câu trả lời có hữu ích?"}</span>
      {[1, -1].map((value) => (
        <button
          key={value}
          type="button"
          aria-label={value === 1 ? "Hữu ích" : "Chưa hữu ích"}
          aria-pressed={rating === value}
          disabled={busy || sent}
          onClick={() => {
            setRating(value);
            setStatus("");
            // 👍 gửi ngay; 👎 mở ô lý do (tuỳ chọn) rồi mới gửi.
            if (value === 1) void submit(value, "");
          }}
        >
          {value === 1 ? "👍" : "👎"}
        </button>
      ))}
      {rating === -1 && !sent && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit(-1, reason);
          }}
        >
          <input
            aria-label={"Lý do phản hồi (không bắt buộc)"}
            placeholder={"Chia sẻ thêm (không bắt buộc)"}
            value={reason}
            maxLength={MAX_FEEDBACK_CHARS}
            onChange={(e) => setReason(e.target.value)}
          />
          <button disabled={busy} type="submit">
            {busy ? "Đang gửi…" : "Gửi phản hồi"}
          </button>
        </form>
      )}
      <span role="status">{status}</span>
    </div>
  );
}
