# TV1 Sprint 4 · Báo cáo bàn giao: feedback, eval, đăng nhập

Nhánh `feature/s4-tv1-feedback-eval-auth` từ `origin/develop` tại `14bda7f`. Chưa merge. **Không tạo tag, release hay merge vào `main`**: release v2 do TV1 quyết định.

Đối chiếu Trello **không** thực hiện (theo yêu cầu). Phân tích thẻ TV1 và đề xuất điều chỉnh nằm ở [đề xuất Sprint 4](../proposals/2026-11-13_s4-tv1-de-xuat-dieu-chinh-ke-hoach.md).

## Đã làm

| Hạng mục | Kết quả |
|---|---|
| 4.3 Feedback | `POST /feedback` lưu vào PostgreSQL (mỗi câu trả lời giữ một đánh giá, đánh giá sau ghi đè), kiểm quyền sở hữu hội thoại như `/chat`. |
| 4.2 Eval | Bảng `eval_runs` có `add_eval_run` và script `backend/scripts/eval_runs.py`; `/admin/stats` nhận biết nhãn lượt chạy (`_run_label`). |
| Data runner | `backend/scripts/data_pipeline.py` nhận bundle S3 và S4 (`CLEAN_VERSIONS`, `CHUNK_VERSIONS`, `--gameplay`, `--structured-tables`, `--wiki-quality`). |
| 4.1 Auth service | Đăng nhập Discord OAuth2 + PKCE, phiên cookie `httpOnly` lưu băm trong PostgreSQL, hội thoại gắn người dùng, nhận lại hội thoại khách, quản trị viên theo `AUTH_ADMIN_DISCORD_IDS`, giới hạn tần suất đăng nhập, kiểm `Origin`. Migration `0004`. |
| Test tích hợp pipeline (thẻ Trello cùng tên) | `tests/integration/test_pipeline_e2e.py`: Qdrant và PostgreSQL thật, LLM và encoder giả (không gọi API ngoài); kiểm nguồn đúng lên đầu, lưu hội thoại, hỏi tiếp, chặn người lạ. Có sẵn bước integration trong CI; thêm bước coverage module `app/rag` với ngưỡng 60% (hiện 95%, `coverage` ghim trong requirements-dev/constraints). |
| Tài liệu | SRS 0.8.0 (FR-AUTH-01..09), TechStack v1.7, ADR-004 (ghi chú), ADR-005 (đề xuất), [hợp đồng cho TV4](../api/auth-tv4.md), `openapi.json` đã sinh lại. |

## Tích hợp với thành viên khác

- **TV4 (web/bot):** đọc [`auth-tv4.md`](../api/auth-tv4.md). Cần làm giao diện đăng nhập (FR-AUTH-09) và, nếu muốn, khôi phục nút 👍/👎 gọi `/feedback`. Bot không đổi: vẫn dùng khách.
- **TV3 (AI/RAG):** `ChatRequest.user_id` do server gắn, không nằm trong JSON/OpenAPI nên client không giả mạo được; pipeline và agent không đổi.
- **TV2 (dữ liệu):** runner đã nhận bundle `s4-wiki`; không đổi định dạng dữ liệu.

## Việc chủ dự án cần làm trước khi chạy

1. `make migrate` (migration `0004`). Chạy API với `CHAT_PERSISTENCE=postgres` trên DB chưa migrate sẽ lỗi.
2. Đặt `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `AUTH_SECRET` (từ 32 ký tự), tùy chọn `AUTH_ADMIN_DISCORD_IDS`; thêm Redirect URL vào Discord Developer Portal (xem `auth-tv4.md`).
3. Quyết định các mục còn mở trong ADR-005: bắt buộc đăng nhập ở v2 hay không, thêm provider khác, có giữ chế độ khách trên production không.

## Kiểm chứng

- `test_health_live` thất bại trên máy này vì `.env` đặt `CHAT_MODE=rag` + `CHAT_PERSISTENCE=postgres` mà thiếu `CHAT_AGENT_ENABLED=true`; không liên quan thay đổi mã. CI dùng `.env` mặc định.
- Unit test backend và ruff sạch; integration test (PostgreSQL thật) cho `eval_runs`, `users`/`auth_sessions`, quyền sở hữu và nhận lại hội thoại, khớp schema migration.
- **Chưa kiểm:** đăng nhập với Discord thật (cần client secret và người bấm; phần gọi Discord kiểm bằng giả lập), giao diện web, HTTPS cho OAuth trên cloud (Sprint 5 cần tên miền).

## Chưa làm / việc tiếp theo

- Gói release v2 (CHANGELOG, hướng dẫn nâng cấp từ v1: migration 0002–0004, biến môi trường mới, checklist). Chỉ chuẩn bị tài liệu; việc tag/release/merge `main` do TV1.
- Xóa tài khoản và dữ liệu (FR-AUTH-08, Sprint 5).
- File `scripts/count_loc.py` chưa theo dõi không thuộc phần việc này.
