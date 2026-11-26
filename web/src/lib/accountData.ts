// Dữ liệu hội thoại gắn với tài khoản trong localStorage: đánh dấu chủ, chọn bản cần xóa, nhớ lựa chọn "không" nhận hội thoại khách.
// Phụ trách: TV4 · [S5] (viết hộ bởi agent của TV1)

import type { Conversation } from "../api/types";
import { isConversationToken, isUuid } from "../api/types.ts";

// Hội thoại tạo trong lúc đã đăng nhập thuộc tài khoản; hội thoại khách (đã có serverId) tiếp tục ở trạng thái khách
// cho đến khi người dùng đồng ý chuyển vào tài khoản.
export function stampOwner(
  previous: Conversation | undefined,
  next: Conversation,
  userId: string | undefined,
): Conversation {
  const owner = previous?.ownerUserId ?? (userId && (!previous || previous.serverId === null) ? userId : undefined);
  return owner ? { ...next, ownerUserId: owner } : next;
}

// Danh tính đang xem: userId null = khách; loading = chưa biết đăng nhập hay chưa (khi đó ẩn mọi bản có chủ).
export interface Viewer {
  loading: boolean;
  userId: string | null;
}

// Chỉ hiện/khôi phục hội thoại khách (không ownerUserId) hoặc của đúng người dùng đang đăng nhập.
// Dùng cho cả danh sách hiển thị lẫn việc dọn bản sao của chủ khác khỏi localStorage.
export function viewerConversations(conversations: Conversation[], viewer: Viewer): Conversation[] {
  return conversations.filter((c) => !c.ownerUserId || (!viewer.loading && c.ownerUserId === viewer.userId));
}

// Mọi bản lưu cục bộ thuộc tài khoản: có ownerUserId trùng, hoặc có serverId nằm trong danh sách server của tài khoản.
export function accountConversationIds(
  conversations: Conversation[],
  userId: string,
  serverIds: Iterable<string> = [],
): string[] {
  const server = new Set(serverIds);
  return conversations
    .filter((c) => c.ownerUserId === userId || (c.serverId !== null && server.has(c.serverId)))
    .map((c) => c.id);
}

// Một dòng trong mục "Của tài khoản": bản cục bộ (nếu có) và/hoặc dòng từ server, gộp theo serverId.
export interface AccountItem {
  key: string;
  title: string;
  serverId: string | null;
  local?: Conversation;
  time: number;
}

export interface SidebarGroups {
  account: AccountItem[];
  browser: Conversation[];
}

// Nhóm sidebar theo chủ sở hữu, không theo nơi lưu: mở một mục (tải bản cục bộ) không làm nó đổi mục.
// - account: mọi hội thoại của tài khoản = bản cục bộ của userId (hoặc có serverId thuộc tài khoản) + dòng chỉ có trên
//   server; gộp theo serverId, mới nhất trước (bản cục bộ dùng updatedAt, dòng server dùng created_at).
// - browser: hội thoại cục bộ không có chủ (khách). Bản của chủ khác không bao giờ được liệt kê.
export function groupSidebarConversations(
  local: Conversation[],
  myConversations: { id: string; title: string; created_at: string }[],
  userId: string | null,
): SidebarGroups {
  const time = (value: string) => Date.parse(value) || 0;
  if (!userId) return { account: [], browser: local.filter((c) => !c.ownerUserId) };
  const mine = new Map(myConversations.map((c) => [c.id, c]));
  const items = new Map<string, AccountItem>();
  const browser: Conversation[] = [];
  for (const c of local) {
    const owned = c.ownerUserId === userId || (!c.ownerUserId && c.serverId !== null && mine.has(c.serverId));
    if (!owned) {
      if (!c.ownerUserId) browser.push(c);
      continue;
    }
    const key = c.serverId ?? `local:${c.id}`;
    const item: AccountItem = { key, title: c.title, serverId: c.serverId, local: c, time: time(c.updatedAt) };
    const existing = items.get(key);
    if (!existing || item.time > existing.time) items.set(key, item);
  }
  for (const r of myConversations) {
    if (!items.has(r.id)) items.set(r.id, { key: r.id, title: r.title, serverId: r.id, time: time(r.created_at) });
  }
  return { account: [...items.values()].sort((a, b) => b.time - a.time), browser };
}

// Hội thoại khách có thể chuyển vào tài khoản: có serverId + token hợp lệ và chưa thuộc ai.
export function claimableGuestConversations(conversations: Conversation[]): Conversation[] {
  return conversations.filter(
    (c) => !c.ownerUserId && c.serverId && isUuid(c.serverId) && c.serverToken && isConversationToken(c.serverToken),
  );
}

// Sau khi nhận: server đã nhận ra chủ qua cookie nên bỏ token để máy dùng chung không đọc lại được.
export function markClaimed(conversation: Conversation, userId: string): Conversation {
  const { serverToken: _token, ...rest } = conversation;
  return { ...rest, ownerUserId: userId };
}

const DECLINE_KEY = "indexbeast.claim.declined";
export function claimDeclined(storage: Pick<Storage, "getItem"> | undefined = safeSession()): boolean {
  try {
    return storage?.getItem(DECLINE_KEY) === "1";
  } catch {
    return false;
  }
}
export function rememberClaimDeclined(storage: Pick<Storage, "setItem"> | undefined = safeSession()): void {
  try {
    storage?.setItem(DECLINE_KEY, "1");
  } catch {
    // không lưu được thì chỉ nhớ trong state của trang
  }
}
function safeSession(): Storage | undefined {
  try {
    return sessionStorage;
  } catch {
    return undefined;
  }
}
