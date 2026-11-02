// Màn chat: danh sách tin nhắn, ô nhập, trạng thái đang tìm/streaming/lỗi.
// Phụ trách: TV4 · [S2] UI chat cơ bản

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";
import Header from "../components/layout/Header";
import GraceMenuItem from "../components/layout/GraceMenuItem";
import type { Conversation } from "../api/types";
import { useConversations } from "../hooks/useConversations";
import { useChatStream } from "../hooks/useChatStream";
import MessageInput from "../components/chat/MessageInput";
import MessageList from "../components/chat/MessageList";
import { retryInput } from "../hooks/chatState";
import graceIcon from "../assets/ERN_Map_Icon_Site_of_Grace.png";
import { createUuid } from "../lib/uuid.ts";

// Thanh thu gọn chỉ dẫn tới chức năng đã có của web TV4.
// S2: ảnh item_ và hiệu ứng dùng chung nằm trong GraceMenuItem, thay RailIcon nét SVG trước đây.
function fresh(mode: Conversation["mode"]): Conversation {
  return {
    id: createUuid(),
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
  const [smallScreen, setSmallScreen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  // Màn hình nhỏ dùng thanh icon; menu chỉ phủ lên nội dung khi người dùng chủ động mở.
  useEffect(() => {
    const query = window.matchMedia("(max-width: 900px)");
    const foldOnSmallScreen = () => {
      setSmallScreen(query.matches);
      if (query.matches) setSidebarOpen(false);
    };
    foldOnSmallScreen();
    query.addEventListener("change", foldOnSmallScreen);
    return () => query.removeEventListener("change", foldOnSmallScreen);
  }, []);
  function closeMobileSidebar() {
    if (window.matchMedia("(max-width: 900px)").matches) {
      setSidebarOpen(false);
      requestAnimationFrame(() => toggleRef.current?.focus());
    }
  }
  const history = useConversations();
  const [mode, setMode] = useState<Conversation["mode"]>("api");
  const [draft, setDraft] = useState(() => fresh("api"));
  const [active, setActive] = useState(draft.id);
  const conversation = history.conversations.find((c) => c.id === active) ?? draft;
  const stream = useChatStream(history.update);
  function reset(nextMode: Conversation["mode"] = "api") {
    setMode(nextMode);
    const next = fresh(nextMode);
    setDraft(next);
    setActive(next.id);
    stream.clearError();
    navigate("/");
    closeMobileSidebar();
  }
  function send(text: string) {
    void stream.send(conversation, text);
  }
  function retry() {
    const input = retryInput(conversation);
    if (input) void stream.send(input.base, input.text);
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
      <img className="toggle-emblem" src={graceIcon} alt="" draggable={false} />
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
      {/* TV4: ghi chú đặt dưới ô chat, dùng chung cả màn chào và hội thoại. */}
      <p className="chat-ai-note">AI có thể mắc sai sót.</p>
    </>
  );
  return (
    <div
      className={`workspace${sidebarOpen ? "" : " sidebar-collapsed"}`}
      onKeyDown={(event) => {
        if (event.key === "Escape" && sidebarOpen) closeMobileSidebar();
        // Giữ điều hướng bàn phím trong menu khi menu phủ lên nội dung trên điện thoại.
        if (event.key === "Tab" && smallScreen && sidebarOpen) {
          const controls = Array.from(
            event.currentTarget.querySelectorAll<HTMLElement>(
              ".sidebar-toggle, .sidebar button:not(:disabled), .sidebar a[href]",
            ),
          ).filter((element) => element.getClientRects().length > 0);
          const first = controls[0];
          const last = controls.at(-1);
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
          }
        }
      }}
    >
      {sidebarToggle}
      {sidebarOpen && (
        <button
          type="button"
          className="sidebar-scrim"
          tabIndex={-1}
          aria-label="Đóng menu điều hướng"
          onClick={() => {
            setSidebarOpen(false);
            requestAnimationFrame(() => toggleRef.current?.focus());
          }}
        />
      )}
      <aside id="conversation-sidebar" className="sidebar" aria-label={"Lịch sử trò chuyện"}>
        <Header sidebarToggle={<span className="sidebar-toggle-space" aria-hidden="true" />} />
        <nav className="sidebar-rail" aria-label="Điều hướng chính">
          <GraceMenuItem icon="new" label="TRÒ CHUYỆN MỚI" disabled={stream.busy} onClick={() => reset()} />
          <GraceMenuItem icon="about" label="VỀ DỰ ÁN" to="/about" onClick={closeMobileSidebar} />
        </nav>

        {history.conversations.length > 0 && (
          <section className="conversation-history" aria-labelledby="conversation-history-title">
            <h2 id="conversation-history-title" className="history-heading">
              Tất cả
            </h2>
            <div className="history">
              {history.conversations.map((c) => (
                <div key={c.id} className={active === c.id ? "history-row selected" : "history-row"}>
                  <button
                    disabled={stream.busy}
                    onClick={() => {
                      setActive(c.id);
                      setMode(c.mode);
                      stream.clearError();
                      navigate("/");
                      closeMobileSidebar();
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
          </section>
        )}
        {history.storageError && <p role="status">{"Trình duyệt không lưu được lịch sử."}</p>}
        <GraceMenuItem
          className="sidebar-admin"
          to="/admin"
          icon="admin"
          label="QUẢN TRỊ"
          onClick={closeMobileSidebar}
        />
      </aside>
      {isChat ? (
        <section
          id="main"
          inert={smallScreen && sidebarOpen}
          className={`chat-panel${conversation.messages.length === 0 ? " chat-empty" : ""}`}
        >
          <div className="chat-content">
            {conversation.messages.length === 0 ? (
              <section className="welcome">
                <h1>{"Hôm nay bạn muốn khám phá điều gì?"}</h1>
                <p className="intro">{"Lần theo những bí ẩn của Elden Ring."}</p>
                <div className="input-area welcome-input">{composer}</div>
                <div className="suggestions" role="group" aria-label="Câu hỏi gợi ý">
                  {["Elden Ring là gì?", "Boss cuối là ai?", "Có bao nhiêu ending?"].map((question) => (
                    <button key={question} type="button" disabled={stream.busy} onClick={() => send(question)}>
                      {question}
                    </button>
                  ))}
                </div>
                <p className="scope-note">{"Cốt truyện trò chơi gốc · Tiếng Việt · Có thể tiết lộ nội dung"}</p>
              </section>
            ) : (
              <MessageList messages={conversation.messages} busy={stream.busy} demo={mode === "demo"} />
            )}
          </div>
          {conversation.messages.length > 0 && <div className="input-area">{composer}</div>}
        </section>
      ) : (
        <div className="document-panel" inert={smallScreen && sidebarOpen}>
          {children}
        </div>
      )}
    </div>
  );
}
