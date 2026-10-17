# ADR 004 Phạm vi Elden Ring base game

Ngày: 2026-10-17. Trạng thái: Chấp nhận theo yêu cầu nhóm 4 Hollows.

## Quyết định

IndexBeast chỉ trả lời về lore **Elden Ring base game** bằng tiếng Việt và tiếng Anh. Mọi DLC, bao gồm **Shadow of the Erdtree**, và game **Elden Ring Nightreign** đều nằm ngoài phạm vi dự án hiện tại, không phải hạng mục mở rộng đang chờ chốt.

## Áp dụng

- Ingestion chỉ giữ trang/section về base game, gán `game_scope=base`; nội dung trộn cần lọc theo section, phần chưa xác định cần kiểm tra thủ công.
- Retrieval luôn giới hạn base game. Câu hỏi DLC/Nightreign phải nhận thông báo ngoài phạm vi.
- Web fallback áp dụng cùng giới hạn, không dựa riêng vào allowlist domain và không chạy để trả lời câu hỏi đã xác định ngoài phạm vi.
- Golden set chứa câu base game cùng câu kiểm thử từ chối DLC/Nightreign; không chấm câu hỏi DLC theo tiêu chí trả lời đúng lore DLC.
- Sprint plan, SRS, techstack và tài liệu kiến trúc phải đồng nhất quyết định này. Hỗ trợ DLC/Nightreign trong tương lai phải qua quy trình thay đổi phạm vi mới.

## Lý do và hệ quả

Thu hẹp dữ liệu và bài toán đánh giá để phù hợp môn NLP và nguồn lực nhóm. Các phần triển khai vẫn đang ở giai đoạn khung xương; quyết định tài liệu này chưa có nghĩa bộ lọc phạm vi đã được lập trình.
