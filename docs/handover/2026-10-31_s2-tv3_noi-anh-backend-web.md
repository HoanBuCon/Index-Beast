# Bàn giao nối ảnh backend vào chat web

31/10/2026 · TV3 — MinhMuc · IndexBeast / 4 Hollows.
Theo yêu cầu người dùng, TV3 nối API ảnh vào UI TV4 đang có; không nhận thay phần thiết kế giao diện của TV4.
Nhánh `feature/s2-tv3-connect-rag-images`, HEAD nền `35cce86`.
Working tree trước tác vụ có sửa JSON recovery chưa commit: giữ nguyên toàn bộ, không stash/reset/rebase.
Các thay đổi đó vẫn cùng working tree; cần tách phạm vi khi review/commit. Chưa commit/push/PR/merge.

## Nguyên nhân không thấy ảnh

Backend đã có `images`, nhưng frontend chưa khai báo/đọc field này trong JSON, SSE, message và storage.
`MessageList` chỉ nhận map fixture từ trang preview nên chat thật không truyền ảnh cho component.
Không phải chỉ cần thêm câu "gửi ảnh" vào prompt. Resolver chọn ảnh theo chunk được citation validate.

## Đã thay đổi

- [DTO](../../web/src/api/types.ts), [media validator](../../web/src/api/images.ts),
  [client](../../web/src/api/client.ts), [events JSON](../../web/src/api/chat.ts): nhận metadata ảnh đúng contract;
  SSE ảnh nằm ở event sources, không ở done/token. Thiếu field tương thích response cũ.
- [Patch state](../../web/src/hooks/chatState.ts), [hook](../../web/src/hooks/useChatStream.ts),
  [storage](../../web/src/lib/storage.ts): giữ images qua JSON/SSE và reload lịch sử; chỉ lưu metadata.
  Media sai bị loại, không làm mất text hoặc cả conversation.
- [Adapter UI](../../web/src/components/chat/answerMedia.ts),
  [MessageList](../../web/src/components/chat/MessageList.tsx),
  [component ảnh](../../web/src/components/chat/AnswerIllustrations.tsx): hiển thị ảnh backend sau khi answer hoàn tất,
  grounded=true; nguồn, caption, alt và credit từ metadata. Không đoán loại thực thể hoặc tạo URL từ text model.
- [Fixture](../../web/src/fixtures/answerIllustrations.ts) và
  [preview](../../web/src/pages/AnswerMediaPreviewPage.tsx): giữ ba lựa chọn cũ, không trộn loại related của backend vào fixture.
- [Tests](../../web/tests/backendImages.test.ts), [hướng dẫn](../../web/ANSWER_IMAGES.md),
  [contract TV4](../api/images-tv4.md): cập nhật trạng thái đã nối frontend.

## Quy tắc cần giữ

Chỉ URL `/api/v1/images/<sha256>` cùng origin, ID hash hợp lệ, source URL HTTP(S), indices có trong sources.
Dedup, tối đa 3; giữ unknown metadata, không tự gán review/license approval.
Không dùng fixture, gallery hoặc từ khóa để lấp khi images rỗng. Không cho Markdown tự tải ảnh.
Message đang stream/lỗi/hủy/user/grounded=false không hiển thị media.
Ảnh mất hoặc lỗi mạng dùng trạng thái lỗi/thử lại của component TV4, không làm mất đáp án text.

Không sửa backend resolver/contract, không gọi LLM, embedding/indexing hoặc ghi DB/Qdrant.
Không sửa .env thật. Không mở rộng bot Discord trong tác vụ này.

## Kiểm chứng thực tế

Từ `web/`:

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run test:integration
npm.cmd run build
```

Kết quả: **30/30 test frontend**, gồm 6 test media tích hợp mới; **9/9 integration** qua Vite proxy/FastAPI mock.
Typecheck và production build đạt. Giữ các test fixture/Markdown/sources/feedback/HTTP LAN cũ.
Các test mới kiểm JSON/SSE → patch state, getConversation, localStorage, URL/citation/dedup và render thật qua SSR.

Đã GET trực tiếp backend đang chạy: Bloodhound's Fang, Ranni the Witch, Messmer the Impaler đều HTTP 200,
MIME PNG/PNG/JPEG, SHA-256 bytes khớp image ID trong audit cũ.
GET Bloodhound's Fang qua web proxy đang chạy cũng 200, PNG, hash khớp.
Chỉ đọc ảnh, không gọi /chat hoặc DeepSeek. Cổng lấy từ cấu hình local, không ghi cứng.
Chưa chạy E2E câu hỏi thật bằng model hoặc kiểm trực quan UI trong trình duyệt ở tác vụ này.

## Cách thử và phần còn lại

Web đang chạy: Ctrl+F5. Nếu chưa chạy dùng `make web` từ gốc; API dùng RAG và bật ảnh như cấu hình backend hiện có.
Tạo chat mới chế độ API/API streaming, hỏi “Bloodhound's Fang có hiệu ứng gây chảy máu không?”.
Không cần restart API chỉ vì thay frontend, không cần index lại. Lượt hỏi thật có phí LLM do người dùng thực hiện.

Ảnh chỉ có khi đáp án trích chunk có association hợp lệ; cùng câu hỏi có thể chọn nguồn khác và trả images=[] đúng policy.
Lịch sử cũ chưa ghi images không tự thêm ảnh. Backend history vẫn RAM, restart API có thể làm ID hội thoại cũ 404;
tạo hội thoại mới trong trường hợp đó. Giới hạn retrieval/image association không được che bằng ảnh fixture.
TV4 có thể chỉnh bố cục tiếp trên component hiện có; không cần thay contract dữ liệu.
