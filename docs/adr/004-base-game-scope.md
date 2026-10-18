# ADR 004 Phạm vi lore Elden Ring

Ngày: 2026-10-17. Trạng thái: Chấp nhận theo yêu cầu nhóm 4 Hollows.

## Quyết định

IndexBeast tập trung trả lời câu hỏi về lore **Elden Ring base game** bằng tiếng Việt và tiếng Anh.

## Áp dụng

- Ingestion, retrieval và web fallback chỉ xử lý dữ liệu lore thuộc base game.
- Chunk được gán `game_scope=base`; dữ liệu cần được rà soát theo trang và section trước khi index.
- Golden set dùng câu hỏi và nguồn tham chiếu thuộc phạm vi này.
- README, SRS, techstack, kiến trúc và sprint plan dùng cùng phạm vi.

## Lý do và hệ quả

Phạm vi dữ liệu rõ giúp nhóm tập trung thời gian xây pipeline RAG và đánh giá chất lượng trong môn NLP. Các module hiện vẫn là khung xương; quyết định này chưa đồng nghĩa mọi bộ lọc ingestion đã được triển khai.
