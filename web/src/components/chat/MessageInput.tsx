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
      <label className="sr-only" htmlFor="question">
        {"Câu hỏi về lore Elden Ring"}
      </label>
      <textarea
        ref={textareaRef}
        id="question"
        placeholder={"Hỏi về một nhân vật, một bí ẩn, một thời đại…"}
        value={text}
        maxLength={MAX_MESSAGE_CHARS}
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
            className="primary"
            disabled={!text.trim()}
            type="submit"
            aria-label={"Gửi câu hỏi"}
            title={"Gửi câu hỏi"}
          >
            <span className="sr-only">{"Gửi câu hỏi"}</span>
            <span aria-hidden="true">↑</span>
          </button>
        )}
      </div>
    </form>
  );
}
