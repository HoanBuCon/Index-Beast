# TV2 — chunk metadata và PostgreSQL (chưa nghiệm thu DB)

## Cập nhật: đã kiểm chứng PostgreSQL local

Docker Engine 29.9.2 và postgres:18.6-bookworm hoạt động sau khi người dùng cài lại.
11 integration tests đạt (schema/repositories và loader trên database tạm), bao gồm
rerun không đổi chunk/timestamp, quarantine không ghi đè, rollback sau replace lỗi.
Test mới: tests/integration/test_chunk_load.py; không đổi mã/schema TV1.
Đã chạy migration 0001 cho database local của dự án. Đã load artifact 200 trang hai lần:
51 documents, 199 chunks, không tăng số lượng ở lượt hai. Cả hai ingestion_jobs partial
(51 OK/103 review). Những document có metadata chưa rõ được giữ ngoài DB, không ép nhãn.
Artifact postgres-report.json lưu tại data/chunk_runs/s2-card-chunk-200.
Chưa nghiệm thu full corpus, chưa có đánh giá retrieval hoặc review contract text TV3.
Các phần dưới mô tả lịch sử trước khi có PostgreSQL; trạng thái DB hiện tại theo mục này.

Nhánh feature/s2-tv2-chunking-metadata từ origin/develop 02c4abf.
Document/chunk ID dùng core.ids; ordinal theo toàn document. ID nội dung prototype giữ
ở artifact_content_id; provenance section/unit/ảnh vẫn giữ. Không đổi namespace chung.

CLI chunk giữ nguyên; nạp: `python -m ingest.chunk.postgres <chunk-run-dir>`.
Thêm `--validate-only` để kiểm tra offline và ghi postgres-validation.json.
Loader kiểm checksum, ID, metadata và raw provenance; document có chunk chưa đủ căn cứ
được giữ nguyên trong DB, không thay thế một phần. Upsert document + replace chunks cùng
transaction, không tạo embedding/Qdrant/entities. No-op chunks nếu dữ liệu đã giống nhau.

Contract đề xuất: DB text chứa embedding_text gồm passage/title/section/context, token_count
tính toàn chuỗi này. TV3 phải review trước khi index để không thêm prefix lần hai.
Artifact text vẫn giữ nguyên body. game_scope cấp document NULL vì có thể là trang trộn;
chunk được nhận chỉ base heuristic. updated_at của artifact là thời điểm tạo, DB là thời
điểm ghi; source_updated_at vẫn chưa có bằng chứng. Không tự đổi migration TV1.

Kiểm chứng: 155 passed, 11 deselected; Ruff check/format các file đổi đạt.
Đã chunk lại 200 trang từ s2-card-clean-200: 1648 chunk, max 450 token, 1646 unit phủ đủ.
Output backend/data/chunk_runs/s2-card-chunk-200. Kiểm tra nạp offline: 51 document đủ
metadata, 103 document phải review (trong 154 document có chunk); 46 trang còn lại không
có section base được chunk. Không có ghi DB trong lần kiểm tra này.

PostgreSQL local từ chối kết nối; chưa thử commit/rollback/no-op trên DB thật.
Chưa nghiệm thu corpus full, chưa đóng thẻ, chưa tạo nhánh mở rộng hệ thống thứ tư.
Các nhánh crawl/clean độc lập từ develop; cần tích hợp qua PR theo thứ tự và kiểm tra
contract TV1/TV3. Không tự merge develop.
