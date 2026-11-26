// Admin: hội thoại + trace, feedback 👎, trạng thái ingestion, kết quả eval.
// Phụ trách: TV4 · [S5] Trang admin

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import type { AdminStats } from "../api/types";
import { getAdminStats, getTrace } from "../api/client";
import { useAuthContext } from "../hooks/AuthContext";
import { ConversationList, FeedbackList, TraceViewer } from "../components/admin/AdminLists";
export default function AdminPage() {
  // Liên kết "Xem trace" ở câu trả lời mang theo message_id; token không đi theo URL, phải nhập tại đây.
  const [params] = useSearchParams();
  const [token, setToken] = useState("");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [trace, setTrace] = useState<unknown>(null);
  const [messageId, setMessageId] = useState(params.get("message_id") ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  // Quản trị viên đăng nhập Discord (is_admin) vào bằng cookie phiên; trạng thái lấy từ AuthContext, không gọi /auth/me lần nữa.
  const { user } = useAuthContext();
  const sessionAdmin = user?.is_admin ? user.display_name : null;
  useEffect(() => {
    if (sessionAdmin) void load(messageId.trim() ? ["stats", "trace"] : ["stats"]);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ tự tải một lần khi biết là quản trị viên
  }, [sessionAdmin]);
  const hasAccess = Boolean(token.trim()) || sessionAdmin !== null;
  // Token nhập tay (nếu có) được ưu tiên; không thì dựa vào cookie phiên.
  const credential = () => token.trim() || null;
  async function load(kinds: ("stats" | "trace")[], traceId = messageId) {
    controller.current?.abort();
    const next = new AbortController();
    controller.current = next;
    setBusy(true);
    setError("");
    const errors = new Set<string>();
    for (const kind of kinds) {
      try {
        if (kind === "stats") setStats(await getAdminStats(credential(), next.signal));
        else setTrace(await getTrace(credential(), traceId.trim(), next.signal));
      } catch (cause) {
        if (next.signal.aborted) return;
        errors.add(cause instanceof Error ? cause.message : "Không tải được dữ liệu.");
      }
    }
    setError([...errors].join(" "));
    setBusy(false);
  }
  // Nút "Xem trace" ở từng dòng: điền ô tra cứu rồi tải luôn (state chưa kịp cập nhật nên truyền id trực tiếp).
  function viewTrace(id: string) {
    setMessageId(id);
    setTrace(null);
    void load(["trace"], id);
  }
  function logout() {
    controller.current?.abort();
    setToken("");
    setStats(null);
    setTrace(null);
    setError("");
    setBusy(false);
  }
  return (
    <main id="main" className="document admin">
      <span className="eyebrow">{"BÀN ĐIỀU KHIỂN / 4 HOLLOWS"}</span>
      <h1>{"Quản trị kho lore"}</h1>
      <p className="lead">{"Hội thoại, phản hồi và chất lượng dữ liệu."}</p>
      <p className="mode-note">
        {sessionAdmin
          ? `Đã đăng nhập với tư cách quản trị viên: ${sessionAdmin}. Không cần token.`
          : "Đăng nhập Discord bằng tài khoản quản trị, hoặc nhập token quản trị để vận hành."}
      </p>
      <form
        className="admin-auth"
        onSubmit={(e) => {
          e.preventDefault();
          // Có sẵn message_id (từ liên kết Xem trace hoặc đã nhập) thì tải luôn trace cùng lúc kết nối
          void load(messageId.trim() ? ["stats", "trace"] : ["stats"]);
        }}
      >
        <label htmlFor="admin-token">{"Token quản trị"}</label>
        <input
          id="admin-token"
          type="password"
          autoComplete="off"
          required={sessionAdmin === null}
          value={token}
          onChange={(e) => {
            controller.current?.abort();
            setBusy(false);
            setError("");
            setToken(e.target.value);
            setStats(null);
            setTrace(null);
          }}
        />
        <button className="primary" disabled={busy || !hasAccess}>
          {busy ? "Đang tải…" : "Kết nối"}
        </button>
        <button type="button" onClick={logout}>
          {"Xóa phiên"}
        </button>
      </form>
      {error && (
        <p className="error-box" role="alert">
          {error}
        </p>
      )}
      <section>
        <h2>{"Hội thoại gần đây"}</h2>
        {stats ? (
          <ConversationList
            conversations={stats.conversations ?? []}
            canView={hasAccess && !busy}
            onViewTrace={viewTrace}
          />
        ) : (
          <p className="muted">{"Kết nối để xem hội thoại."}</p>
        )}
      </section>
      <section>
        <h2>{"Tra cứu trace"}</h2>
        <form
          className="trace-form"
          onSubmit={(e) => {
            e.preventDefault();
            void load(["trace"]);
          }}
        >
          <label className="sr-only" htmlFor="message-id">
            Message ID
          </label>
          <input
            id="message-id"
            placeholder="Message ID (hoặc ID hội thoại)"
            value={messageId}
            onChange={(e) => setMessageId(e.target.value)}
            required
          />
          <button disabled={!hasAccess || !messageId.trim() || busy}>{"Xem trace"}</button>
        </form>
        {trace === null && messageId.trim() && !error && (
          <p className="muted">
            {"Đăng nhập quản trị hoặc nhập token rồi bấm Kết nối (hoặc Xem trace) để xem trace của mã này."}
          </p>
        )}
        {trace !== null && <TraceViewer value={trace} />}
      </section>
      <section>
        <h2>{"Phản hồi chưa hữu ích"}</h2>
        {stats ? (
          <FeedbackList feedback={stats.feedback ?? []} canView={hasAccess && !busy} onViewTrace={viewTrace} />
        ) : (
          <p className="muted">{"Chưa tải phản hồi."}</p>
        )}
      </section>
      <div className="admin-columns">
        <section>
          <h2>Ingestion</h2>
          {stats?.ingestion_jobs?.map((job) => (
            <p key={job.id}>
              {job.id} · {job.status} · {job.pages_ok} {"trang"}
            </p>
          ))}
          {!stats?.ingestion_jobs?.length && <p className="muted">{"Chưa có job để hiển thị."}</p>}
        </section>
        <section>
          <h2>{"Kết quả đánh giá"}</h2>
          {stats?.eval_runs?.map((run) => (
            <div key={run.id}>
              <h3>{run.id}</h3>
              <pre>{JSON.stringify(run.metrics, null, 2)}</pre>
            </div>
          ))}
          {!stats?.eval_runs?.length && <p className="muted">{"Chưa có kết quả eval."}</p>}
        </section>
      </div>
    </main>
  );
}
