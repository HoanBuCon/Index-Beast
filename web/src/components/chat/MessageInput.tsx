// Ô nhập (Enter gửi, Shift+Enter xuống dòng), nút Gửi/Dừng.
// Phụ trách: TV4 · [S2] UI chat cơ bản

import { useState } from "react";
import { useLanguage } from "../../lib/i18n";
export default function MessageInput({
  busy,
  onSend,
  onStop,
}: {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const { t } = useLanguage();
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
        {t("Câu hỏi về lore Elden Ring")}
      </label>
      <textarea
        id="question"
        placeholder={t("Hỏi về một nhân vật, một bí ẩn, một thời đại…")}
        value={text}
        maxLength={8000}
        rows={2}
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
        <small>{t("Enter để gửi · Shift + Enter xuống dòng")}</small>
        {busy ? (
          <button type="button" className="primary" onClick={onStop}>
            {t("■ Dừng")}
          </button>
        ) : (
          <button className="primary" disabled={!text.trim()} type="submit">
            {t("Gửi câu hỏi")}
            <span aria-hidden="true">↑</span>
          </button>
        )}
      </div>
    </form>
  );
}
