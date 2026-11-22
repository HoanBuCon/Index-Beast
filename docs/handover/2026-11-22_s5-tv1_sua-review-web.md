# Sửa review TV2 phía web (#1, #13, #17)

Nhánh `fix/s5-tv1-review-web`, chỉ sửa `web/**`.

## Đã sửa
- **#1 (P1)** Lịch sử local chỉ hiện cho khách (không `ownerUserId`) hoặc đúng tài khoản hiện tại (`viewerConversations` trong `web/src/lib/accountData.ts`, dùng bởi `useConversations(viewer)`). Khi auth đang tải thì ẩn mọi bản có chủ; khi auth đã biết (hết phiên, đổi tài khoản) bản của chủ khác bị xóa khỏi state và localStorage. `useChatStream` nhận `identity`: đổi danh tính thì hủy luồng và bỏ cập nhật muộn; `openRemote` và `acceptClaim` bỏ phản hồi đến sau khi danh tính đã đổi.
- **#13** `readConversations` dùng `readClarification`; clarification sai dạng bị bỏ, tin nhắn vẫn giữ.
- **#17** `turnId` chuyển khỏi `ChatOptions` (transport) sang `SendOptions` của `useChatStream`.

## Quyết định
- Hội thoại guest (không chủ) vẫn hiện cho mọi người dùng để luồng "nhận hội thoại khách" không đổi.
- Không có test cho phần hủy luồng/phản hồi muộn (cần môi trường hook có effect; SSR không chạy effect); logic nằm ở generation guard trong `useChatStream` và so sánh `identity` ref trong `ChatPage`.

## Kiểm tra
`npm run typecheck` sạch; `npm test` 74/74 pass (có `web/tests/historyOwner.test.ts`: hết phiên, đổi tài khoản, đang tải, dữ liệu chủ cũ, clarification hỏng); `npx prettier --check .` sạch.
