// Ô nhập (Enter gửi, Shift+Enter xuống dòng), nút Gửi/Dừng.
// Phụ trách: TV4 · [S2] UI chat cơ bản

import { useLayoutEffect, useRef, useState } from "react";
import { MAX_MESSAGE_CHARS } from "../../api/types";

// Đo cả dòng xuống hàng tự nhiên; giới hạn chiều cao rồi cuộn nội dung dài.
function fitTextarea(element: HTMLTextAreaElement) {
  const styles = getComputedStyle(element);
  const minHeight = Number.parseFloat(styles.minHeight) || 36;
  const maxHeight = Number.parseFloat(styles.maxHeight) || 180;
  element.style.height = "auto";
  const height = element.scrollHeight;
  element.style.height = `${Math.min(maxHeight, Math.max(minHeight, height))}px`;
  element.style.overflowY = height > maxHeight ? "auto" : "hidden";
}
export default function MessageInput({
  busy,
  onSend,
  onStop,
}: {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const composing = useRef(false);
  useLayoutEffect(() => {
    // Trình duyệt hỗ trợ tự giãn sẽ không cần đo lại DOM sau mỗi ký tự.
    if (CSS.supports("field-sizing", "content")) return;
    if (textareaRef.current) fitTextarea(textareaRef.current);
  }, [text]);
  useLayoutEffect(() => {
    if (CSS.supports("field-sizing", "content")) return;
    const element = textareaRef.current;
    if (!element) return;
    let previousWidth = element.getBoundingClientRect().width;
    const observer = new ResizeObserver(() => {
      const width = element.getBoundingClientRect().width;
      if (width !== previousWidth) {
        previousWidth = width;
        fitTextarea(element);
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  function submit() {
    if (!busy && text.trim()) {
      onSend(text.trim());
      setText("");
    }
  }
  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      {/* Đại kiếm chỉ là lớp trang trí, không nhận chuột hoặc thay đổi thao tác nhập/gửi. */}
      <span className="composer-sword" aria-hidden="true">
        <span className="sword-blade" />
        <svg className="sword-hilt" width="76" height="80" viewBox="0 0 76 80" fill="none">
          <path d="M10 33h44v14H10z" fill="#24271f" stroke="#8b7950" />
          <path d="M3 33 10 28l8 12-8 12-7-5z" fill="#8b7950" />
          <path d="m23 34 5 12m7-12 5 12" stroke="#8b7950" />
          <path d="m54 9 10-5 7 6-7 18v24l7 18-7 6-10-5 4-20V29z" fill="#393c2c" stroke="#b49a60" />
          <path d="M59 34h13v12H59z" fill="#b49a60" />
        </svg>
      </span>
      <label className="sr-only" htmlFor="question">
        {"Câu hỏi về lore Elden Ring"}
      </label>
      <textarea
        ref={textareaRef}
        id="question"
        placeholder={"Hỏi về một nhân vật, một bí ẩn, một thời đại…"}
        value={text}
        maxLength={MAX_MESSAGE_CHARS}
        aria-describedby="question-limit"
        rows={1}
        onChange={(e) => setText(e.target.value)}
        onCompositionStart={() => {
          composing.current = true;
        }}
        onCompositionEnd={() => {
          composing.current = false;
        }}
        onKeyDown={(e) => {
          if (
            e.key === "Enter" &&
            !e.shiftKey &&
            !composing.current &&
            !e.nativeEvent.isComposing &&
            e.nativeEvent.keyCode !== 229
          ) {
            e.preventDefault();
            if (!e.repeat) submit();
          }
        }}
      />
      <div className="composer-bottom">
        <small>{"Enter để gửi · Shift + Enter xuống dòng"}</small>
        {busy ? (
          <button type="button" className="primary" onClick={onStop}>
            <span aria-hidden="true">■</span>
            <span className="sr-only">{"■ Dừng"}</span>
          </button>
        ) : (
          <button
            className="primary send-button"
            disabled={!text.trim()}
            type="submit"
            aria-label={"Gửi câu hỏi"}
            title={"Gửi câu hỏi"}
          >
            <span className="sr-only">{"Gửi câu hỏi"}</span>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M3.3 2.8a1 1 0 0 0-1.4 1.2l2.6 6.5L14 12l-9.5 1.5L1.9 20a1 1 0 0 0 1.4 1.2l18-8.3a1 1 0 0 0 0-1.8l-18-8.3Z" />
            </svg>
          </button>
        )}
      </div>
      <span id="question-limit" className="sr-only">
        Tối đa {MAX_MESSAGE_CHARS} ký tự. Enter để gửi, Shift và Enter để xuống dòng.
      </span>
    </form>
  );
}
