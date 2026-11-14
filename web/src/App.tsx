// Layout + định tuyến: / (chat), /about, /admin.
// TV4: / và /login là màn vào riêng; hội thoại chuyển sang /chat.
// Phụ trách: TV4 · [S1] Khởi tạo web React

import { Route, Routes, Link, useLocation } from "react-router";
import ChatPage from "./pages/ChatPage";
import AboutPage from "./pages/AboutPage";
import AdminPage from "./pages/AdminPage";
import SharedAnswerPage from "./pages/SharedAnswerPage";
import LoginPage from "./pages/LoginPage";
import { lazy, Suspense } from "react";
// TV4: chỉ mở fixture khi DEV và truy cập URL rõ ràng; không đóng gói fixture vào production.
const AnswerMediaPreviewPage = import.meta.env.DEV ? lazy(() => import("./pages/AnswerMediaPreviewPage")) : null;
export default function App() {
  const { pathname } = useLocation();
  // Màn vào không nằm trong ChatPage: chưa hiện sidebar/composer trước khi chọn vào web.
  if (pathname === "/" || pathname === "/login") return <LoginPage />;
  return (
    <>
      <a className="skip-link" href="#main">
        {"Đến nội dung chính"}
      </a>
      <ChatPage>
        <Routes>
          <Route path="/chat" element={null} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/answer" element={<SharedAnswerPage />} />
          {AnswerMediaPreviewPage && (
            <Route
              path="/preview/answer-images"
              element={
                <Suspense
                  fallback={
                    <main id="main">
                      <p role="status">Đang mở trang thử…</p>
                    </main>
                  }
                >
                  <AnswerMediaPreviewPage />
                </Suspense>
              }
            />
          )}
          <Route
            path="*"
            element={
              <main id="main" className="document">
                <h1>{"Trang này chưa được tìm thấy."}</h1>
                <Link to="/chat">{"Trở về bàn tra cứu"}</Link>
              </main>
            }
          />
        </Routes>
      </ChatPage>
    </>
  );
}
