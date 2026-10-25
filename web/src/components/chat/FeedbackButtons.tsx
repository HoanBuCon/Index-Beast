// Nút 👍/👎 + lý do tuỳ chọn.
// Phụ trách: TV4 · [S4] Web: feedback, lịch sử, câu hỏi gợi ý

import { useState } from "react";
import { sendFeedback } from "../../api/client";
import { useLanguage } from "../../lib/i18n";
export default function FeedbackButtons({ messageId, demo }: { messageId: string; demo: boolean }) {
  const { t } = useLanguage();
  const [rating, setRating] = useState(0);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  async function submit() {
    setBusy(true);
    setStatus("");
    try {
      if (!demo) await sendFeedback(messageId, rating, reason);
      setStatus(demo ? t("Đã thử phản hồi (chưa gửi lên server).") : t("Đã gửi phản hồi. Cảm ơn bạn!"));
    } catch {
      setStatus(t("Chưa gửi được phản hồi. Vui lòng thử lại."));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="feedback">
      <span>{t("Câu trả lời có hữu ích?")}</span>
      {[1, -1].map((value) => (
        <button
          key={value}
          aria-label={value === 1 ? t("Hữu ích") : t("Chưa hữu ích")}
          aria-pressed={rating === value}
          onClick={() => {
            setRating(value);
            setStatus("");
          }}
        >
          {value === 1 ? "👍" : "👎"}
        </button>
      ))}
      {rating !== 0 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <input
            aria-label={t("Lý do phản hồi (không bắt buộc)")}
            placeholder={t("Chia sẻ thêm (không bắt buộc)")}
            value={reason}
            maxLength={1000}
            onChange={(e) => setReason(e.target.value)}
          />
          <button disabled={busy} type="submit">
            {busy ? t("Đang gửi…") : t("Gửi phản hồi")}
          </button>
        </form>
      )}
      <span role="status">{t(status)}</span>
    </div>
  );
}
