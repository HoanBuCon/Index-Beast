// Layout + định tuyến: / (chat), /about, /admin.
// Phụ trách: TV4 · [S1] Khởi tạo web React

import { Route, Routes, Link } from "react-router";
import Header from "./components/layout/Header";
import ChatPage from "./pages/ChatPage";
import AboutPage from "./pages/AboutPage";
import AdminPage from "./pages/AdminPage";
import { useLanguage } from "./lib/i18n";
export default function App() {
  const { t } = useLanguage();
  return (
    <>
      <a className="skip-link" href="#main">
        {t("Đến nội dung chính")}
      </a>
      <Header />
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route
          path="*"
          element={
            <main id="main" className="document">
              <h1>{t("Trang này chưa được tìm thấy.")}</h1>
              <Link to="/">{t("Trở về bàn tra cứu")}</Link>
            </main>
          }
        />
      </Routes>
    </>
  );
}
