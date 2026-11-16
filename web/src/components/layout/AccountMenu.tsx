// Tên người dùng + Đăng xuất + Xóa tài khoản (có hộp xác nhận); dùng trong thanh bên khi đã đăng nhập.
// Phụ trách: TV4 · [S5] (viết hộ bởi agent của TV1). DELETE /me thuộc nhánh feature/s5-tv1-quyen-rieng-tu.

import { useEffect, useRef, useState } from "react";
import { deleteAccount } from "../../api/auth";
import "../../styles/account.css";

export default function AccountMenu({
  name,
  disabled = false,
  onLogout,
  onDeleted,
  initialConfirming = false,
}: {
  name: string;
  disabled?: boolean;
  onLogout: () => void;
  onDeleted: () => void;
  initialConfirming?: boolean;
}) {
  const [confirming, setConfirming] = useState(initialConfirming);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cancelRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);
  // Hộp xác nhận nhận focus ở nút an toàn (Hủy) và trả focus về nút mở khi đóng.
  useEffect(() => {
    if (confirming) cancelRef.current?.focus();
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
      {confirming && (
        <div
          className="account-confirm"
          role="alertdialog"
          aria-labelledby="account-confirm-title"
          aria-describedby="account-confirm-desc"
          onKeyDown={(event) => {
            if (event.key === "Escape" && !busy) {
              event.stopPropagation();
              close();
            }
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
        </div>
      )}
    </>
  );
}
