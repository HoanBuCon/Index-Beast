import { useEffect, useRef, useState } from "react";
import type { Clarification } from "../../api/types";
import { MAX_MESSAGE_CHARS } from "../../api/types";

export default function ClarificationForm({
  question,
  disabled,
  onAnswer,
}: {
  question: Clarification;
  disabled: boolean;
  onAnswer: (text: string, id: string) => Promise<boolean> | void;
}) {
  const [text, setText] = useState("");
  const [expired, setExpired] = useState(() => Date.parse(question.expires_at) <= Date.now());
  const sending = useRef(false);
  useEffect(() => {
    const timer = setTimeout(() => setExpired(true), Math.max(0, Date.parse(question.expires_at) - Date.now()));
    return () => clearTimeout(timer);
  }, [question.expires_at]);
  async function submit(value = text) {
    if (disabled || expired || sending.current || !value.trim()) return;
    sending.current = true;
    try {
      if (await onAnswer(value, question.id)) setText("");
    } finally {
      sending.current = false;
    }
  }
  return (
    <form
      className="clarification-form"
      aria-label="Bổ sung thông tin"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label htmlFor={`clarification-${question.id}`}>Trả lời bổ sung</label>
      <div className="composer">
        <textarea
          id={`clarification-${question.id}`}
          value={text}
          rows={2}
          placeholder="Nhập câu trả lời của bạn…"
          maxLength={MAX_MESSAGE_CHARS}
          disabled={disabled || expired}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              void submit();
            }
          }}
        />
        <button disabled={disabled || expired || !text.trim()} type="submit">
          {expired ? "Đã hết hạn — gửi lại yêu cầu" : disabled ? "Đang xử lý…" : "Tiếp tục"}
        </button>
      </div>
      <button type="button" disabled={disabled || expired} onClick={() => void submit("Hủy yêu cầu đang chờ.")}>
        Hủy yêu cầu
      </button>
      <small> Enter để gửi, Shift+Enter xuống dòng. Bạn cũng có thể gửi câu hỏi mới trong ô chat chính.</small>
    </form>
  );
}
