# Handover · TV1 · S5 · Sidebar hội thoại theo chủ sở hữu (2026-11-23)

## Nguyên nhân / bối cảnh

Người dùng báo: đăng nhập lại thì hội thoại của tài khoản hiện ở "Của tài khoản"; bấm vào một mục thì nó nhảy lên "Tất cả"; đôi khi mục trong "Của tài khoản" trông như bị "kẹt".

Sidebar nhóm theo **nơi lưu** thay vì **chủ sở hữu**:

- "Tất cả" = `history.conversations` (bản lưu trong trình duyệt).
- "Của tài khoản" = `remoteOnly` = hội thoại server chưa có bản cục bộ.
- Đăng xuất xóa bản cục bộ của tài khoản (`purgeAccountConversations`), nên đăng nhập lại chúng chỉ nằm ở "Của tài khoản"; `openRemote` tải về một bản cục bộ nên mục chuyển sang "Tất cả".

Triệu chứng "kẹt / không có nút xóa" trên production là **mã trước PR #152** (thêm nút xóa cho cả hai danh sách); PR #152 chưa được deploy, release PR #153 đang mở. Phần xóa của #152 được giữ nguyên.

## Thay đổi

- `web/src/lib/accountData.ts`: thêm hàm thuần `groupSidebarConversations(local, myConversations, userId)` trả `{ account, browser }`.
  - `account`: bản cục bộ có `ownerUserId === userId` (hoặc không chủ nhưng `serverId` thuộc `/me/conversations`) gộp với dòng chỉ có trên server, khử trùng theo serverId (key ổn định = serverId, bản cục bộ chưa có serverId dùng `local:<id>`), mới nhất trước (bản cục bộ dùng `updatedAt`, dòng server dùng `created_at`).
  - `browser`: bản cục bộ không có chủ (khách). Bản của chủ khác không bao giờ được liệt kê; khách chưa đăng nhập: `account` rỗng.
- `web/src/pages/ChatPage.tsx`: dùng helper. Mục "Của tài khoản" mở bản cục bộ trực tiếp (`openLocal`) hoặc tải từ server (`openRemote`), × xóa trên server + cục bộ (`removeConversation` / `deleteFromAccount`), mục đang mở được tô sáng. Mục còn lại tên "Trên trình duyệt này" khi đã đăng nhập, "Tất cả" với khách; mục rỗng thì ẩn. Hội thoại mới của người dùng đã đăng nhập (có `ownerUserId`) hiện ngay ở "Của tài khoản", không chờ `/me/conversations` tải lại.
- `web/tests/sidebarGroups.test.ts` (mới): test đơn vị cho helper (gộp, khử trùng, thứ tự, khách và tài khoản, loại chủ khác, bản trùng) và SSR sidebar (một mục chỉ xuất hiện ở đúng một mục trước và sau khi có bản cục bộ).

## Quyết định

- Giữ nguyên ClaimPrompt, purge khi đăng xuất, xóa tài khoản và lọc chủ khác (`viewerConversations`); không đổi `useConversations`.
- Bản cục bộ chưa có `serverId` nhưng có `ownerUserId` vẫn nằm ở "Của tài khoản" (xóa chỉ cục bộ).

## Kiểm tra

- `npm run typecheck`: sạch.
- `npm test`: 94 test, 94 pass, 0 fail (gồm `historyOwner.test.ts`, `account.test.ts`).
- `npx prettier --check .`: sạch.

## Chưa làm / chưa kiểm chứng

- Chưa thử bằng trình duyệt thật với backend; chỉ SSR và test đơn vị.
- Test SSR không mô phỏng việc bấm (không có DOM); tô sáng mục đang mở dựa trên cùng điều kiện `active === c.id` như trước.
