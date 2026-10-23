# Prototype ingest Sprint 1

Phụ trách TV2. Lưu raw và ảnh phục vụ IndexBeast; không tạo embedding, không ghi entities/PG/Qdrant. Dùng Python 3.11 và môi trường backend hiện có.

Chạy từ `backend/`, dùng `.venv/Scripts/python.exe` trên Windows hoặc `.venv/bin/python` trên Linux:

```powershell
.venv/Scripts/python.exe -m ingest crawl --dry-run
.venv/Scripts/python.exe -m ingest survey
.venv/Scripts/python.exe -m ingest crawl --page "Ranni the Witch"
.venv/Scripts/python.exe -m ingest crawl --limit 200
.venv/Scripts/python.exe -m ingest report
```

Đặt `INGEST_CONTACT_EMAIL` trong `.env` ở gốc repo. Ingest đọc đúng file đó độc lập với thư mục chạy; biến môi trường thật có ưu tiên cao hơn. Giá trị mẫu được khai báo trong `.env.example`; cấu hình nguồn vẫn ở `ingest/config/sources.toml`. Không cần API key hoặc chạy các service hạ tầng. Trong S1 CLI chạy local; wiring biến ingest và mount dữ liệu trong Compose sẽ phối hợp TV1 khi tích hợp container.

`--no-media` chỉ tải raw. `--refresh-discovery` cập nhật danh sách category; mặc định dùng lại danh sách đã khảo sát. `--limit` là mục tiêu số trang thành công, thử tối đa 3 lần số ứng viên để bù trang lỗi/ngoài phạm vi. Exit 2 nghĩa kết quả partial (thiếu trang hoặc lỗi ảnh), không phải thành công đầy đủ. Không chạy hai CLI ghi vào cùng data directory.

## Artifact và schema version 1

- `data/raw/wikigg/<pageid>.json`: source, source_id, title, url, revision_id, fetched_at, content_format, content, content_hash, categories, sections, image_titles, license, scope_status.
- `data/media/blobs/<2 ký tự đầu hash>/<sha256>.<ext>`: file ảnh gốc nếu imageinfo cung cấp URL gốc; nếu chỉ có URL hiển thị thì manifest ghi `rendition=display_fallback`.
- `data/media/manifests/wikigg/<pageid>.json`: revision trang và từng occurrence: section, alt, caption, trang File, URL ảnh, image_id, path, MIME, kích thước, tác giả/giấy phép, trạng thái.
- `data/media/url-index.json`: cache URL ảnh và source SHA-1 nếu có; kiểm SHA-256 bytes local trước khi dùng lại. Cùng nội dung qua URL khác dùng chung blob.
- `data/reports/categories.json`: danh sách/đếm category và provenance nhóm.
- `data/reports/crawl-<job>.json`: thời gian, số trang mới/cache/thành công/lỗi và trạng thái ảnh. Số ảnh downloaded/cached đếm occurrence; muốn số file duy nhất đếm blob/hash.
- `data/research/`: bằng chứng khảo sát và tokenizer thử nghiệm, không phải corpus production.

Không commit data. Raw text chưa lọc section nên `scope_status=requires_section_review`, `game_scope=null`; consumer không được index thẳng hoặc đổi thành base hàng loạt. Rà soát scope ở Sprint 2 phải xét cả trang, section và ảnh. Không tự suy diễn nội dung/nhân vật trong ảnh.

## Chạy lại và xử lý lỗi

Crawl so revision mới với raw đã lưu, kiểm content hash trước khi dùng cache. Ghi file atomic rồi mới chuyển sang trang tiếp theo. Image manifest ghi từng occurrence; chạy lại dùng URL cache nếu file hợp lệ, tải lại ảnh lỗi/hỏng. Caption/section được lấy lại từ raw của revision hiện tại. Job cuối có status và lỗi; dữ liệu đã lưu vẫn đọc được sau ngắt.

Nếu một URL giữ nguyên nhưng nguồn không cung cấp SHA-1, cache không chứng minh bytes từ xa chưa đổi. Muốn buộc làm mới ảnh, lưu bản sao `url-index.json` rồi bỏ entry tương ứng trước khi chạy lại. Cập nhật/xóa phiên bản đầy đủ của corpus thuộc S2/S5.

## Mở rộng

Thêm plugin triển khai `Source` trong `sources/` và cấu hình source. S1 chỉ đăng ký wikigg; module fanapis/entities của TV3 giữ nguyên. HTTP, media, artifact storage và runner tách nhau; parser/chunker thuần sẽ nằm ở `core/text/` trong S2. Hợp đồng RawPage được mô tả tại đây để review với TV3, chưa sửa toàn bộ `core/types.py` dùng chung.

Các bước filter/transform/chunk/index/update chưa được expose trong CLI; không dùng tên lệnh có vẻ hoàn chỉnh khi chưa triển khai.

## Kiểm thử

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_ingest_s1.py -q
.venv/Scripts/python.exe -m ruff check ingest tests/unit/test_ingest_s1.py
.venv/Scripts/python.exe -m ingest.debug.source_survey
.venv/Scripts/python.exe -m ingest.debug.heading_analysis --tokenizer data/research/tokenizer.json
```

Hai lệnh đầu không gọi mạng. `source_survey` gọi mạng nhưng chỉ khảo sát, không ghi bảng entities. Heading analysis đọc tokenizer JSON local của `intfloat/multilingual-e5-small`; không tải model/không gọi API AI. Report lưu SHA-256 tokenizer để tái lập.
