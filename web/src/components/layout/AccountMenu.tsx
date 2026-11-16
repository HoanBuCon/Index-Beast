// Tên người dùng + Đăng xuất + Xóa tài khoản (hộp xác nhận <dialog> modal); dùng trong thanh bên khi đã đăng nhập.
// Phụ trách: TV4 · [S5] (viết hộ bởi agent của TV1). DELETE /me thuộc nhánh feature/s5-tv1-quyen-rieng-tu.

import { useEffect, useRef, useState } from "react";
import { deleteAccount } from "../../api/auth";
import "../../styles/account.css";

export default function AccountMenu({
  name,
  disabled = false,
  logoutError = "",
  onLogout,
  onDeleted,
  initialConfirming = false,
}: {
  name: string;
  disabled?: boolean;
  logoutError?: string;
  onLogout: () => void;
  onDeleted: () => void;
  initialConfirming?: boolean;
}) {
  const [confirming, setConfirming] = useState(initialConfirming);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);
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
    <>
      <span className="sidebar-account__name" title={name}>
        {name}
      </span>
      <button type="button" disabled={disabled} onClick={onLogout}>
        Đăng xuất
      </button>
      <button type="button" ref={openerRef} disabled={disabled} onClick={() => setConfirming(true)}>
        Xóa tài khoản
      </button>
      {logoutError && (
        <p className="sidebar-account__error" role="alert">
          {logoutError}
        </p>
      )}
      {confirming && (
        <dialog
          ref={dialog}
          className="account-confirm"
          role="alertdialog"
          aria-labelledby="account-confirm-title"
          aria-describedby="account-confirm-desc"
          onCancel={(event) => {
            // Esc: đóng hộp, trừ khi đang xóa dở
            event.preventDefault();
            if (!busy) close();
          }}
        >
          <h2 id="account-confirm-title">Xóa tài khoản?</h2>
          <p id="account-confirm-desc">
            Toàn bộ hội thoại của bạn sẽ bị xóa vĩnh viễn và không thể khôi phục. Bạn sẽ quay về chế độ khách.
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
    </>
  );
}
