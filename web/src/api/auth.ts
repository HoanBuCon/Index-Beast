// Đăng nhập Discord theo docs/api/auth-tv4.md: web không bao giờ thấy token phiên (cookie httpOnly, cùng origin).
// Phụ trách: TV4 · [S5] Web đăng nhập Discord (viết hộ bởi agent của TV1)

import type { Conversation, ConversationOut } from "./types";
import { isUuid, isConversationToken } from "./types.ts";

export interface AuthUser {
  id: string;
  display_name: string;
  is_admin: boolean;
}
export interface MyConversation {
  id: string;
  title: string;
  created_at: string;
}
export interface Capabilities {
  authAvailable: boolean;
  searchAvailable: boolean;
  traceAvailable: boolean;
}

const BASE = "/api/v1";
// Production: web và API cùng origin sau Caddy; dev: proxy Vite. Cookie phiên đi kèm tự động.
const SAME_ORIGIN: RequestInit = { credentials: "same-origin" };

// Chỉ nhận đường dẫn tương đối ("/chat"); "//host" hoặc "/\\host" bị đổi về "/chat" (backend cũng lọc lại).
export function discordLoginUrl(next = "/chat"): string {
  const safe = /^\/(?![/\\])/.test(next) ? next : "/chat";
  return `${BASE}/auth/discord/login?next=${encodeURIComponent(safe)}`;
}

export async function getCapabilities(signal?: AbortSignal): Promise<Capabilities> {
  const none = { authAvailable: false, searchAvailable: false, traceAvailable: false };
  try {
    const response = await fetch(`${BASE}/chat/capabilities`, { ...SAME_ORIGIN, signal });
    if (!response.ok) return none;
    const data = await response.json();
    return {
      authAvailable: data?.auth_available === true,
      searchAvailable: data?.web_search_available === true,
      traceAvailable: data?.trace_available === true,
    };
  } catch {
    if (signal?.aborted) throw signal.reason;
    return none;
  }
}

// /auth/me luôn 200; lỗi mạng/503 coi như khách (null) để web vẫn dùng được.
export async function getMe(signal?: AbortSignal): Promise<AuthUser | null> {
  try {
    const response = await fetch(`${BASE}/auth/me`, { ...SAME_ORIGIN, signal });
    if (!response.ok) return null;
    const data = await response.json();
    const user = data?.user;
    if (
      data?.authenticated !== true ||
      !user ||
      typeof user.id !== "string" ||
      typeof user.display_name !== "string" ||
      typeof user.is_admin !== "boolean"
    )
      return null;
    return { id: user.id, display_name: user.display_name, is_admin: user.is_admin };
  } catch {
    if (signal?.aborted) throw signal.reason;
    return null;
  }
}

export async function logout(): Promise<boolean> {
  try {
    return (await fetch(`${BASE}/auth/logout`, { ...SAME_ORIGIN, method: "POST" })).ok;
  } catch {
    return false;
  }
}

export async function listMyConversations(signal?: AbortSignal): Promise<MyConversation[]> {
  try {
    const response = await fetch(`${BASE}/me/conversations`, { ...SAME_ORIGIN, signal });
    if (!response.ok) return [];
    const data: unknown = await response.json();
    if (!Array.isArray(data)) return [];
    return data.filter(
      (c): c is MyConversation => c && isUuid(c.id) && typeof c.title === "string" && typeof c.created_at === "string",
    );
  } catch {
    if (signal?.aborted) throw signal.reason;
    return [];
  }
}

// 204 = đã nhận; 404 (đã có chủ khác/không còn) và 401 (token sai) đều bỏ qua, không phải lỗi với người dùng.
export async function claimConversation(conversationId: string, conversationToken: string): Promise<boolean> {
  try {
    const response = await fetch(`${BASE}/me/conversations/claim`, {
      ...SAME_ORIGIN,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, conversation_token: conversationToken }),
    });
    return response.status === 204;
  } catch {
    return false;
  }
}

// Xóa tài khoản và toàn bộ hội thoại (FR-AUTH-08): DELETE /me, cần cookie phiên + cùng Origin; 204 và server xóa cookie.
// Endpoint nằm ở nhánh feature/s5-tv1-quyen-rieng-tu (chưa gộp vào develop khi viết phần web này).
export async function deleteAccount(): Promise<boolean> {
  try {
    return (await fetch(`${BASE}/me`, { ...SAME_ORIGIN, method: "DELETE" })).status === 204;
  } catch {
    return false;
  }
}

// Nhận mọi hội thoại khách đang lưu ở trình duyệt (cần serverId + serverToken hợp lệ); trả về các id đã nhận.
export async function claimGuestConversations(conversations: Conversation[]): Promise<string[]> {
  const claimable = conversations.filter(
    (c) => c.serverId && isUuid(c.serverId) && c.serverToken && isConversationToken(c.serverToken),
  );
  const results = await Promise.all(
    claimable.map(async (c) => ((await claimConversation(c.serverId!, c.serverToken!)) ? c.serverId! : null)),
  );
  return results.filter((id): id is string => id !== null);
}

// Hội thoại của tài khoản mở trên thiết bị khác: server nhận ra chủ qua cookie nên không có serverToken.
export function toLocalConversation(data: ConversationOut, title: string): Conversation {
  return {
    id: data.id,
    title,
    mode: "api-stream",
    serverId: data.id,
    updatedAt: data.created_at,
    messages: data.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      sources: m.sources,
      ...(m.images === undefined ? {} : { images: m.images }),
      ...(m.role === "assistant" ? { serverId: m.id, ...(m.grounded == null ? {} : { grounded: m.grounded }) } : {}),
    })),
  };
}
