// Layout + định tuyến: / (chat), /about, /admin.
// Phụ trách: TV4 · [S1] Khởi tạo web React

import { Route, Routes, Link } from "react-router";
import ChatPage from "./pages/ChatPage";
import AboutPage from "./pages/AboutPage";
import AdminPage from "./pages/AdminPage";
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
