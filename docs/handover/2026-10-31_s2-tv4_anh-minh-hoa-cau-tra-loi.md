# TV4 · Ảnh minh họa kèm câu trả lời bằng fixture

## Phạm vi và căn cứ

Nhánh `feature/tv4-hinh-anh-cau-tra-loi`. Người dùng yêu cầu làm UI trước cho nhân vật/vũ khí/vật phẩm, phối hợp ảnh thật sau. Đã đọc quy ước, AGENTS, kiến trúc, SRS và các nhiệm vụ TV4 trong planning/sprint_plan.json: giữ công việc trong frontend TV4, không thay kế hoạch hoặc nhận phần dữ liệu/RAG/API của TV1–TV3. Đây là phần mở rộng UI theo yêu cầu người dùng, không tự đánh dấu tính năng ảnh thật hoặc checklist chung hoàn thành.

Chỉ sửa `web/` và tài liệu bàn giao/index. Không đổi backend, bot, planning, API DTO/OpenAPI, localStorage schema, root README, sidebar, background, favicon, composer hoặc nút gửi. Không cài dependency, gọi model/LLM/API thật, commit/push/rebase.

## File thay đổi

- `web/src/components/chat/answerMedia.ts`: kiểu dữ liệu UI, nhãn loại đối tượng, kiểm tra URL, điều kiện chỉ assistant hoàn tất mới có ảnh.
- `web/src/components/chat/AnswerIllustrations.tsx`: frame kích thước cố định, img/alt, caption/nguồn, loading/error/manual retry; timeout 15 giây, xử lý ảnh cache; đổi src tạo lượt tải mới.
- `web/src/components/chat/MessageList.tsx`: nhận map ảnh theo ID tùy chọn; đặt sau nội dung câu trả lời, trước nguồn/feedback. Giữ comment, Markdown an toàn, skipHtml, img Markdown bị chặn, nguồn, feedback và logic chờ/dừng.
- `web/src/styles/answer-media.css`: chỉ scope phần ảnh và preview, dùng token theme sẵn có, desktop hai cột/mobile một cột, object-fit contain.
- `web/src/fixtures/answerIllustrations.ts`: ba ví dụ tách riêng; tranh Elden Beast có sẵn, biểu tượng vũ khí chung và chìa khóa. Nguồn là file asset cục bộ kèm ghi chú chưa xác minh tác giả/giấy phép; không giả làm ảnh một vũ khí có tên cụ thể.
- `web/item_/MENU_Tab_07.png`: chép nguyên ảnh từ bộ hi_01 của người dùng, SHA-256 nguồn/đích giống nhau; chỉ dùng fixture, không đổi file nguồn ngoài dự án.
- `web/src/pages/AnswerMediaPreviewPage.tsx`: chọn ba loại/cả ba và sáu tình huống, không gọi API hoặc thay lịch sử.
- `web/src/App.tsx`: route `/preview/answer-images` chỉ DEV, lazy import fixture; bản production loại bỏ route và dữ liệu.
- `web/tests/answerMedia.test.ts`: ba test mới gồm các nhánh hoàn tất/đang trả lời/dừng/user/không có ảnh/URL xấu, SSR nguồn/feedback/Markdown, loading/error; SSR Vite tắt ws để không tranh cổng HMR với test khác.
- `web/ANSWER_IMAGES.md`: hướng dẫn chạy và điểm tích hợp sau.

## Cách dùng và quyết định

Chạy `make web` hoặc `npm.cmd run dev` trong web, mở `http://127.0.0.1:15173/preview/answer-images` (thay cổng nếu WEB_PORT khác). Trang chat chính giữ nguyên; fixture không tự xuất hiện khi hỏi thật hoặc API lỗi. Không dò từ khóa; không thêm trường vào ChatResponse/Message. UI thật chỉ có ảnh khi adapter tương lai truyền `illustrationsByMessage` sau khi thống nhất dữ liệu.

Loading mô phỏng giữ nguyên đến khi chọn tình huống khác. Lỗi mô phỏng xảy ra lần đầu; nút Thử lại bắt đầu tải ảnh cục bộ thật. Ngoài fixture, loading/error do img events thực tế và timeout điều khiển; mỗi lần thử lại do người dùng bấm, không tự lặp. Ảnh chỉ hiển thị sau câu trả lời hoàn tất, không hiện cho assistant incomplete hoặc lượt cuối còn busy. Lượt trước đã hoàn tất vẫn có thể giữ ảnh khi đang trả lời lượt tiếp theo.

Khung và thông tin nguồn vẫn giữ khi ảnh lỗi; không có dữ liệu ảnh thì trả null, không dựng frame trống. URL nguồn và ảnh chỉ HTTP(S)/root-relative; không javascript/data/protocol-relative/credentials. Không lưu token, không đọc .env cho fixture.

## Kiểm tra thực tế

- `npm.cmd test`: **24/24 đạt**, gồm 21 test cũ và 3 test mới. HMR báo tranh cổng trong lần thử đầu; test SSR mới đã tắt ws, lần cuối không còn cảnh báo và toàn bộ vẫn đạt.
- `npm.cmd run format:check`: đạt. Build TypeScript/Vite production đạt.
- Chrome/CDP dev: cả ba loại tải được, alt/name/source đúng, object-fit contain; thành công/tải/lỗi/không ảnh/câu trả lời dang dở/dừng hoạt động đúng. Retry bằng Enter, Tab tới nguồn được.
- Giữ request ảnh cục bộ bằng Fetch CDP để kiểm tra loading thực, sau đó fail request để kiểm tra onError; không tự retry. Bấm Thử lại tải thành công. Kích thước frame trước/sau tải hoàn toàn bằng nhau. Script QA ban đầu gửi phím Enter thiếu text nên không kích hoạt nút; đã sửa thao tác CDP, không thay logic ứng dụng để né lỗi kiểm tra.
- Desktop 1440, tablet 768, mobile 360 px không tràn ngang; đã xem screenshot cả ba loại, loading/error và mobile. Lịch sử trước/sau preview giống nhau, ghi nhận **0 request `/api`**, không lỗi JavaScript.
- Production Vite preview: route thử không hiện bộ điều khiển, root có composer bình thường; JS bundle không chứa marker fixture hoặc đường dẫn route thử. Không có request API trong QA production.
- Taste source lint cho component/CSS/page mới: 0 FAIL, 0 WARN. Inspector DEV tại 1440/768/390: 0 FAIL, 2 WARN — Cambria là font hệ thống có sẵn theo theme cũ, và dev-server là chủ ý vì fixture không chạy ở production. Không chỉnh font/sidebar chỉ để xóa cảnh báo ngoài phạm vi. Giữ hướng true-black-flat đã có, không redraw cho một component nhỏ.
- Artefact QA Git bỏ qua: `web/.taste-skill/answer-images-*.jpg`, `answer-images-after/`, `check-answer-images.mjs`, `check-answer-images-production.mjs`. Chưa chạy API/Discord thật hoặc backend unit trong lượt này.

## Giới hạn và bàn giao tiếp

Chỉ hoàn tất phần hiển thị frontend bằng fixture. Chưa có tìm ảnh, xác định thực thể, ảnh từ backend, tích hợp vào câu trả lời thật hoặc đồng bộ lịch sử ảnh. TV1 cần thống nhất hợp đồng/URL truyền; TV2 chuẩn bị metadata ảnh/nguồn/giấy phép; TV3 xác định thực thể liên quan và spoiler theo cách nhóm chốt. Đây là các điểm cần phối hợp, không tự sửa phần của các thành viên.

Tài nguyên fixture do người dùng cung cấp, chưa xác minh quyền phát hành/ghi tác giả; chỉ nằm ở trang DEV và không đóng gói vào production. Không coi link file fixture là nguồn wiki hoặc bằng chứng cho một câu trả lời RAG.
