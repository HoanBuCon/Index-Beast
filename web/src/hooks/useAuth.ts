// Trạng thái đăng nhập + capabilities: tải một lần ở App rồi chia sẻ qua AuthContext (không gọi lặp ở từng trang).
// Phụ trách: TV4 · [S5] Web đăng nhập Discord (viết hộ bởi agent của TV1)

import { useCallback, useEffect, useState } from "react";
import { getCapabilities, getMe, listMyConversations, logoutVerified } from "../api/auth";
import type { AuthUser, MyConversation } from "../api/auth";

export interface AuthState {
  loading: boolean;
  authAvailable: boolean;
  searchAvailable: boolean;
  traceAvailable: boolean;
  user: AuthUser | null;
  myConversations: MyConversation[];
  // true khi phiên thật sự đã hết; false thì vẫn giữ người dùng và đặt logoutError.
  logout: () => Promise<boolean>;
  logoutError: string;
  // Sau khi xóa tài khoản: coi như khách, không gọi /auth/logout (phiên đã bị xóa phía server).
  clearUser: () => void;
}

export function useAuth(): AuthState {
  const [loading, setLoading] = useState(true);
  const [caps, setCaps] = useState({ authAvailable: false, searchAvailable: false, traceAvailable: false });
  const [user, setUser] = useState<AuthUser | null>(null);
  const [myConversations, setMyConversations] = useState<MyConversation[]>([]);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const [capabilities, me] = await Promise.all([getCapabilities(controller.signal), getMe(controller.signal)]);
        setCaps(capabilities);
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
    setLogoutError("");
    // Chỉ về chế độ khách khi server xác nhận phiên đã hết; lỗi thì giữ người dùng để họ thử lại.
    if (!(await logoutVerified())) {
      setLogoutError("Chưa đăng xuất được. Vui lòng thử lại.");
      return false;
    }
    setUser(null);
    setMyConversations([]);
    return true;
  }, []);

  const clearUser = useCallback(() => {
    setLogoutError("");
    setUser(null);
    setMyConversations([]);
  }, []);

  return { loading, ...caps, user, myConversations, logout, logoutError, clearUser };
}
