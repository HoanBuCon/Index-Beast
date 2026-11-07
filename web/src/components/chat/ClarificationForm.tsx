import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Clarification } from "../../api/types";
import { MAX_MESSAGE_CHARS } from "../../api/types";
import "../../styles/clarification.css";

function fitSupplement(element: HTMLTextAreaElement) {
  const style = getComputedStyle(element);
  const minHeight = Number.parseFloat(style.minHeight);
  const maxHeight = Number.parseFloat(style.maxHeight);
  element.style.height = "auto";
  // scrollHeight làm tròn pixel; giữ chiều cao CSS lẻ khi ô chưa cần giãn.
  const height = element.scrollHeight <= Math.ceil(minHeight) ? minHeight : element.scrollHeight;
  element.style.height = `${Math.min(maxHeight, Math.max(minHeight, height))}px`;
}

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
  const input = useRef<HTMLTextAreaElement>(null);
  // TV4: ô phụ tự giãn theo nội dung, không dùng lưới/nút gửi của composer chính.
  useLayoutEffect(() => {
    if (input.current) fitSupplement(input.current);
  }, [text]);
  useLayoutEffect(() => {
    const element = input.current;
    if (!element) return;
    let width = element.getBoundingClientRect().width;
    const observer = new ResizeObserver(() => {
      const nextWidth = element.getBoundingClientRect().width;
      if (nextWidth !== width) {
        width = nextWidth;
        fitSupplement(element);
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
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
    <div className="clarification-group">
      <form
        className="clarification-form"
        aria-label="Bổ sung thông tin"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="clarification-title" htmlFor={`clarification-${question.id}`}>
          Trả lời bổ sung
        </label>
        <div className="clarification-divider" aria-hidden="true" />
        <div className="clarification-panel">
          <textarea
            ref={input}
            className="clarification-input"
            id={`clarification-${question.id}`}
            value={text}
            rows={1}
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
        </div>
        <div className="clarification-footer">
          <button
            className="clarification-confirm"
            disabled={disabled || expired || !text.trim()}
            type="submit"
            aria-label="OK — gửi câu trả lời bổ sung bằng Enter"
            aria-keyshortcuts="Enter"
          >
            OK
          </button>
        </div>
        <div className="clarification-footer">
          <button
            className="clarification-confirm clarification-cancel"
            type="button"
            disabled={disabled || expired}
            onClick={() => void submit("Hủy yêu cầu đang chờ.")}
          >
            Hủy yêu cầu
          </button>
        </div>
        <p className="clarification-status" role="status" aria-live="polite">
          {expired ? "Đã hết hạn — gửi lại yêu cầu trong ô chat chính." : disabled ? "Đang xử lý…" : ""}
        </p>
      </form>
      <div className="clarification-help">
        <small>Enter để gửi · Shift+Enter xuống dòng. Bạn cũng có thể hỏi mới trong ô chat chính.</small>
      </div>
    </div>
  );
}
