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
