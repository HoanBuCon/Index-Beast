# TV1 · Đăng nhập bằng Google (23/11/2026)

Sprint 5, ADR-005. Nhánh `feat/s5-tv1-google-auth-trace-sidebar`. Runbook: [`docs/production.md`](../production.md) mục 3.3b.

## Bối cảnh

Web đã có hợp đồng Google (`googleLoginUrl`, `google_auth_available` trong `GET /chat/capabilities`, hàng Google bị khóa trên `LoginPage`) nhưng backend chưa có gì. Bản này làm phần backend theo đúng cách của Discord và bật hàng Google khi capability bật.

## Thay đổi

1. **Cấu hình** (`core/config.py`): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (SecretStr), `GOOGLE_REDIRECT_URI` (trống: `<WEB_URL>/api/v1/auth/google/callback`). `google_auth_enabled` = client id và secret thật (không trống, không `change-me`) và `AUTH_SECRET` từ 32 ký tự. `login_enabled = auth_enabled or google_auth_enabled` dùng cho đọc cookie phiên (`optional_user`), băm admin và kiểm cookie Secure ở prod. `auth_enabled` vẫn nghĩa là "Discord bật". `ensure_safe_for_environment` quét mọi trường nên tự bắt `change-me` ở các biến Google.
2. **Adapter** `app/adapters/google_oauth.py` (`GoogleOAuth`): URL `accounts.google.com/o/oauth2/v2/auth` (`response_type=code`, scope `openid profile`, PKCE S256, `state`, `prompt=select_account`); đổi mã ở `oauth2.googleapis.com/token`; đọc `openidconnect.googleapis.com/v1/userinfo` bằng access token, lấy `sub` (chuỗi, tối đa 255 ký tự) và `name` (tối đa 80). Không xin và không đọc email. Timeout 10 s, không theo redirect, lỗi mạng hoặc dữ liệu lạ là `UpstreamError` chung (502), không ghi token hay phản hồi vào log.
3. **Routes** `GET /auth/google/login` và `/auth/google/callback`: cùng bảo vệ với Discord (state + verifier trong Redis `OAUTH_STATE_TTL_SECONDS`, state gắn trình duyệt qua `ib_oauth`, giới hạn đăng nhập theo IP, `next` chỉ đường dẫn tương đối, cookie `httpOnly` `SameSite=Lax`, 404 khi chưa cấu hình). Phần dùng chung được tách thành `_start_login` và `_finish_login` trong `routes/auth.py`; hành vi Discord giữ nguyên (test Discord không đổi).
4. **Người dùng**: `provider_hash(settings, raw_id, provider="discord")`; Discord vẫn là `HMAC("discord:<id>")` byte-identical (có test). Google là `HMAC("google:<sub>")`. `upsert_user(..., provider="discord")` ghi `provider`. Chỉ lưu băm của `sub` và tên hiển thị; không email.
5. **Migration 0006** (`0006_google_provider.py`): tạo lại `ck_users_provider` thành `provider IN ('discord', 'google')`. Downgrade xóa người dùng Google (phiên xóa theo, hội thoại về `user_id` NULL) rồi trả ràng buộc cũ. Model `User` cập nhật theo.
6. **Capabilities**: thêm `google_auth_available`; `auth_available` giữ nghĩa Discord.
7. **Web**: hàng Google bật khi `googleAuthAvailable`; khi tắt giữ khóa và hiện "(sắp có)" (Discord tắt vẫn "(chưa khả dụng)"). Chỉ đổi `LoginPage.tsx`, `login.css` (chú thích) và test.
8. **Cấu hình/tài liệu**: `.env.example`, `.env.prod.example` (Google để trống, tùy chọn), `docker-compose.yml`, `docker-compose.prod.yml` (suy `GOOGLE_REDIRECT_URI` từ `DOMAIN`), `production.md` 3.3b + dòng xử lý sự cố, `privacy.md`, `02_SRS.md` (FR-AUTH-09 sửa, thêm FR-AUTH-10).

## Quyết định

- State bắt đầu ở Google ghi thêm `provider: "google"`; callback của mỗi nhà cung cấp từ chối state của nhà kia (cùng cookie `ib_oauth`, nếu không một state có thể bị đem sang callback khác). State Discord không có khóa này nên mặc định là `discord`, định dạng cũ không đổi.
- `provider_hash` nhận `provider` là tham số cuối có mặc định (không phải thứ tự `(settings, provider, raw_id)`) để mọi chỗ gọi và test Discord hiện có chạy không đổi.
- Người dùng Google không bao giờ là admin: admin chỉ theo `AUTH_ADMIN_DISCORD_IDS` (so băm `discord:<id>`); Google `sub` không thể trùng vì khác tiền tố.
- Hai tài khoản Discord và Google của cùng một người là hai người dùng riêng (không gộp), vì không lấy email để đối chiếu.
- `.env.prod.example` để Google trống thay vì `change-me`: `deploy.sh` từ chối `change-me` còn sót và Google là tùy chọn. Đã điền thì phải là giá trị thật, prod từ chối khởi động nếu còn `change-me`.

## Kiểm tra

| Lệnh | Kết quả |
|---|---|
| `ruff check .` / `ruff format --check .` (backend) | All checks passed / 298 files already formatted |
| `pytest tests/unit -q -p no:cacheprovider` | 1086 passed |
| `npm run typecheck` (web) | không lỗi |
| `npm test` (web) | 102 pass, 0 fail |
| `npx prettier --check .` (web) | All matched files use Prettier code style |

Test mới: `backend/tests/unit/test_google_auth.py` (cấu hình, băm, adapter bằng `httpx.MockTransport`, routes, migration import được); `web/tests/login.test.ts` (hai trạng thái hàng Google). `test_web_search.py` cập nhật payload capabilities.

## Chưa làm / chưa kiểm

- Chưa thử với Google thật (cần OAuth client); chưa chạy migration 0006 trên PostgreSQL thật (test integration cần DB, chưa chạy ở đây). Cần chạy `alembic upgrade head` rồi `downgrade -1` trên DB tạm trước khi deploy.
- `docs/api/openapi.json` chưa sinh lại (thêm 2 route và trường capabilities); lead sinh.
- `scripts/deploy.sh` chỉ kiểm các biến Discord, không đụng Google (tùy chọn).

## Cấu hình người dùng cần làm

- Google Cloud Console, OAuth client loại Web application, Authorized redirect URI: `https://tarnished.liemdai.io.vn/api/v1/auth/google/callback`.
- `.env` production: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (cùng `AUTH_SECRET` sẵn có). `GOOGLE_REDIRECT_URI` do compose suy ra từ `DOMAIN`.
