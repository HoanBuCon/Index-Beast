// Hỏi trước khi chuyển hội thoại khách trong trình duyệt này vào tài khoản; không bao giờ nhận âm thầm.
// Phụ trách: TV4 · [S5] (viết hộ bởi agent của TV1)
import "../../styles/account.css";

export default function ClaimPrompt({
  count,
  busy = false,
  onAccept,
  onDecline,
}: {
  count: number;
  busy?: boolean;
  onAccept: () => void;
  onDecline: () => void;
}) {
  return (
    <div className="claim-prompt" role="group" aria-labelledby="claim-prompt-text">
      <p id="claim-prompt-text">{`Chuyển ${count} hội thoại khách trong trình duyệt này vào tài khoản?`}</p>
      <div className="account-confirm__actions">
        <button type="button" disabled={busy} onClick={onAccept}>
          Đồng ý
        </button>
        <button type="button" disabled={busy} onClick={onDecline}>
          Không
        </button>
      </div>
    </div>
  );
}
