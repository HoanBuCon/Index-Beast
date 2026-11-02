// Layout + định tuyến: / (chat), /about, /admin.
// Phụ trách: TV4 · [S1] Khởi tạo web React

import { Route, Routes, Link } from "react-router";
import ChatPage from "./pages/ChatPage";
import AboutPage from "./pages/AboutPage";
import AdminPage from "./pages/AdminPage";
import { lazy, Suspense } from "react";
// TV4: chỉ mở fixture khi DEV và truy cập URL rõ ràng; không đóng gói fixture vào production.
const AnswerMediaPreviewPage = import.meta.env.DEV ? lazy(() => import("./pages/AnswerMediaPreviewPage")) : null;
export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        {"Đến nội dung chính"}
      </a>
      <ChatPage>
        <Routes>
          <Route path="/" element={null} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/admin" element={<AdminPage />} />
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
                <Link to="/">{"Trở về bàn tra cứu"}</Link>
              </main>
            }
          />
        </Routes>
      </ChatPage>
    </>
  );
}
