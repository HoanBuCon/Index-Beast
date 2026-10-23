// Logo + điều hướng.
// Phụ trách: TV4 · [S1] Khởi tạo web React

import { NavLink, Link } from "react-router";
import { useLanguage } from "../../lib/i18n";
export default function Header() {
  const { t, language, setLanguage } = useLanguage();
  return (
    <header className="header">
      <Link to="/" className="brand" aria-label={t("Index Beast — trang chủ")}>
        <span className="brand-mark" aria-hidden="true">
          ✦
        </span>
        <span>
          INDEX <strong>BEAST</strong>
          <small>THE LANDS BETWEEN ARCHIVE</small>
        </span>
      </Link>
      <nav aria-label={t("Điều hướng chính")}>
        <NavLink to="/" end>
          {t("Tra cứu lore")}
        </NavLink>
        <NavLink to="/about">{t("Về dự án")}</NavLink>
        <NavLink to="/admin">{t("Quản trị")}</NavLink>
      </nav>
      <div className="header-actions">
        <span className="header-note">4 HOLLOWS / BASE GAME</span>
        <div className="language-switch" role="group" aria-label={t("Ngôn ngữ giao diện")}>
          <button
            type="button"
            lang="vi"
            aria-label="Tiếng Việt"
            aria-pressed={language === "vi"}
            onClick={() => setLanguage("vi")}
          >
            VI
          </button>
          <button
            type="button"
            lang="en"
            aria-label="English"
            aria-pressed={language === "en"}
            onClick={() => setLanguage("en")}
          >
            EN
          </button>
        </div>
      </div>
    </header>
  );
}
