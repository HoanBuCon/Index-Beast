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
- Hội thoại tạo/mở khi đang đăng nhập mang `ownerUserId` và bị xóa khỏi localStorage khi đăng xuất thành công hoặc xóa tài khoản (xem "Sửa sau review").
- Không có script `lint` trong `web/package.json`; kiểm tra bằng `tsc --noEmit` (trong `build`) và `prettier --check`.

## Kiểm tra

- `cd web && npm ci`: ok.
- `npm test`: 71 pass / 0 fail (sau review; trước review 63) (thêm `tests/auth.test.ts`, `tests/account.test.ts`, `tests/review.test.ts`; sửa `login.test.ts`, `traceLink.test.ts`).
- `npm run build` (gồm `tsc --noEmit`): ok. `npx prettier --check .`: ok.

## Sửa sau review

1. `Conversation.ownerUserId`: gắn cho hội thoại tạo/mở khi đã đăng nhập (`stampOwner`); hội thoại khách đã có trên server giữ trạng thái khách. Xóa tài khoản xóa mọi bản cục bộ có chủ đó, đã nhận, hoặc có trong danh sách server của tài khoản (`accountConversationIds`).
2. `logout` chỉ về chế độ khách khi POST `/auth/logout` thành công, hoặc POST lỗi nhưng `/auth/me` báo hết phiên (`logoutVerified`); không thì giữ người dùng và hiện lỗi.
3. Đăng xuất thành công cũng xóa các bản cục bộ thuộc tài khoản (kể cả bản đã nhận, vốn đã bỏ `serverToken`).
4. Nhận hội thoại khách chỉ sau khi người dùng bấm Đồng ý ở hộp "Chuyển N hội thoại khách trong trình duyệt này vào tài khoản?"; "Không" được nhớ trong `sessionStorage` của phiên. Nhận xong thì bỏ `serverToken` và gắn chủ.
5. `useAuth` chạy một lần ở `App` và chia sẻ qua `AuthContext` (capabilities gồm `authAvailable/searchAvailable/traceAvailable`, user, hội thoại của tôi); ChatPage bỏ fetch capabilities riêng, AdminPage bỏ `/auth/me` riêng.
6. Xác nhận xóa tài khoản dùng `<dialog>` + `showModal()` (khóa focus, Esc có sẵn), focus đầu vào "Hủy".

## Chưa kiểm chứng

- **`DELETE /api/v1/me` đến từ nhánh `feature/s5-tv1-quyen-rieng-tu`, chưa gộp vào develop**: nút "Xóa tài khoản" chỉ chạy được sau khi nhánh đó vào.
- Chưa thử với Discord thật, backend thật hay trình duyệt (không có backend/OAuth trong môi trường này). Luồng bấm xác nhận chưa test bằng DOM (không có testing-library); chỉ test `deleteAccount` bằng fetch giả và việc hộp xác nhận hiển thị trước khi gọi API.
- `showModal()`, Esc và khóa focus của `<dialog>` chỉ kiểm bằng đọc code/markup SSR, chưa chạy trong trình duyệt.
- Chưa kiểm responsive/bàn phím trên thiết bị thật.
