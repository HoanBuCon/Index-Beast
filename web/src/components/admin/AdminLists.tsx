// Danh sách hội thoại / phản hồi trong khung cuộn cố định và khung JSON của trace.
// Phụ trách: TV1 · [S5] Trang admin

import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { AdminStats } from "../../api/types";
import { copyText, isSelectAllKey, selectOnly } from "../../lib/adminTrace";
import type { CopyResult } from "../../lib/adminTrace";

type Conversation = AdminStats["conversations"][number];
type Feedback = AdminStats["feedback"][number];

// Trace cần id câu trả lời; hội thoại chưa có câu trả lời thì gửi id hội thoại (API vẫn tra theo hội thoại được).
export function traceTargetOf(c: Pick<Conversation, "id" | "last_message_id">): string {
  return c.last_message_id ?? c.id;
}

interface ListProps {
  canView: boolean;
  onViewTrace: (id: string) => void;
}

export function ConversationList({
  conversations,
  canView,
  onViewTrace,
}: ListProps & { conversations: Conversation[] }) {
  if (!conversations.length) return <p className="muted">{"Chưa có hội thoại nào."}</p>;
  return (
    <div className="admin-scroll" tabIndex={0} role="region" aria-label="Danh sách hội thoại gần đây">
      <ul className="admin-list">
        {conversations.map((c) => (
          <li key={c.id}>
            <div className="admin-row">
              <div>
                <strong>{c.title}</strong>
                <small>{new Date(c.created_at).toLocaleString("vi-VN")}</small>
                <small>
                  {"Message ID: "}
                  {c.last_message_id ? <code>{c.last_message_id}</code> : "chưa có câu trả lời"}
                </small>
                <small>
                  {"Hội thoại: "}
                  <code>{c.id}</code>
                </small>
              </div>
              <button
                type="button"
                disabled={!canView}
                aria-label={`Xem trace của hội thoại ${c.title}`}
                onClick={() => onViewTrace(traceTargetOf(c))}
              >
                {"Xem trace"}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function FeedbackList({ feedback, canView, onViewTrace }: ListProps & { feedback: Feedback[] }) {
  const unhelpful = feedback.filter((f) => f.rating < 0);
  if (!unhelpful.length) return <p className="muted">{"Chưa có phản hồi chưa hữu ích."}</p>;
  return (
    <div className="admin-scroll" tabIndex={0} role="region" aria-label="Danh sách phản hồi chưa hữu ích">
      <ul className="admin-list">
        {unhelpful.map((f, i) => (
          <li key={`${f.message_id}-${i}`}>
            <div className="admin-row">
              <div>
                <strong>{f.reason || "Không ghi lý do"}</strong>
                <small>
                  <code>{f.message_id}</code>
                </small>
              </div>
              <button
                type="button"
                disabled={!canView}
                aria-label={`Xem trace của phản hồi ${f.message_id}`}
                onClick={() => onViewTrace(f.message_id)}
              >
                {"Xem trace"}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TraceViewer({ value }: { value: unknown }) {
  const text = JSON.stringify(value, null, 2);
  const [state, setState] = useState<CopyResult | "idle">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  async function copy() {
    setState(await copyText(text, typeof navigator === "undefined" ? undefined : navigator.clipboard));
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 3000);
  }
  function onKeyDown(event: KeyboardEvent<HTMLPreElement>) {
    if (isSelectAllKey(event)) selectOnly(event, event.currentTarget);
  }
  return (
    <div className="trace-viewer">
      <div className="trace-toolbar">
        <button type="button" onClick={() => void copy()}>
          {state === "copied" ? "Đã sao chép" : "Sao chép"}
        </button>
        <span className="muted" role="status">
          {state === "failed" ? "Không sao chép được: hãy bấm vào khung, nhấn Ctrl+A rồi sao chép thủ công." : ""}
        </span>
      </div>
      <pre
        className="trace-json"
        tabIndex={0}
        role="region"
        aria-label="Kết quả trace dạng JSON, bấm vào rồi nhấn Ctrl+A để chọn"
        onKeyDown={onKeyDown}
      >
        {text}
      </pre>
    </div>
  );
}
