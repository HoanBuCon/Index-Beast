// Màn chat: danh sách tin nhắn, ô nhập, trạng thái đang tìm/streaming/lỗi.
// Phụ trách: TV4 · [S2] UI chat cơ bản

import { useRef, useState } from "react";
import type { Conversation } from "../api/types";
import { useConversations } from "../hooks/useConversations";
import { useChatStream } from "../hooks/useChatStream";
import MessageInput from "../components/chat/MessageInput";
import MessageList from "../components/chat/MessageList";

const questions = [
  ["01", "NHÂN VẬT", "Godrick the Grafted là ai?"],
  ["02", "SỰ KIỆN", "Night of the Black Knives là gì?"],
  ["03", "THẾ GIỚI", "Erdtree có ý nghĩa gì ở Lands Between?"],
];
function fresh(mode: Conversation["mode"]): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "Cuộc trò chuyện mới",
    mode,
    serverId: null,
    messages: [],
    updatedAt: new Date().toISOString(),
  };
}
import { useLanguage } from "../lib/i18n";
export default function ChatPage() {
  const { t, language } = useLanguage();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const history = useConversations();
  const [mode, setMode] = useState<Conversation["mode"]>("demo");
  const [draft, setDraft] = useState(() => fresh("demo"));
  const [active, setActive] = useState(draft.id);
  const conversation = history.conversations.find((c) => c.id === active) ?? draft;
  const stream = useChatStream(history.update);
  function reset(nextMode = mode) {
    const next = fresh(nextMode);
    setDraft(next);
    setActive(next.id);
    stream.clearError();
  }
  function send(text: string) {
    void stream.send(conversation, text);
  }
  function retry() {
    const last = conversation.messages.findLastIndex((m) => m.role === "user");
    if (last < 0) return;
    void stream.send(
      { ...conversation, messages: conversation.messages.slice(0, last) },
      conversation.messages[last].content,
    );
  }
  const sidebarToggle = (
    <button
      type="button"
      className="sidebar-toggle"
      ref={toggleRef}
      aria-controls="conversation-sidebar"
      aria-expanded={sidebarOpen}
      aria-label={t(sidebarOpen ? "Đóng thanh bên" : "Mở thanh bên")}
      title={t(sidebarOpen ? "Đóng thanh bên" : "Mở thanh bên")}
      onClick={() => {
        setSidebarOpen((open) => !open);
        requestAnimationFrame(() => toggleRef.current?.focus());
      }}
    >
      <svg
        aria-hidden="true"
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <path d="M9 4v16" />
        <path d={sidebarOpen ? "m16 9-3 3 3 3" : "m13 9 3 3-3 3"} />
      </svg>
    </button>
  );
  return (
    <main id="main" className={`workspace${sidebarOpen ? "" : " sidebar-collapsed"}`}>
      <aside id="conversation-sidebar" className="sidebar" hidden={!sidebarOpen} aria-label={t("Lịch sử trò chuyện")}>
        <div className="sidebar-top">
          {sidebarOpen && sidebarToggle}
          <span className="archive-label">
            <span className="status-dot" />
            {t("KHO LORE / BASE GAME")}
          </span>
        </div>
        <button className="new-chat" disabled={stream.busy} onClick={() => reset()}>
          {t("＋ Cuộc trò chuyện mới")}
        </button>
        <span className="eyebrow">{t("NHỮNG TRANG ĐÃ MỞ")}</span>
        <div className="history">
          {!history.conversations.length && (
            <p className="muted">{t("Những câu chuyện bạn tìm kiếm sẽ được lưu tại đây.")}</p>
          )}
          {history.conversations.map((c) => (
            <div key={c.id} className={active === c.id ? "history-row selected" : "history-row"}>
              <button
                disabled={stream.busy}
                onClick={() => {
                  setActive(c.id);
                  setMode(c.mode);
                  stream.clearError();
                }}
              >
                <span>{c.title}</span>
                <small>
                  {c.mode === "demo" ? t("Xem thử") : "API"} ·{" "}
                  {new Date(c.updatedAt).toLocaleDateString(language === "vi" ? "vi-VN" : "en-GB")}
                </small>
              </button>
              <button
                disabled={stream.busy}
                className="delete"
                aria-label={`${t("Xóa")} ${c.title}`}
                onClick={() => {
                  history.remove(c.id);
                  if (active === c.id) reset();
                }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <div className="sidebar-foot">
          <span className="archive-seal" aria-hidden="true">
            ✧
          </span>
          <p>
            {t("Mọi truyền thuyết đều")}
            <br />
            {t("để lại một dấu vết.")}
          </p>
          <small>
            {t("Lịch sử lưu trên trình duyệt này.")}
            <br />
            {t("Tối đa 30 cuộc trò chuyện.")}
          </small>
          {history.storageError && <p role="status">{t("Trình duyệt không lưu được lịch sử.")}</p>}
        </div>
      </aside>
      <section className="chat-panel">
        <div className="chat-toolbar">
          <div className="toolbar-start">{!sidebarOpen && sidebarToggle}</div>
          <label>
            {t("Chế độ")}{" "}
            <select
              aria-label={t("Chế độ trò chuyện")}
              value={mode}
              disabled={stream.busy}
              onChange={(e) => {
                const next = e.target.value as Conversation["mode"];
                setMode(next);
                reset(next);
              }}
            >
              <option value="demo">{t("Xem thử giao diện")}</option>
              <option value="api">{t("Kết nối API")}</option>
            </select>
          </label>
        </div>
        <div className="mode-note" role="status">
          {mode === "demo"
            ? t("Đang xem thử với dữ liệu minh họa. Câu trả lời không phải kết quả RAG thật.")
            : t("Gửi câu hỏi tới API dự án. Dịch vụ chat cần được backend triển khai và khởi động.")}
        </div>
        <div className="chat-content">
          {conversation.messages.length === 0 ? (
            <section className="welcome">
              <div className="rune" aria-hidden="true">
                <span>✦</span>
              </div>
              <p className="eyebrow">A FRAGMENT OF THE LANDS BETWEEN</p>
              <h1>
                {t("Mỗi câu hỏi,")}
                <br />
                {t("một mảnh")} <em>{t("truyền thuyết.")}</em>
              </h1>
              <p className="intro">
                {t("Lần theo những bí ẩn của Elden Ring.")}
                <br />
                {t("Khám phá nhân vật, sự kiện và câu chuyện — cùng nguồn tham chiếu.")}
              </p>
              <div className="suggestions">
                {questions.map(([number, category, question]) => (
                  <button key={number} onClick={() => send(t(question))}>
                    <span className="suggestion-top">
                      <span>
                        {number} / {t(category)}
                      </span>
                      <span>↗</span>
                    </span>
                    <strong>{t(question)}</strong>
                  </button>
                ))}
              </div>
              <p className="scope-note">{t("✧ Chỉ lore base game · Tiếng Việt & English · Có thể chứa spoiler")}</p>
            </section>
          ) : (
            <MessageList messages={conversation.messages} busy={stream.busy} demo={mode === "demo"} />
          )}
        </div>
        <div className="input-area">
          {stream.error && (
            <div className="error-box" role="alert">
              {t(stream.error)}
              <button disabled={stream.busy} onClick={retry}>
                {t("Thử lại")}
              </button>
            </div>
          )}
          <MessageInput busy={stream.busy} onSend={send} onStop={stream.stop} />
          <p className="input-note">
            {t("Kiểm chứng câu trả lời qua nguồn trích dẫn. Lore có thể bao gồm các cách diễn giải khác nhau.")}
          </p>
        </div>
      </section>
    </main>
  );
}
