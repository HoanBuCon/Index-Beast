// Type viết tay theo backend/app/api/schemas (ChatRequest, Source, DoneEvent…).
// Phụ trách: TV4 · [S2] File api.ts viết tay

// Hợp đồng frontend tạm theo SRS §5; chờ TV1 chốt OpenAPI v1.
// S2: đã đối chiếu docs/api/openapi.json v0.1.0; ghi chú trên mô tả bản nháp ban đầu.
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
  images?: ChatImage[];
  grounded: boolean;
  latency_ms: number;
}
// Additive backend contract: legacy responses/history may omit images.
export interface ChatImage {
  id: string;
  url: string;
  source_url: string;
  source_indices: number[];
  caption?: string | null;
  alt?: string | null;
  attribution?: string | null;
  license?: string | null;
  license_status?: string | null;
  file_page_url?: string | null;
  game_scope?: string | null;
  release_scope?: string | null;
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
    images?: ChatImage[];
    grounded?: boolean | null;
    created_at: string;
  }[];
}
export type StreamEvent =
  | { type: "status"; status: string }
  | { type: "token"; token: string }
  | { type: "sources"; sources: Source[]; images?: ChatImage[] }
  | { type: "done"; data: Omit<ChatResponse, "answer" | "sources" | "images"> }
  | { type: "error"; message: string };
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  images?: ChatImage[];
  serverId?: string;
  incomplete?: boolean;
  grounded?: boolean;
}
export interface Conversation {
  id: string;
  title: string;
  mode: "demo" | "api" | "api-stream";
  serverId: string | null;
  messages: Message[];
  updatedAt: string;
}
export interface AdminStats {
  conversations: { id: string; title: string; created_at: string }[];
  feedback: { message_id: string; reason?: string; rating: number }[];
  ingestion_jobs: { id: string; status: string; pages_ok: number }[];
  eval_runs: { id: string; metrics: Record<string, number> }[];
}
