// Màn chat: danh sách tin nhắn, ô nhập, trạng thái đang tìm/streaming/lỗi.
// Phụ trách: TV4 · [S2] UI chat cơ bản

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import Header from "../components/layout/Header";
import GraceMenuItem from "../components/layout/GraceMenuItem";
import type { Conversation } from "../api/types";
import { useConversations } from "../hooks/useConversations";
import { useChatStream } from "../hooks/useChatStream";
import { useAuthContext } from "../hooks/AuthContext";
import ClaimPrompt from "../components/layout/ClaimPrompt";
import {
  accountConversationIds,
  claimDeclined,
  claimableGuestConversations,
  markClaimed,
  rememberClaimDeclined,
  stampOwner,
} from "../lib/accountData";
import AccountMenu from "../components/layout/AccountMenu";
import { claimGuestConversations, toLocalConversation } from "../api/auth";
import { getConversation } from "../api/client";
import MessageInput from "../components/chat/MessageInput";
import type { SearchMode } from "../components/chat/searchMode";
import MessageList from "../components/chat/MessageList";
import { retryInput } from "../hooks/chatState";
import graceIcon from "../assets/ERN_Map_Icon_Site_of_Grace.png";
import newChatIcon from "../../item_/MENU_Tab_22.png";
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
  const { pathname } = useLocation();
  const isChat = pathname === "/chat";
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
  const [mode, setMode] = useState<Conversation["mode"]>("api-stream");
  const [searchMode, setSearchMode] = useState<SearchMode>("auto");
  // Capabilities và đăng nhập tải một lần ở App (AuthContext), không gọi lặp ở đây.
  const auth = useAuthContext();
  const userId = auth.user?.id ?? null;
  // Chỉ hiện hội thoại khách hoặc của tài khoản hiện tại; bản của chủ khác bị dọn khi auth đã biết.
  const history = useConversations({ loading: auth.loading, userId });
  const identity = useRef(userId);
  identity.current = userId;
  const { searchAvailable, traceAvailable } = auth;
  const [draft, setDraft] = useState(() => fresh("api-stream"));
  const [active, setActive] = useState(draft.id);
  const conversation = history.conversations.find((c) => c.id === active) ?? draft;
  // Hội thoại tạo khi đang đăng nhập được gắn chủ để xóa khỏi trình duyệt lúc đăng xuất/xóa tài khoản.
  const stream = useChatStream(
    (c) =>
      history.update(
        stampOwner(
          history.conversations.find((x) => x.id === c.id),
          c,
          auth.user?.id,
        ),
      ),
    userId ?? "guest",
  );
  // Nhận hội thoại khách vào tài khoản chỉ sau khi người dùng đồng ý; chọn "Không" được nhớ trong phiên trình duyệt.
  const [declined, setDeclined] = useState(() => claimDeclined());
  const [claiming, setClaiming] = useState(false);
  const claimable = auth.user && !declined ? claimableGuestConversations(history.conversations) : [];
  async function acceptClaim() {
    const user = auth.user;
    if (!user) return;
    setClaiming(true);
    const done = new Set(await claimGuestConversations(claimable));
    if (identity.current !== user.id) return setClaiming(false); // đổi danh tính khi đang chờ: bỏ kết quả
    claimable.filter((c) => c.serverId && done.has(c.serverId)).forEach((c) => history.update(markClaimed(c, user.id)));
    setClaiming(false);
  }
  function declineClaim() {
    rememberClaimDeclined();
    setDeclined(true);
  }
  // Xóa bản lưu cục bộ thuộc tài khoản để người dùng kế tiếp trên trình duyệt không đọc được.
  function purgeAccountConversations(userId: string, serverIds: string[]) {
    const ids = accountConversationIds(history.conversations, userId, serverIds);
    ids.forEach((id) => history.remove(id));
    if (ids.includes(active)) reset();
  }
  // Hội thoại trên server chưa có bản trong trình duyệt này (đăng nhập từ thiết bị khác).
  const localServerIds = new Set(history.conversations.map((c) => c.serverId));
  const remoteOnly = auth.myConversations.filter((c) => !localServerIds.has(c.id));
  const [openError, setOpenError] = useState("");
  async function openRemote(id: string, title: string) {
    setOpenError("");
    const requestedBy = userId;
    try {
      // Không gửi X-Conversation-Token: server nhận ra chủ sở hữu qua cookie phiên.
      const loaded = {
        ...toLocalConversation(await getConversation(id), title),
        ...(requestedBy ? { ownerUserId: requestedBy } : {}),
      };
      if (identity.current !== requestedBy) return; // phản hồi của danh tính cũ: không ghi vào lịch sử hiện tại
      history.update(loaded);
      setActive(loaded.id);
      setMode(loaded.mode);
      stream.clearError();
      navigate("/chat");
      closeMobileSidebar();
    } catch {
      setOpenError("Không mở được hội thoại này. Vui lòng thử lại.");
    }
  }
  function reset(nextMode: Conversation["mode"] = "api-stream") {
    setMode(nextMode);
    const next = fresh(nextMode);
    setDraft(next);
    setActive(next.id);
    stream.clearError();
    navigate("/chat");
    closeMobileSidebar();
  }
  function send(text: string) {
    // S3: hội thoại API cũ cũng nhận SSE từ lượt gửi mới; giữ nguyên ID/token và lịch sử.
    void stream.send(conversation.mode === "api" ? { ...conversation, mode: "api-stream" } : conversation, text, {
      webSearch: searchAvailable ? searchMode : "off",
    });
  }
  function retry() {
    const input = retryInput(conversation);
    if (input)
      void stream.send(input.base.mode === "api" ? { ...input.base, mode: "api-stream" } : input.base, input.text, {
        webSearch: searchAvailable ? searchMode : "off",
        clarificationId: input.clarificationId,
        turnId: input.turnId,
      });
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
      <MessageInput
        busy={stream.busy}
        onSend={send}
        onStop={stream.stop}
        searchMode={searchMode}
        searchAvailable={searchAvailable && conversation.mode !== "demo"}
        onSearchChange={setSearchMode}
      />
      {/* TV4: ghi chú đặt dưới ô chat, dùng chung cả màn chào và hội thoại. */}
      <p className="chat-ai-note">INDEX BEAST có thể mắc sai sót.</p>
    </>
  );
  return (
    <div
      className={`workspace${sidebarOpen ? "" : " sidebar-collapsed"}`}
      onKeyDown={(event) => {
        // Dialog tự giữ focus và xử lý Esc; không để vòng Tab của sidebar giành thao tác này.
        if (event.target instanceof Element && event.target.closest("dialog")) return;
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
      {/* TV4 · Điện thoại (≤ 700 px): thanh tiêu đề thay cho cột icon; CSS ẩn thanh này ở màn rộng.
          Nút mở menu là sidebarToggle phía trên, được đặt vào góc trái thanh này. */}
      <div className="mobile-topbar">
        <span className="mobile-topbar__toggle-space" aria-hidden="true" />
        <Link to="/chat" className="mobile-topbar__brand" aria-label="Index Beast — trang chủ">
          INDEX <strong>BEAST</strong>
        </Link>
        <button
          type="button"
          className="mobile-topbar__new"
          aria-label="Trò chuyện mới"
          title="Trò chuyện mới"
          disabled={stream.busy}
          onClick={() => reset()}
        >
          <img src={newChatIcon} alt="" draggable={false} />
        </button>
      </div>
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
          <GraceMenuItem
            icon="about"
            label="VỀ DỰ ÁN"
            to="/about"
            disabled={stream.busy}
            onClick={closeMobileSidebar}
          />
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
                      navigate("/chat");
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
        {remoteOnly.length > 0 && (
          <section className="conversation-history" aria-labelledby="remote-history-title">
            <h2 id="remote-history-title" className="history-heading">
              Của tài khoản
            </h2>
            <div className="history">
              {remoteOnly.map((c) => (
                <div key={c.id} className="history-row">
                  <button disabled={stream.busy} onClick={() => void openRemote(c.id, c.title)}>
                    <span>{c.title}</span>
                    <small>{new Date(c.created_at).toLocaleDateString("vi-VN")}</small>
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
        {claimable.length > 0 && (
          <ClaimPrompt
            count={claimable.length}
            busy={claiming}
            onAccept={() => void acceptClaim()}
            onDecline={declineClaim}
          />
        )}
        {openError && <p role="alert">{openError}</p>}
        {history.storageError && <p role="status">{"Trình duyệt không lưu được lịch sử."}</p>}
        <AccountMenu
          name={auth.user?.display_name}
          canAdmin={auth.user?.is_admin === true || auth.traceAvailable}
          onNavigate={closeMobileSidebar}
          disabled={stream.busy || auth.loading}
          logoutError={auth.logoutError}
          onLogout={() => {
            const user = auth.user;
            const serverIds = auth.myConversations.map((c) => c.id);
            return auth.logout().then((ok) => {
              if (ok && user) {
                purgeAccountConversations(user.id, serverIds);
                navigate("/login");
                closeMobileSidebar();
              }
            });
          }}
          onDeleted={() => {
            // Server đã xóa mọi hội thoại của tài khoản: bỏ luôn mọi bản lưu trong trình duyệt thuộc tài khoản.
            if (auth.user)
              purgeAccountConversations(
                auth.user.id,
                auth.myConversations.map((c) => c.id),
              );
            auth.clearUser();
            reset();
            navigate("/login");
          }}
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
                <p className="scope-note">
                  {"Elden Ring · Cốt truyện, nhiệm vụ và gameplay · Có thể tiết lộ nội dung"}
                </p>
              </section>
            ) : (
              <MessageList
                messages={conversation.messages}
                busy={stream.busy}
                demo={mode === "demo"}
                conversationToken={conversation.serverToken}
                traceLinks={traceAvailable}
                onClarification={(text, id) => {
                  const failed = retryInput(conversation);
                  const retry = stream.error && failed?.clarificationId === id && failed.text === text ? failed : null;
                  const base = retry?.base ?? conversation;
                  return stream.send(base.mode === "api" ? { ...base, mode: "api-stream" } : base, text, {
                    webSearch: searchAvailable ? searchMode : "off",
                    clarificationId: id,
                    turnId: retry?.turnId,
                  });
                }}
              />
            )}
          </div>
          {conversation.messages.length > 0 && <div className="input-area">{composer}</div>}
        </section>
      ) : (
        <div
          className={`document-panel${pathname === "/answer" ? " chat-panel shared-answer-panel" : pathname === "/login" ? " chat-panel login-panel" : ""}`}
          inert={smallScreen && sidebarOpen}
        >
          {children}
        </div>
      )}
    </div>
  );
}
