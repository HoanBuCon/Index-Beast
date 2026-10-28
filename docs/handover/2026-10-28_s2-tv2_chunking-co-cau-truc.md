# Bàn giao TV2 Sprint 2 prototype chunking có cấu trúc

Ngày: 28/10/2026. Chủ sở hữu: TV2 (UncleThing). Phạm vi FR-ING-04 và metadata artifact theo FR-ING-05, theo đề xuất ADR-003 và nghiên cứu 200 trang. Nhánh feature/s2-tv2-lam-sach-va-xuat-csv; giữ nguyên các thay đổi đang có trên nhánh. Thay đổi hiện trong working tree, chưa commit/push/merge trong lượt này. Không làm phần embedding/indexing/retrieval/LLM/entities/DB của TV3/TV1.

## Đã triển khai

- core/text/html_clean.py: clean v2 giữ typed turns trong bảng thoại, language label, trigger từ th, source rows/text theo thứ tự. Kiểm text sau typed conversion phải giống block nguồn. Speaker chỉ lấy khi nguồn cung cấp rõ, không đoán từ page title.
- Khôi phục anchor từ h2/h3 id hoặc span.mw-headline id; khi id lặp trong tab, dùng anchor panel biến thể và giữ heading_anchor gốc. Lấy variant label từ data-title/title/aria-labelledby của nguồn.
- core/text/chunking.py: hàm thuần, gộp block trong cùng section, xử lý riêng table/typed dialogue; kiểm toàn chuỗi final bằng tokenizer được caller truyền vào. Section ngắn được giữ, không ghép xuyên heading chỉ để đủ tối thiểu token.
- Unit dài: ưu tiên ranh giới đoạn/câu, fallback character range có kiểm lại token thật; context trigger/variant/language được lặp ở prefix. Overlap chỉ trong cùng unit, không xuyên điều kiện. Prefix quá dài đi vào review, không truncate lặng lẽ.
- ingest/chunk/runner.py: đọc clean v2, chỉ chunk section base, ghi JSONL/CSV/report/coverage; không tạo encoder hay DB client.
- ingest/__main__.py: thêm chunk, nhận input-dir/tokenizer/output-dir; cap/overlap từ [chunk] sources.toml hoặc CLI override. Nhánh offline chạy trước tạo HTTP client.
- tests/unit/test_chunking_s2.py và ingest/README.md: regression và hướng dẫn.

## Chạy và kiểm chứng thực tế

Chạy clean v2 trên 20 trang rồi chunk: 375 unit/chunk, max 448 token, không unit review. Tiếp theo clean v2 đủ 200 trang, giữ đúng 783 section base, 564 review, 6 excluded.

Tập 200 tạo 1.648 chunk từ 1.646 unit, phủ đủ mọi source character range, max 450 token. Một unit được chia ba fragment, overlap đo lại bằng tokenizer thực là 50/50. Có 862 dialogue chunk, 859 unit mang header điều kiện nguồn, 169 chunk có variant context. Language: en 1.112, ja 429, unknown 107; speaker null khi nguồn thiếu trường tường minh.

Khôi phục đủ 508 anchor của section base có heading; xác nhận từng anchor tồn tại trong raw. Đối chiếu độc lập mọi chunk với prepare_units/processed: nguyên văn slice, không gap, trigger/speaker/lang, prefix, image_ids nằm trong section và token_count đúng re-encode. Hai lần chạy cùng clean input cho logical_content_sha256 giống nhau; updated_at khác theo thời điểm tạo nên không hứa file bytes giống hệt.

Test backend thực tế: 134 passed, 1 integration test deselected. Ruff check/format đạt cho core/text, ingest và test mới. Không chạy notebook, tải model, gọi API LLM, embedding/indexing hoặc ghi entities/PG/Qdrant. Raw/media và artifact clean v1 giữ nguyên; clean v2 nằm trong thư mục mới.

## Artifact

- backend/data/clean_runs/s2-clean-v2-20 và s2-clean-v2-200: processed có typed turns/anchors/variant context, raw không đổi.
- backend/data/chunk_runs/s2-chunk-20: kết quả thử 20 trang.
- backend/data/chunk_runs/s2-chunk-200: chunks.jsonl, chunks.csv BOM, wikigg/<doc>.jsonl, coverage.json, review.jsonl, report.json, validation.json.
- backend/data/chunk_runs/s2-chunk-200-repeat: lần đối chiếu tính ổn định logic.

Artifact/data không commit Git. Gói outputs của chat có CSV/JSONL/report/coverage và bản bàn giao, không nhân bản ảnh.

## Cách dùng và contract

Từ backend:

```powershell
.venv/Scripts/python.exe -m ingest clean --limit 20 --output-dir data/clean_runs/typed-20-new
.venv/Scripts/python.exe -m ingest chunk --input-dir data/clean_runs/typed-20-new --tokenizer "<tokenizer.json-local>" --output-dir data/chunk_runs/chunk-20-new
.venv/Scripts/python.exe -m ingest clean --limit 200 --output-dir data/clean_runs/typed-200-new
.venv/Scripts/python.exe -m ingest chunk --input-dir data/clean_runs/typed-200-new --tokenizer "<tokenizer.json-local>" --output-dir data/chunk_runs/chunk-200-new
```

Output phải mới/rỗng, tách khỏi input. Chunk yêu cầu clean version s2-clean-2.0 và tokenizer local; không tự tải. Cap/overlap mặc định 450/50 từ config, có --max-tokens/--overlap-tokens. Lệnh trả exit 2 nếu có unit chưa chunk được và đã đưa vào review.

text là exact source fragment; embedding_text đã thêm passage/title/section/context và được tính token toàn chuỗi. TV3 dùng embedding_text thì tránh thêm passage prefix lần nữa; nếu đổi context/encoder thì phải kiểm lại budget. section_record_id, unit_id, start/end_char và source_locations cho phép truy ngược nguồn. chunk_id phụ thuộc unit/span/config/tokenizer/content, không dùng một mình title+section.

updated_at là thời điểm sinh chunk artifact, processed_at là lúc clean và fetched_at là lúc tải. source_updated_at còn null; chưa gọi nguồn để bổ sung revision timestamp. Đây là định nghĩa tường minh cho prototype, không giả rằng fetched_at là ngày nguồn sửa. Cần TV3/TV1 review khi nối metadata contract và DB.

Image_ids kế thừa association section, không tạo mô tả/embedding ảnh. Metadata ghi image_association=section; ảnh gallery/không rõ vẫn theo review của cleaner. License unknown không được tự đổi.

## Giới hạn và việc còn lại

Scope base là heuristic, chưa xác minh ngữ nghĩa toàn bộ. 564 review/6 excluded chưa được đưa vào chunks, không phải đã giải quyết xong. Nhãn trigger là header nguồn, chưa thẩm định từng điều kiện gameplay. Speaker của toàn bộ tập hiện null, page context vẫn có; không điền bằng suy đoán. Source_updated_at chưa có nguồn xác thực.

Nhiều chunk ngắn được giữ vì nguyên vẹn nghĩa/điều kiện; chưa có retrieval benchmark để gọi 450/50 tối ưu. Cần TV3 đánh giá retrieval và phối hợp TV2 review chunk boundaries trước production. ADR-003 vẫn Proposed chờ review chính thức; không đổi trạng thái SRS/planning hoặc tự đánh dấu toàn bộ S2 Done. Timestamp artifact làm file hash thay đổi giữa lượt; logical hash/IDs/text vẫn ổn định.

Sự cố đã xử lý: Windows console CP1252 không in được một số đoạn Unicode khi preview; dùng UTF-8 cho stdout preview, các artifact luôn ghi UTF-8. Không phải lỗi dữ liệu. Các invariant budget/coverage không được thay bằng việc nhìn số chunk hoặc model truncation.


## Cập nhật trạng thái Git

Sau lượt triển khai/nghiên cứu này, mã đã được rebase và push lên nhánh riêng theo yêu cầu người dùng. Xem [bàn giao Git](2026-10-28_s2-tv2_day-ma-nguon-github.md) để biết commit, kiểm tra sau rebase và trạng thái review.
