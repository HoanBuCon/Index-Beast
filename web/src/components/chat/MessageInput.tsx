// Ô nhập (Enter gửi, Shift+Enter xuống dòng), nút Gửi/Dừng.
// Phụ trách: TV4 · [S2] UI chat cơ bản

import { useState } from "react";
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
        id="question"
        placeholder={"Hỏi về một nhân vật, một bí ẩn, một thời đại…"}
        value={text}
        maxLength={8000}
        rows={text.includes("\n") ? Math.min(text.split("\n").length, 5) : 1}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
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
