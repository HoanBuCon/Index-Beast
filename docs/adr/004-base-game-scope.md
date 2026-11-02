# ADR 004 Phạm vi lore Elden Ring

> Cập nhật được người dùng duyệt 29/10/2026: Sprint 2 clean/chunk toàn bộ 4164 raw base game + Shadow of the Erdtree. game_scope=elden_ring; release_scope là nhãn có bằng chứng/candidate/unknown. Không áp dụng điều kiện base-only để chặn DLC trong lượt này. Nightreign/Tarnished Edition vẫn ở review. TV3 cần phối hợp bộ lọc retrieval, không thay đổi tự động trong phần việc TV2. Nội dung base-only bên dưới là quyết định trước ngoại lệ này.


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
