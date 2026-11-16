# TV1 Sprint 5 · Quyền riêng tư và xóa tài khoản

Nhánh `feature/s5-tv1-quyen-rieng-tu`, tách từ `origin/develop`. Làm FR-AUTH-08 (xóa tài khoản), NFR-PRIV-01 (xóa log sau 90 ngày), văn bản chính sách và test phân quyền.

## Phạm vi

| Yêu cầu | Làm | File |
|---|---|---|
| FR-AUTH-08 | `DELETE /api/v1/me`: cần cookie phiên và `Origin` hợp lệ (như các lệnh ghi cookie khác), xóa người dùng, mọi phiên, mọi hội thoại gắn `user_id` cùng tin nhắn, feedback, ký ức, runtime (khóa ngoại `ON DELETE CASCADE`) và điểm Qdrant; xóa cookie; trả 204 | `backend/app/api/routes/auth.py`, `backend/app/services/privacy.py` |
| NFR-PRIV-01 | `python -m scripts.retention --days 90 [--dry-run] [--no-vectors]`: xóa hội thoại có hoạt động cuối quá N ngày và phiên hết hạn, theo lô 500, chỉ in số đếm | `backend/scripts/retention.py`, `backend/app/services/privacy.py` |
| Chính sách | Văn bản cho người dùng (TV4 hiển thị ở trang Giới thiệu) và hướng dẫn vận hành kèm cron mẫu | `docs/privacy.md` |
| Audit | Test phân quyền cho `/admin/stats` và `DELETE /me` | `backend/tests/unit/test_auth.py` |

Cập nhật: `docs/api/auth-tv4.md` (thêm `DELETE /me`), `docs/api/openapi.json` (xuất lại), SRS (FR-AUTH-08, NFR-PRIV-01 sang In Progress).

## Quyết định

- **Qdrant xóa trước, PostgreSQL sau.** Qdrant lỗi thì trả 503 và chưa xóa gì; người dùng thử lại được. Xóa ngược lại sẽ để vector mồ côi không còn cách tìm ra. Điểm Qdrant lọc theo payload `conversation_id` (đã có chỉ mục keyword) nên không cần biết id từng ký ức.
- **Xóa theo lô** (`BATCH_SIZE = 500`, hằng số trong module, không thêm vào `core/config.py` vì file đó bị khóa). Mỗi lô một transaction ngắn.
- **Idempotent ở tầng dịch vụ.** `delete_account` với người dùng đã mất trả số đếm 0, không lỗi. Ở tầng HTTP, gọi lại sau khi xóa nhận **401** vì cookie không còn hiệu lực (đúng hành vi của mọi route cần đăng nhập). Nếu muốn 204 cho cả lần gọi lại thì phải đổi sang `optional_user`, tôi không làm vì mất phân biệt "chưa đăng nhập".
- **"Trace lưu riêng"**: không có bảng trace riêng; trace RAG là cột `messages.rag_trace` nên đi theo hội thoại. Không cần bước dọn thêm.
- **Hoạt động cuối** của hội thoại = tin nhắn mới nhất, hoặc `created_at` nếu chưa có tin. Hội thoại cũ nhưng vừa có tin mới được giữ (có test).
- **Tên collection ký ức** đọc từ `settings.chat_memory_collection` (đã có sẵn); script không thêm cấu hình mới. Hằng số 90 ngày là mặc định của cờ `--days`.
- **Cần hợp nhất với PR #110**: #110 thêm `MemoryVectors.delete_conversations`. `purge_memory_vectors` trong `privacy.py` làm cùng việc bằng client Qdrant trực tiếp (không sửa `semantic_memory.py` để khỏi xung đột). Khi merge #110, nên để `purge_memory_vectors` gọi phương thức của #110 và bỏ bản trùng.
- Admin: `/admin/*` cho phép admin đăng nhập vào thẳng, còn lại cần `X-Admin-Token`; người dùng thường có phiên nhưng không có token nhận 401, và 404 khi chưa đặt `ADMIN_TOKEN`. Hành vi giữ nguyên, nay có test khóa lại.

## Kiểm tra

Chạy với venv của checkout chính (worktree không có venv riêng).

| Lệnh | Kết quả |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 277 files already formatted |
| `python -m pytest tests/unit -q` | 1154 passed, 20 skipped |
| `python -m pytest tests/integration/test_privacy.py -m integration` (PostgreSQL 18 thật trong Docker, DB tạm) | 5 passed |
| `python -m scripts.export_openapi` | ghi lại `docs/api/openapi.json` (+ route `DELETE /me`) |

Test mới: 5 test route trong `tests/unit/test_auth.py` (401 khách và cookie giả, 403 Origin lạ, id lấy từ phiên không từ client, cookie bị xóa, 503 không xóa cookie, admin/stats 401/404 với phiên thường), 6 test trong `tests/unit/test_privacy.py` (bộ lọc Qdrant theo lô, no-op, lỗi chung 503 không lộ chi tiết, in số đếm, cutoff, `--days 0`), 5 test PostgreSQL thật (xóa đúng người và chỉ dữ liệu của họ, idempotent, Qdrant lỗi thì không mất gì và thử lại được, retention theo mốc kể cả hội thoại rỗng và hội thoại cũ vừa có tin mới, lô nhỏ, phiên hết hạn).

## Chưa kiểm chứng

- Chưa chạy `scripts.retention` với Qdrant thật (test dùng bản giả ghi lại lệnh `delete`); cú pháp `FilterSelector` + `MatchAny` theo qdrant-client đã cài nhưng chưa thử trên collection thật.
- Chưa đặt cron trên máy chủ; chưa có nút xóa tài khoản trên web (TV4) và `/clear` của bot chưa tồn tại.
- Chưa tính bản sao lưu PostgreSQL (thuộc PR #109): dữ liệu đã xóa vẫn còn trong bản sao lưu cũ.

## Bàn giao

- TV4: hiển thị `docs/privacy.md` ở trang Giới thiệu và thêm nút "Xóa tài khoản" (hỏi xác nhận, gọi `DELETE /api/v1/me`, sau 204 về trang chủ).
- TV1: merge #110 thì hợp nhất `purge_memory_vectors` như trên; cân nhắc đưa `--days` vào cấu hình khi `core/config.py` mở khóa.
