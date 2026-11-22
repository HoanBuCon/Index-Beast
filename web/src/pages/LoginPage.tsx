// TV4 · [S5] Discord đăng nhập thật theo docs/api/auth-tv4.md (điều hướng trình duyệt, không fetch, không lưu token).
// Google chỉ bật khi backend công bố capability tương ứng; mọi phiên đều do backend đặt cookie httpOnly.
import { Link, useSearchParams } from "react-router";
import { useEffect, useRef, useState } from "react";
import graceIcon from "../assets/ERN_Map_Icon_Site_of_Grace.png";
import loginArtwork from "../assets/patches.png";
import loginVideo from "../video/ELDEN_RING_login_cut.mp4";
// TV4: biểu tượng menu gốc hi_01; nhãn bên cạnh vẫn xác định đúng nhà cung cấp.
import googleMenuIcon from "../../item_/MENU_Tab_Net.png";
import discordMenuIcon from "../../item_/MENU_Tab_Manual.png";
import { discordLoginUrl, googleLoginUrl, safeAuthNext } from "../api/auth";
import { useAuthContext } from "../hooks/AuthContext";
import "../styles/login.css";
import "../styles/sidebar-menu.css";

export default function LoginPage() {
  const auth = useAuthContext();
  const [params] = useSearchParams();
  // Người dùng bấm "Từ chối" trên Discord được đưa về /?login=denied.
  const next = safeAuthNext(params.get("next"));
  const messages: Record<string, string> = {
    denied: "Bạn đã từ chối cấp quyền. Bạn vẫn có thể chọn “Dùng thử”.",
    expired: "Phiên đăng nhập đã hết hạn. Vui lòng thử lại.",
    error: "Chưa đăng nhập được. Vui lòng thử lại hoặc chọn Dùng thử.",
  };
  const loginStatus = params.get("login") ?? "";
  const notice = Object.hasOwn(messages, loginStatus) ? messages[loginStatus] : "";
  const [pending, setPending] = useState<string | null>(null);
  const [redirectError, setRedirectError] = useState("");
  useEffect(() => {
    const reset = () => setPending(null);
    window.addEventListener("pageshow", reset);
    return () => window.removeEventListener("pageshow", reset);
  }, []);
  function login(provider: "google" | "discord") {
    if (pending || auth.loading || !(provider === "google" ? auth.googleAuthAvailable : auth.authAvailable)) return;
    setPending(provider);
    setRedirectError("");
    try {
      window.location.assign(provider === "google" ? googleLoginUrl(next) : discordLoginUrl(next));
    } catch {
      setPending(null);
      setRedirectError("Không mở được trang đăng nhập. Vui lòng thử lại.");
    }
  }
  const [videoFailed, setVideoFailed] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  // Video minh họa không hiện thanh điều khiển; tôn trọng lựa chọn giảm chuyển động.
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePlayback = () => {
      if (preference.matches) video.current?.pause();
      else void video.current?.play().catch(() => {});
    };
    updatePlayback();
    preference.addEventListener("change", updatePlayback);
    return () => preference.removeEventListener("change", updatePlayback);
  }, []);
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
              {auth.user ? (
                <Link className="login-menu login-menu--user" to={next}>
                  <span className="login-menu__highlight" aria-hidden="true" />
                  <img
                    className="login-provider-mark"
                    src={discordMenuIcon}
                    width={32}
                    height={32}
                    alt=""
                    draggable={false}
                  />
                  <span>Tiếp tục với tư cách {auth.user.display_name}</span>
                </Link>
              ) : (
                [
                  { id: "google" as const, label: "Google", icon: googleMenuIcon, enabled: auth.googleAuthAvailable },
                  { id: "discord" as const, label: "Discord", icon: discordMenuIcon, enabled: auth.authAvailable },
                ].map((provider) => (
                  <button
                    key={provider.id}
                    className="login-menu"
                    type="button"
                    disabled={auth.loading || !!pending || !provider.enabled}
                    aria-busy={pending === provider.id}
                    aria-describedby="login-availability"
                    onClick={() => login(provider.id)}
                  >
                    <span className="login-menu__highlight" aria-hidden="true" />
                    <img
                      className="login-provider-mark"
                      src={provider.icon}
                      width={32}
                      height={32}
                      alt=""
                      draggable={false}
                    />
                    <span>
                      {pending === provider.id
                        ? `Đang chuyển tới ${provider.label}…`
                        : `Đăng nhập bằng ${provider.label}`}
                      {!auth.loading && !provider.enabled && <small className="login-soon"> (chưa khả dụng)</small>}
                    </span>
                  </button>
                ))
              )}
            </div>

            <p id="login-availability" className="sr-only">
              {auth.loading
                ? "Đang kiểm tra phương thức đăng nhập…"
                : auth.user || auth.authAvailable || auth.googleAuthAvailable
                  ? "Đăng nhập để giữ lịch sử trò chuyện giữa các thiết bị, hoặc chọn Dùng thử để làm khách."
                  : "Đăng nhập hiện chưa khả dụng. Chọn Dùng thử để trò chuyện với tư cách khách."}
            </p>
            {notice && (
              <p className="login-notice" role="status">
                {notice}
              </p>
            )}
            {redirectError && (
              <p className="login-notice" role="alert">
                {redirectError}
              </p>
            )}
            <Link className="login-guest login-menu" to="/chat">
              <span className="login-menu__highlight" aria-hidden="true" />
              <span>
                {auth.user ? "Vào trò chuyện" : "Dùng thử"} <span aria-hidden="true">↗</span>
              </span>
            </Link>
          </div>
        </section>
        <figure className="login-visual">
          {videoFailed ? (
            <img src={loginArtwork} alt="" draggable={false} />
          ) : (
            <video
              ref={video}
              src={loginVideo}
              poster={loginArtwork}
              autoPlay
              muted
              loop
              playsInline
              disablePictureInPicture
              disableRemotePlayback
              controlsList="nodownload nofullscreen noremoteplayback"
              preload="metadata"
              aria-label="Video minh họa Elden Ring"
              onError={() => setVideoFailed(true)}
            />
          )}
        </figure>
      </div>
    </main>
  );
}
