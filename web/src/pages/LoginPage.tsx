// TV4 · Giao diện trước: không gọi OAuth, không tạo tài khoản/phiên giả hoặc lưu token.
// Discord sẽ nối theo docs/api/auth-tv4.md; Google cần contract và quyết định riêng của nhóm.
import { Link } from "react-router";
import { useState } from "react";
import graceIcon from "../assets/ERN_Map_Icon_Site_of_Grace.png";
import loginArtwork from "../assets/patches.png";
// TV4: bi?u t??ng menu g?c hi_01; nh?n b?n c?nh v?n x?c ??nh ??ng nh? cung c?p.
import googleMenuIcon from "../../item_/MENU_Tab_Net.png";
import discordMenuIcon from "../../item_/MENU_Tab_Manual.png";
import "../styles/login.css";
import "../styles/sidebar-menu.css";

export default function LoginPage() {
  const [notice, setNotice] = useState("");
  const previewLogin = (provider: string) =>
    setNotice(`Đăng nhập bằng ${provider} chưa sẵn sàng. Bạn có thể chọn “Vào website” để tiếp tục.`);
  return (
    <main id="main" className="login-page" aria-label="Đăng nhập INDEX BEAST">
      <header className="login-brand">
        <img src={graceIcon} width={32} height={32} alt="" draggable={false} />
        <span>INDEX BEAST</span>
      </header>
      <div className="login-layout">
        <section className="login-content" aria-labelledby="login-heading">
          <h1 id="login-heading">LANG THANG ELDEN RING</h1>
          <div className="login-card">
            <div
              className="login-providers"
              role="group"
              aria-label="Phương thức đăng nhập"
              aria-describedby="login-availability"
            >
              <button
                className="login-menu"
                type="button"
                onClick={() => previewLogin("Google")}
                aria-describedby="login-availability"
              >
                <span className="login-menu__highlight" aria-hidden="true" />
                <img
                  className="login-provider-mark"
                  src={googleMenuIcon}
                  width={32}
                  height={32}
                  alt=""
                  draggable={false}
                />
                <span>Đăng nhập bằng Google</span>
              </button>
              <button
                className="login-menu"
                type="button"
                onClick={() => previewLogin("Discord")}
                aria-describedby="login-availability"
              >
                <span className="login-menu__highlight" aria-hidden="true" />
                <img
                  className="login-provider-mark"
                  src={discordMenuIcon}
                  width={32}
                  height={32}
                  alt=""
                  draggable={false}
                />
                <span>Đăng nhập bằng Discord</span>
              </button>
            </div>

            <p id="login-availability" className="sr-only">
              Đăng nhập hiện chưa khả dụng. Chọn Vào website để trò chuyện với tư cách khách.
            </p>
            {notice && (
              <p className="login-notice" role="status">
                {notice}
              </p>
            )}
            <Link className="login-guest login-menu" to="/chat">
              <span className="login-menu__highlight" aria-hidden="true" />
              <span>
                Vào website <span aria-hidden="true">↗</span>
              </span>
            </Link>
          </div>
        </section>
        <figure className="login-visual">
          <img src={loginArtwork} alt="" draggable={false} />
        </figure>
      </div>
    </main>
  );
}
