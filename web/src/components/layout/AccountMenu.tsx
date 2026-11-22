// Tên người dùng + Đăng xuất + Xóa tài khoản (hộp xác nhận <dialog> modal); dùng trong thanh bên khi đã đăng nhập.
// Phụ trách: TV4 · [S5] (viết hộ bởi agent của TV1). DELETE /me thuộc nhánh feature/s5-tv1-quyen-rieng-tu.

import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link, useLocation } from "react-router";
import { deleteAccount, loginPageUrl } from "../../api/auth";
// TV4: icon menu hi_01 chép nguyên bản vào item_ (không tham chiếu thư mục nguồn bên ngoài dự án).
// Chỉ dùng ảnh không có khung viền (bộ MENU_Tab_*), không dùng MENU_FL_* có khung đá.
import memberAvatar from "../../../item_/MENU_Tab_Armor.png";
import guestAvatar from "../../../item_/MENU_Tab_10.png";
import moreIcon from "../../../item_/MENU_Tab_Option.png";
import adminIcon from "../../../item_/MENU_Tab_03.png";
import loginIcon from "../../../item_/MENU_Tab_12.png";
import logoutIcon from "../../../item_/MENU_Tab_Exit.png";
import deleteIcon from "../../../item_/KG_Key_Delete.png";
import "../../styles/account.css";

function MenuIcon({ src, wide = false }: { src: string; wide?: boolean }) {
  return (
    <span className={`account-menu-icon${wide ? " account-menu-icon--key" : ""}`} aria-hidden="true">
      <img src={src} alt="" draggable={false} />
    </span>
  );
}

export default function AccountMenu({
  name,
  canAdmin = false,
  onNavigate,
  disabled = false,
  logoutError = "",
  onLogout,
  onDeleted,
  initialConfirming = false,
}: {
  name?: string;
  canAdmin?: boolean;
  onNavigate?: () => void;
  disabled?: boolean;
  logoutError?: string;
  onLogout: () => void | Promise<unknown>;
  onDeleted: () => void;
  initialConfirming?: boolean;
}) {
  const { pathname } = useLocation();
  const signedIn = name !== undefined;
  const displayName = signedIn ? name?.trim() || "Người dùng" : "Khách";
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 8, bottom: 70 });
  const root = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [confirming, setConfirming] = useState(initialConfirming);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);
  function closeMenu(restoreFocus = false) {
    setOpen(false);
    if (restoreFocus) openerRef.current?.focus();
  }
  useEffect(() => {
    setOpen(false);
  }, [pathname, name, disabled]);
  useEffect(() => {
    if (!open) return;
    const place = () => {
      const rect = openerRef.current?.getBoundingClientRect();
      if (rect)
        setPosition({ left: Math.max(8, Math.min(rect.left, innerWidth - 268)), bottom: innerHeight - rect.top + 8 });
    };
    place();
    const observer = new ResizeObserver(place);
    if (root.current) observer.observe(root.current);
    menu.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    };
    const focusOutside = (event: FocusEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("focusin", focusOutside);
    window.addEventListener("resize", place);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("focusin", focusOutside);
      window.removeEventListener("resize", place);
      observer.disconnect();
    };
  }, [open]);
  function menuKeys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeMenu(true);
      return;
    }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const items = Array.from(menu.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)') ?? []);
    const index = items.indexOf(document.activeElement as HTMLElement);
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? items.length - 1
          : (index + (event.key === "ArrowUp" ? -1 : 1) + items.length) % items.length;
    items[next]?.focus();
  }
  // <dialog>.showModal(): trình duyệt tự khóa focus trong hộp và đóng bằng Esc; vẫn đặt focus đầu vào nút an toàn "Hủy".
  useEffect(() => {
    const element = dialog.current;
    if (!confirming || !element || element.open) return;
    element.showModal?.();
    cancelRef.current?.focus();
  }, [confirming]);
  function close() {
    setConfirming(false);
    setError("");
    requestAnimationFrame(() => openerRef.current?.focus());
  }
  async function confirm() {
    setBusy(true);
    setError("");
    if (await deleteAccount()) {
      setBusy(false);
      onDeleted();
      return;
    }
    setBusy(false);
    setError("Chưa xóa được tài khoản. Vui lòng thử lại.");
  }
  return (
    <div className="sidebar-account" ref={root}>
      <button
        className="account-trigger"
        type="button"
        ref={openerRef}
        disabled={disabled || busy}
        aria-label={`Menu tài khoản: ${displayName}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="account-menu"
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span className="account-avatar" aria-hidden="true">
          <img src={signedIn ? memberAvatar : guestAvatar} alt="" draggable={false} />
        </span>
        <span className="account-trigger__text">
          <span className="sidebar-account__name">{displayName}</span>
          <small>{signedIn ? "Tài khoản của bạn" : "Chưa đăng nhập"}</small>
        </span>
        <span className="account-trigger__more" aria-hidden="true">
          <img src={moreIcon} alt="" draggable={false} />
        </span>
      </button>
      <div
        id="account-menu"
        ref={menu}
        className="account-popover"
        role="menu"
        aria-label="Tài khoản"
        hidden={!open}
        style={position}
        onKeyDown={menuKeys}
      >
        <p className="account-popover__heading">{signedIn ? displayName : "Bạn đang dùng thử"}</p>
        {canAdmin && (
          <Link
            role="menuitem"
            to="/admin"
            onClick={() => {
              closeMenu();
              onNavigate?.();
            }}
          >
            <MenuIcon src={adminIcon} />
            Quản trị
          </Link>
        )}
        <Link
          role="menuitem"
          to={loginPageUrl(pathname)}
          onClick={() => {
            closeMenu();
            onNavigate?.();
          }}
        >
          <MenuIcon src={loginIcon} />
          {signedIn ? "Trang đăng nhập" : "Đăng nhập"}
        </Link>
        {signedIn && (
          <>
            <div className="account-popover__separator" role="separator" />
            <button
              role="menuitem"
              type="button"
              disabled={busy}
              onClick={async () => {
                if (busy) return;
                setBusy(true);
                try {
                  await onLogout();
                } finally {
                  setBusy(false);
                }
              }}
            >
              <MenuIcon src={logoutIcon} />
              {busy ? "Đang đăng xuất…" : "Đăng xuất"}
            </button>
            <button
              role="menuitem"
              className="account-danger"
              type="button"
              disabled={busy}
              onClick={() => {
                closeMenu();
                setConfirming(true);
              }}
            >
              <MenuIcon src={deleteIcon} wide />
              Xóa tài khoản
            </button>
          </>
        )}
        {logoutError && (
          <p className="sidebar-account__error" role="alert">
            {logoutError}
          </p>
        )}
      </div>
      {confirming && (
        <dialog
          ref={dialog}
          className="account-confirm"
          role="alertdialog"
          aria-labelledby="account-confirm-title"
          aria-describedby="account-confirm-desc"
          onKeyDown={(event) => {
            if (event.key !== "Tab") return;
            const buttons = Array.from(
              event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"),
            );
            const first = buttons[0];
            const last = buttons.at(-1);
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }}
          onCancel={(event) => {
            // Esc: đóng hộp, trừ khi đang xóa dở
            event.preventDefault();
            if (!busy) close();
          }}
        >
          <h2 id="account-confirm-title">Xóa tài khoản?</h2>
          <p id="account-confirm-desc">
            Toàn bộ hội thoại của bạn sẽ bị xóa vĩnh viễn và không thể khôi phục. Bạn sẽ quay về trang đăng nhập.
          </p>
          {error && <p role="alert">{error}</p>}
          <div className="account-confirm__actions">
            <button type="button" ref={cancelRef} disabled={busy} onClick={close}>
              Hủy
            </button>
            <button type="button" className="danger" disabled={busy} onClick={() => void confirm()}>
              {busy ? "Đang xóa…" : "Xóa vĩnh viễn"}
            </button>
          </div>
        </dialog>
      )}
    </div>
  );
}
