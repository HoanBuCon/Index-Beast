// Chia sẻ trạng thái đăng nhập cho LoginPage, ChatPage và AdminPage (một lần tải, không gọi lặp /auth/me).
// Giá trị mặc định là "khách chưa biết capabilities" để trang dùng độc lập (và test) không cần Provider.
import { createContext, useContext } from "react";
import type { AuthState } from "./useAuth";

export const guestAuth: AuthState = {
  loading: false,
  authAvailable: false,
  searchAvailable: false,
  traceAvailable: false,
  user: null,
  myConversations: [],
  logout: async () => false,
  logoutError: "",
  clearUser: () => {},
};

export const AuthContext = createContext<AuthState>(guestAuth);
export const useAuthContext = () => useContext(AuthContext);
