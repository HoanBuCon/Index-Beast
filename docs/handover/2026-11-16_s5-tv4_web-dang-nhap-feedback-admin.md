# TV4 · Web: đăng nhập Discord, feedback, admin, xóa tài khoản (S5)

Ngày: 16/11/2026. Nhánh: `feature/s5-web-dang-nhap-feedback`. **Phần việc của TV4, do agent của TV1 làm hộ.**
Chỉ sửa `web/` và tài liệu; không đụng backend, bot, hai video trong `web/src/video`.

## Đã làm

| Yêu cầu | Nội dung |
|---|---|
| FR-AUTH-09 / FR-WEB-09 | `web/src/api/auth.ts` (capabilities, `/auth/me`, logout, `/me/conversations`, claim, `DELETE /me`), hook `useAuth`. `LoginPage`: nút Discord điều hướng trình duyệt tới `/api/v1/auth/discord/login?next=/chat`, **chỉ hiện khi `auth_available=true`**; đã đăng nhập thì hiện "Tiếp tục với tư cách …"; `/?login=denied` hiện thông báo nhẹ. Google: nút khóa, ghi "(sắp có)", không có luồng giả. Sidebar: tên người dùng, Đăng xuất, "Đăng nhập Discord" (khi khách và auth bật), mục "Của tài khoản" liệt kê hội thoại server chưa có trong trình duyệt; mở bằng `GET /conversations/{id}` không gửi token. Sau đăng nhập, mỗi hội thoại khách có `serverId`+`serverToken` được `POST /me/conversations/claim` (404/401 bỏ qua), một lần mỗi tài khoản mỗi lần tải trang. |
| FR-WEB-04 | `FeedbackButtons` nay hiển thị dưới câu trả lời hoàn tất (có `serverId`, không `incomplete`, không phải câu hỏi bổ sung, không ở chế độ minh họa). 👍 gửi ngay; 👎 mở ô lý do tuỳ chọn. Khách gửi `X-Conversation-Token`, người đăng nhập chỉ dùng cookie. |
| FR-WEB-08 | `AdminPage`: nếu `/auth/me` báo `is_admin` thì tự tải `/admin/stats` bằng cookie, không cần token; token dán tay vẫn dùng được (ưu tiên khi có). Hiển thị hội thoại gần đây, 👎, job ingestion, eval, trace. |
| FR-AUTH-08 (phần web) | Menu người dùng có "Xóa tài khoản" + hộp xác nhận (`role="alertdialog"`, focus vào "Hủy", Esc đóng) nói rõ hội thoại bị xóa vĩnh viễn; xác nhận mới gọi `DELETE /api/v1/me`, thành công thì về trạng thái khách và xóa bản lưu cục bộ của các hội thoại thuộc tài khoản. Trang About có mục "Quyền riêng tư" (mã Discord băm, giữ 90 ngày, xóa bằng "Xóa tài khoản" hoặc `/clear` của bot). |
| FR-WEB-06 | Rà soát phần đã chạm: hộp xác nhận rộng `min(360px, 100vw-32px)`, nút ≥ 32px, nhãn/aria đầy đủ, focus quản lý. Không thiết kế lại. |

Cookie: mọi `fetch` dùng `credentials: "same-origin"` (production cùng origin qua Caddy; dev qua proxy Vite `/api`), web không lưu token phiên.

## Quyết định

- Repo dùng `node --test` + render SSR qua Vite, **không có vitest/testing-library**; tôi theo đó và không thêm dependency.
- Hội thoại mở từ tài khoản được ghi vào localStorage như hội thoại thường (cần cho lịch sử/gửi tiếp); trên máy dùng chung, đăng xuất không xóa chúng. Xóa tài khoản thì xóa.
- Không có script `lint` trong `web/package.json`; kiểm tra bằng `tsc --noEmit` (trong `build`) và `prettier --check`.

## Kiểm tra

- `cd web && npm ci`: ok.
- `npm test`: 63 pass / 0 fail (thêm `tests/auth.test.ts`, `tests/account.test.ts`; sửa `login.test.ts`, `traceLink.test.ts`).
- `npm run build` (gồm `tsc --noEmit`): ok. `npx prettier --check .`: ok.

## Chưa kiểm chứng

- **`DELETE /api/v1/me` đến từ nhánh `feature/s5-tv1-quyen-rieng-tu`, chưa gộp vào develop**: nút "Xóa tài khoản" chỉ chạy được sau khi nhánh đó vào.
- Chưa thử với Discord thật, backend thật hay trình duyệt (không có backend/OAuth trong môi trường này). Luồng bấm xác nhận chưa test bằng DOM (không có testing-library); chỉ test `deleteAccount` bằng fetch giả và việc hộp xác nhận hiển thị trước khi gọi API.
- Chưa kiểm responsive/bàn phím trên thiết bị thật.
