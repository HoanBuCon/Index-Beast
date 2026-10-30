// Admin: hội thoại + trace, feedback 👎, trạng thái ingestion, kết quả eval.
// Phụ trách: TV4 · [S5] Trang admin

import { useEffect, useRef, useState } from "react";
import type { AdminStats } from "../api/types";
import { getAdminStats, getTrace } from "../api/client";
export default function AdminPage() {
  const [token, setToken] = useState("");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [trace, setTrace] = useState<unknown>(null);
  const [messageId, setMessageId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function load(kind: "stats" | "trace") {
    controller.current?.abort();
    const next = new AbortController();
    controller.current = next;
    setBusy(true);
    setError("");
    try {
      if (kind === "stats") setStats(await getAdminStats(token.trim(), next.signal));
      else setTrace(await getTrace(token.trim(), messageId.trim(), next.signal));
    } catch (cause) {
      if (!next.signal.aborted) setError(cause instanceof Error ? cause.message : "Không tải được dữ liệu.");
    } finally {
      if (!next.signal.aborted) setBusy(false);
    }
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
        {"Giao diện kết nối API quản trị do TV1 phụ trách. Chưa có dữ liệu thật khi API chưa sẵn sàng."}
      </p>
      <form
        className="admin-auth"
        onSubmit={(e) => {
          e.preventDefault();
          void load("stats");
        }}
      >
        <label htmlFor="admin-token">{"Token quản trị"}</label>
        <input
          id="admin-token"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(e) => {
            controller.current?.abort();
            setBusy(false);
            setError("");
            setToken(e.target.value);
            setStats(null);
            setTrace(null);
          }}
          required
        />
        <button className="primary" disabled={busy || !token.trim()}>
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
          <ul className="admin-list">
            {stats.conversations?.map((c) => (
              <li key={c.id}>
                <strong>{c.title}</strong>
                <small>
                  {c.created_at} · {c.id}
                </small>
              </li>
            ))}
          </ul>
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
            void load("trace");
          }}
        >
          <label className="sr-only" htmlFor="message-id">
            Message ID
          </label>
          <input
            id="message-id"
            placeholder="Message ID"
            value={messageId}
            onChange={(e) => setMessageId(e.target.value)}
            required
          />
          <button disabled={!token.trim() || !messageId.trim() || busy}>{"Xem trace"}</button>
        </form>
        {trace !== null && <pre>{JSON.stringify(trace, null, 2)}</pre>}
      </section>
      <section>
        <h2>{"Phản hồi chưa hữu ích"}</h2>
        {stats ? (
          <ul className="admin-list">
            {stats.feedback
              ?.filter((f) => f.rating < 0)
              .map((f, i) => (
                <li key={`${f.message_id}-${i}`}>
                  <strong>{f.reason || "Không ghi lý do"}</strong>
                  <small>{f.message_id}</small>
                </li>
              ))}
          </ul>
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
