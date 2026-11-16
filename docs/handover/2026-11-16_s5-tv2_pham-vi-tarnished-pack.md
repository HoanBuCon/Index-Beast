# Sprint 5 TV2 · Chặn trang độc quyền Tarnished Pack khỏi corpus

Ngày 16/11/2026. Nhánh `fix/s5-tv2-ingest-scope`, nền `develop` `c5635ec`. Thẻ FR-ING-07 và lỗi phạm vi dữ liệu đã xác minh.

## Phạm vi sửa

- `backend/ingest/transform/wiki_quality.py`: nhận diện tựa ngoài phạm vi, câu độc quyền trong đoạn dẫn hoặc huy hiệu `TP.webp` trong ngữ cảnh bài về mảnh/bộ giáp. Gán lý do `external_tarnished_edition_content` khi bằng chứng từ nội dung đủ rõ.
- `backend/ingest/chunk/full.py`, `backend/ingest/chunk/load_full.py`: chunker xuất 0 chunk cho document external; preflight chỉ chấp nhận document `out_of_scope` có reason hợp lệ và không có chunk. Tăng `WIKI_QUALITY_VERSION` thành `s4-full-chunk-1.1` để update hiện cảnh báo pipeline version khác.
- `backend/ingest/update.py`: refresh category chỉ xem Nightreign/Tarnished Edition/Tarnished Pack là ngoài phạm vi, giữ SotE theo ADR-004. Discovery category lỗi giờ làm lượt cập nhật thất bại an toàn và giữ nguyên cache trước đó thay vì dùng cây category thiếu để xóa dữ liệu.
- `backend/ingest/sources/wikigg.py` và `backend/ingest/update.py`: xác minh tập page ID và revision của phản hồi metadata trước khi dựng kế hoạch. Trang xóa phải có tín hiệu `missing` cho page ID được hỏi. Xem [mã nguồn MediaWiki ApiQuery](https://doc.wikimedia.org/mediawiki-core/1.45.3/php/ApiQuery_8php_source.html).
- `backend/ingest/update_cli.py`: preview bootstrap giữ state trong bộ nhớ. Checkpoint khi chạy thật gắn đích PostgreSQL, Qdrant, collection và chính sách corpus. CLI chặn state lệch đích hoặc collection chưa tồn tại. Nếu state cũ chưa ghi đích, sao lưu state, xác minh bản đang phục vụ rồi bootstrap lại trước lượt thật.

## Kiểm tra artifact đã lưu (chỉ đọc)

Quét **4.164 snapshot raw** trong `D:/Index-Beast/backend/data/delivery/final/raw/snapshots`. Có 517 body chứa dấu hiệu cần đọc HTML. Quy tắc trả về `out_of_scope` cho 36 trang, gồm 13 trang kiểm tra ban đầu. Sáu trang kỹ năng base/SotE có huy hiệu trên liên kết tới trang bị vẫn là `elden_ring`: Overhead Stance, Blind Spot, No Skill, Spinning Slash, Shield Strike và Impaling Thrust.

Ví dụ hồi quy: Silver Grooved Gauntlets dùng “are an armor piece” cùng huy hiệu trong Acquisition, Spectral Steed Regalia ghi phát hành cùng Tarnished Edition, Muleta và Causality’s Wrath ghi độc quyền với một vũ khí được đánh dấu Tarnished Pack ngay trong đoạn dẫn.

Unit suite backend đạt 1.287 test, 20 skip. Ruff check và format check đã qua. Kiểm fixture gồm bootstrap preview, collection thiếu, discovery lỗi, phản hồi metadata thiếu, trang bị xóa xác nhận bằng page ID và zero-chunk khi ngoài phạm vi.

## Dữ liệu lịch sử và bước chuyển cần duyệt riêng

Chunker mới không phát sinh chunk cho các trang này. Tuy nhiên loader PostgreSQL toàn bộ bỏ qua document `out_of_scope` thay vì xóa/sửa record đã active; bản sửa này không có cleanup dữ liệu lịch sử. Khi được duyệt vận hành, dựng artifact mới từ raw, nạp vào Qdrant collection tách biệt, kiểm tra kết quả, đối soát riêng các document/chunk PostgreSQL cũ, rồi mới chuyển collection/state. Không dùng lại collection đang phục vụ để thử nghiệm.

## Giới hạn

- Kiểm offline áp dụng trực tiếp quy tắc phạm vi trên raw local và chạy fixture cho hợp đồng chunk/preflight. Artifacts đang sử dụng chưa được tái dựng.
- Wiki.gg, PostgreSQL và Qdrant thật chưa được dùng trong lượt này. Lịch cập nhật hằng tuần nằm trong PR tài liệu/backlog riêng. Hai trường hợp Origins và Samurai được để riêng theo quyết định của TV2.
- Trang có cách trình bày khác những dấu hiệu đã xác minh cần được đối chiếu bằng raw trước khi mở rộng quy tắc.
