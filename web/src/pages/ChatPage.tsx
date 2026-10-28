// Màn chat: danh sách tin nhắn, ô nhập, trạng thái đang tìm/streaming/lỗi.
// Phụ trách: TV4 · [S2] UI chat cơ bản

import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import Header from "../components/layout/Header";
import type { Conversation } from "../api/types";
import { useConversations } from "../hooks/useConversations";
import { useChatStream } from "../hooks/useChatStream";
import MessageInput from "../components/chat/MessageInput";
import MessageList from "../components/chat/MessageList";
import type { DemoScenario } from "../api/demo";
import { retryInput } from "../hooks/chatState";

const questions = [
  ["01", "NHÂN VẬT", "Godrick the Grafted là ai?"],
  ["02", "SỰ KIỆN", "Night of the Black Knives là gì?"],
  ["03", "THẾ GIỚI", "Erdtree có ý nghĩa gì ở Lands Between?"],
];
// Thanh thu gọn chỉ dẫn tới chức năng đã có của web TV4.
function RailIcon({ name }: { name: "new" | "lore" | "history" | "about" | "admin" }) {
  const paths = {
    new: "M12 5H5v14h14v-7M10 14l1-4 7-7 3 3-7 7-4 1Z",
    lore: "M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15ZM16 16l5 5",
    history: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 7v5l3 2",
    about: "M12 3 2 8l10 5 10-5-10-5ZM6 10v6l6 3 6-3v-6",
    admin: "M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3ZM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  };
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
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
export default function ChatPage({ children }: { children?: ReactNode }) {
  // Sidebar dùng chung cho chat, About và Admin; nội dung hội thoại vẫn thuộc hooks hiện có.
  const isChat = useLocation().pathname === "/";
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const history = useConversations();
  const [mode, setMode] = useState<Conversation["mode"]>("demo");
  const [scenario, setScenario] = useState<DemoScenario>("success");
  const [draft, setDraft] = useState(() => fresh("demo"));
  const [active, setActive] = useState(draft.id);
  const conversation = history.conversations.find((c) => c.id === active) ?? draft;
  const stream = useChatStream(history.update);
  function reset(nextMode = mode) {
    const next = fresh(nextMode);
    setDraft(next);
    setActive(next.id);
    stream.clearError();
    navigate("/");
  }
  function send(text: string) {
    void stream.send(conversation, text, { scenario });
  }
  function retry() {
    const input = retryInput(conversation);
    if (input) void stream.send(input.base, input.text, { scenario });
  }
  const sidebarToggle = (
    <button
      type="button"
      className="sidebar-toggle"
      ref={toggleRef}
      aria-controls="conversation-sidebar"
      aria-expanded={sidebarOpen}
      aria-label={sidebarOpen ? "Đóng thanh bên" : "Mở thanh bên"}
      title={sidebarOpen ? "Đóng thanh bên" : "Mở thanh bên"}
      onClick={() => {
        setSidebarOpen((open) => !open);
        requestAnimationFrame(() => toggleRef.current?.focus());
      }}
    >
      <span className="toggle-emblem" aria-hidden="true">
        ✦
      </span>
      <svg
        className="toggle-arrow"
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
        <path d={sidebarOpen ? "M5 5v14M16 7l-5 5 5 5" : "M19 5v14M8 7l5 5-5 5"} />
      </svg>
    </button>
  );
  const composer = (
    <>
      {stream.error && (
        <div className="error-box" role="alert">
          {stream.error}
          <button disabled={stream.busy} onClick={retry}>
            {"Thử lại"}
          </button>
        </div>
      )}
      <MessageInput busy={stream.busy} onSend={send} onStop={stream.stop} />
      <p className="input-note">
        {"Kiểm chứng câu trả lời qua nguồn trích dẫn. Lore có thể bao gồm các cách diễn giải khác nhau."}
      </p>
    </>
  );
  return (
    <div className={`workspace${sidebarOpen ? "" : " sidebar-collapsed"}`}>
      {sidebarToggle}
      <aside id="conversation-sidebar" className="sidebar" aria-label={"Lịch sử trò chuyện"}>
        {!sidebarOpen && (
          <nav className="sidebar-rail" aria-label="Điều hướng thu gọn">
            <button
              type="button"
              title="Cuộc trò chuyện mới"
              aria-label="Cuộc trò chuyện mới"
              disabled={stream.busy}
              onClick={() => reset()}
            >
              <RailIcon name="new" />
            </button>
            <NavLink to="/" end title="Tra cứu lore" aria-label="Tra cứu lore">
              <RailIcon name="lore" />
            </NavLink>
            <button
              type="button"
              title="Lịch sử trò chuyện"
              aria-label="Lịch sử trò chuyện"
              onClick={() => {
                setSidebarOpen(true);
                requestAnimationFrame(() => toggleRef.current?.focus());
              }}
            >
              <RailIcon name="history" />
            </button>
            <NavLink to="/about" title="Về dự án" aria-label="Về dự án">
              <RailIcon name="about" />
            </NavLink>
            <NavLink className="rail-admin" to="/admin" title="Quản trị" aria-label="Quản trị">
              <RailIcon name="admin" />
            </NavLink>
          </nav>
        )}
        <Header sidebarToggle={<span className="sidebar-toggle-space" aria-hidden="true" />} />
        <div className="sidebar-top">
          <span className="archive-label">
            <span className="status-dot" />
            {"KHO LORE / BASE GAME"}
          </span>
        </div>
        <button className="new-chat" disabled={stream.busy} onClick={() => reset()}>
          {"＋ Cuộc trò chuyện mới"}
        </button>
        <nav className="sidebar-nav" aria-label={"Tra cứu lore"}>
          <NavLink to="/" end>
            <span aria-hidden="true">✦</span>
            {"Tra cứu lore"}
          </NavLink>
        </nav>

        <span className="eyebrow">{"NHỮNG TRANG ĐÃ MỞ"}</span>
        <div className="history">
          {!history.conversations.length && (
            <p className="muted">{"Những câu chuyện bạn tìm kiếm sẽ được lưu tại đây."}</p>
          )}
          {history.conversations.map((c) => (
            <div key={c.id} className={active === c.id ? "history-row selected" : "history-row"}>
              <button
                disabled={stream.busy}
                onClick={() => {
                  setActive(c.id);
                  setMode(c.mode);
                  stream.clearError();
                  navigate("/");
                }}
              >
                <span>{c.title}</span>
                <small>
                  {c.mode === "demo" ? "Xem thử" : "API"} · {new Date(c.updatedAt).toLocaleDateString("vi-VN")}
                </small>
              </button>
              <button
                disabled={stream.busy}
                className="delete"
                aria-label={`${"Xóa"} ${c.title}`}
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
          <div className="sidebar-controls">
            <label>
              {"Chế độ"}{" "}
              <select
                aria-label={"Chế độ trò chuyện"}
                value={mode}
                disabled={stream.busy}
                onChange={(e) => {
                  const next = e.target.value as Conversation["mode"];
                  setMode(next);
                  reset(next);
                }}
              >
                <option value="demo">{"Xem thử giao diện"}</option>
                <option value="api">{"Kết nối API (JSON)"}</option>
                <option value="api-stream">{"Kết nối API (SSE)"}</option>
              </select>
            </label>
            {mode === "demo" && (
              <label>
                {"Tình huống thử"}{" "}
                <select
                  aria-label={"Tình huống thử"}
                  value={scenario}
                  disabled={stream.busy}
                  onChange={(e) => setScenario(e.target.value as DemoScenario)}
                >
                  <option value="success">{"Thành công"}</option>
                  <option value="error">{"Lỗi"}</option>
                  <option value="slow">{"Phản hồi chậm"}</option>
                </select>
              </label>
            )}
          </div>
          <nav className="sidebar-nav" aria-label={"Điều hướng chính"}>
            <NavLink to="/about">
              <span aria-hidden="true">◇</span>
              {"Về dự án"}
            </NavLink>
            <NavLink to="/admin">
              <span aria-hidden="true">⚙</span>
              {"Quản trị"}
            </NavLink>
          </nav>
          <small>
            {"Lịch sử lưu trên trình duyệt này."}
            <br />
            {"Tối đa 30 cuộc trò chuyện."}
          </small>
          {history.storageError && <p role="status">{"Trình duyệt không lưu được lịch sử."}</p>}
        </div>
      </aside>
      {isChat ? (
        <section id="main" className={`chat-panel${conversation.messages.length === 0 ? " chat-empty" : ""}`}>
          <div className="mode-note" role="status">
            {mode === "demo"
              ? "Đang xem thử với dữ liệu minh họa. Câu trả lời không phải kết quả RAG thật."
              : mode === "api"
                ? "Gửi JSON tới /api/v1/chat. Cần API mock và contract do TV1 xác nhận."
                : "Gửi câu hỏi tới API dự án. Dịch vụ chat cần được backend triển khai và khởi động."}
          </div>
          <div className="chat-content">
            {conversation.messages.length === 0 ? (
              <section className="welcome">
                <span className="welcome-mark" aria-hidden="true">
                  ✦
                </span>
                <h1>{"Hôm nay bạn muốn khám phá điều gì?"}</h1>
                <p className="intro">{"Lần theo những bí ẩn của Elden Ring."}</p>
                <div className="input-area welcome-input">{composer}</div>
                <div className="suggestions">
                  {questions.map(([number, category, question]) => (
                    <button key={number} title={question} aria-label={question} onClick={() => send(question)}>
                      <span className="suggestion-icon" aria-hidden="true">
                        {number === "01" ? "♙" : number === "02" ? "◇" : "✧"}
                      </span>
                      <strong>{category}</strong>
                    </button>
                  ))}
                </div>
                <p className="scope-note">{"✧ Chỉ lore base game · Tiếng Việt & English · Có thể chứa spoiler"}</p>
              </section>
            ) : (
              <MessageList messages={conversation.messages} busy={stream.busy} demo={mode === "demo"} />
            )}
          </div>
          {conversation.messages.length > 0 && <div className="input-area">{composer}</div>}
        </section>
      ) : (
        <div className="document-panel">{children}</div>
      )}
    </div>
  );
}
