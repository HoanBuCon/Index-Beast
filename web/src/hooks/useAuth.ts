// Trạng thái đăng nhập: capabilities + /auth/me, đăng xuất, danh sách hội thoại của tài khoản.
// Phụ trách: TV4 · [S5] Web đăng nhập Discord (viết hộ bởi agent của TV1)

import { useCallback, useEffect, useState } from "react";
import { getCapabilities, getMe, listMyConversations, logout as apiLogout } from "../api/auth";
import type { AuthUser, MyConversation } from "../api/auth";

export interface AuthState {
  loading: boolean;
  authAvailable: boolean;
  user: AuthUser | null;
  myConversations: MyConversation[];
  logout: () => Promise<void>;
  // Sau khi xóa tài khoản: coi như khách, không gọi /auth/logout (phiên đã bị xóa phía server).
  clearUser: () => void;
}

export function useAuth(): AuthState {
  const [loading, setLoading] = useState(true);
  const [authAvailable, setAuthAvailable] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [myConversations, setMyConversations] = useState<MyConversation[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const [caps, me] = await Promise.all([getCapabilities(controller.signal), getMe(controller.signal)]);
        setAuthAvailable(caps.authAvailable);
        setUser(me);
        setMyConversations(me ? await listMyConversations(controller.signal) : []);
        setLoading(false);
      } catch {
        // abort khi unmount: không cập nhật state nữa
      }
    })();
    return () => controller.abort();
  }, []);

  const logout = useCallback(async () => {
    // Dù server lỗi vẫn coi như khách ở phía web; cookie hết hạn sẽ tự dọn.
    await apiLogout();
    setUser(null);
    setMyConversations([]);
  }, []);

  const clearUser = useCallback(() => {
    setUser(null);
    setMyConversations([]);
  }, []);

  return { loading, authAvailable, user, myConversations, logout, clearUser };
}
