// Type viết tay theo backend/app/api/schemas.
// Phụ trách: TV4 · [S2] File api.ts viết tay

// S2: sao chép phần hợp đồng công khai từ web; không phụ thuộc UI hoặc endpoint admin.
export const MAX_MESSAGE_CHARS = 2000;
export const MAX_FEEDBACK_CHARS = 500;
export function isUuid(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
export interface Source {
  index: number;
  title: string;
  section?: string | null;
  url: string;
  text?: string | null;
  origin?: "web" | "corpus";
}

export function isSource(value: unknown): value is Source {
  if (!value || typeof value !== "object") return false;
  const source = value as Record<string, unknown>;
  return (
    Number.isInteger(source.index) &&
    Number(source.index) > 0 &&
    typeof source.title === "string" &&
    typeof source.url === "string" &&
    (source.section == null || typeof source.section === "string") &&
    (source.text == null || typeof source.text === "string") &&
    (source.origin === undefined || source.origin === "web" || source.origin === "corpus")
  );
}
export interface ChatRequest {
  conversation_id?: string | null;
  message: string;
  channel: "web" | "discord";
  external_ref?: string | null;
  options?: { lang?: "auto" | "vi" | "en"; spoilers?: boolean };
}
export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  sources: Source[];
  grounded: boolean;
  latency_ms: number;
}
export interface FeedbackRequest {
  message_id: string;
  rating: 1 | -1;
  reason?: string | null;
}
export interface ConversationOut {
  id: string;
  channel: "web" | "discord";
  created_at: string;
  messages: {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources: Source[];
    grounded?: boolean | null;
    created_at: string;
  }[];
}
export type StreamEvent =
  | { type: "status"; status: string }
  | { type: "token"; token: string }
  | { type: "sources"; sources: Source[] }
  | { type: "done"; data: Omit<ChatResponse, "answer" | "sources"> }
  | { type: "error"; message: string };
