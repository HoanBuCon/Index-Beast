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
    <main id="main" className="chat-content shared-answer">
      {/* TV4: cùng nền/cột chữ với chat, giữ thông tin chỉ đọc bên ngoài MessageList. */}
      <header className="shared-answer-heading">
        <h1>Câu trả lời từ Discord</h1>
        <p>
          Bản chia sẻ chỉ đọc một câu trả lời. Người có link có thể xem cho tới khi hết hạn; link không mở toàn bộ hội
          thoại.
        </p>
        {answer && (
          <p>
            Hết hạn: <time dateTime={answer.expires_at}>{new Date(answer.expires_at).toLocaleString("vi-VN")}</time>
          </p>
        )}
      </header>
      {!answer && !error && (
        <p className="shared-answer-status" role="status">
          Đang tải câu trả lời…
        </p>
      )}
      {error && (
        <div className="shared-answer-status error-box" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => setAttempt((n) => n + 1)}>
            Thử lại
          </button>
        </div>
      )}
      {answer && (
        <>
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
        </>
      )}
      <footer className="shared-answer-footer">
        {answer && <p className="chat-ai-note">AI có thể mắc sai sót. Hãy kiểm tra các nguồn được dẫn.</p>}
        <Link to="/">Trở về trò chuyện</Link>
      </footer>
    </main>
  );
}
