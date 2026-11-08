// TV4 · Chỉ đọc một bản trả lời Discord; không mở lịch sử hoặc gửi câu hỏi mới bằng share token.
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
import { readSharedAnswer } from "../api/answerShares";
import type { SharedAnswer } from "../api/answerShares";
import MessageList from "../components/chat/MessageList";

export default function SharedAnswerPage() {
  const { hash } = useLocation();
  const [answer, setAnswer] = useState<SharedAnswer | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setAnswer(null);
    setError("");
    readSharedAnswer(hash.slice(1), controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setAnswer(value);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("Link đã hết hạn, không hợp lệ hoặc dịch vụ chưa sẵn sàng. Bạn có thể thử tải lại.");
      });
    return () => controller.abort();
  }, [hash, attempt]);
  return (
    <main id="main" className="document shared-answer">
      <h1>Câu trả lời từ Discord</h1>
      <p className="muted">
        Bản chia sẻ chỉ đọc một câu trả lời. Người có link có thể xem cho tới khi hết hạn; link không mở toàn bộ hội
        thoại.
      </p>
      {!answer && !error && <p role="status">Đang tải câu trả lời…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => setAttempt((n) => n + 1)}>
            Thử lại
          </button>
        </div>
      )}
      {answer && (
        <>
          <p className="muted">Hết hạn: {new Date(answer.expires_at).toLocaleString("vi-VN")}</p>
          <MessageList
            autoScroll={false}
            busy={false}
            demo={false}
            messages={[
              { id: "shared-question", role: "user", content: answer.question, sources: [] },
              {
                id: "shared-answer",
                role: "assistant",
                content: answer.answer,
                sources: answer.sources,
                grounded: answer.grounded,
              },
            ]}
          />
          <p>AI có thể mắc sai sót. Hãy kiểm tra các nguồn được dẫn.</p>
        </>
      )}
      <Link to="/">Trở về trò chuyện</Link>
    </main>
  );
}
