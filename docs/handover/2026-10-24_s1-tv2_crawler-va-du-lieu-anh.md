# Bàn giao Sprint 1 TV2 crawler và dữ liệu ảnh

Ngày bàn giao: 24/10/2026. Người thực hiện: TV2 (UncleThing). Nhánh: `feature/s1-tv2-crawler-va-du-lieu-anh`. Commit crawler gốc `4da2e35` được chuyển sang nhánh mới thành `9487bbf`, tách từ origin/develop; phần sửa và tài liệu bàn giao được commit riêng trên cùng nhánh. Chưa merge vào develop; Mentor review và CI là điều kiện tích hợp theo quy ước nhóm.

## Phạm vi và kết quả

Ba thẻ TV2 S1: khảo sát nguồn, prototype crawler wiki.gg, ADR-003. Phần ảnh là mở rộng đã được TV2 duyệt và đã ghi ở planning/sprint_plan.json; 10 story point gốc chưa định lượng thêm công sức ảnh. Không triển khai embedding, retrieval, LLM, bảng entities của TV3 hoặc schema/hạ tầng của TV1.

- Tập mẫu có **200 trang duy nhất**, đủ 200 manifest.
- **1188 blob ảnh duy nhất**, 1,667,412,119 byte (khoảng 1,67 GB), trong tập mẫu sau loại icon giao diện.
- Checksum raw/ảnh và revision manifest đều kiểm tra đạt; `s1-acceptance.json` không có lỗi.
- Phân tích heading/token trên 20 trang; ADR đề xuất giới hạn tổng 450 token, overlap 50, chờ review TV3/Mentor.
- Kiểm tra trực quan 20 ảnh đại diện và quan hệ ảnh–trang–section; giữ caption/alt từ nguồn, không tự sinh.
- Kiểm thử backend: 79 passed, 1 integration test deselected; ruff check/format đạt cho ingest và test mới. Chưa chạy integration service/PostgreSQL vì phần S1 này không cần hạ tầng.

Lượt crawl gốc `crawl-2301a25ddbc1` đạt 200 trang, mất 1.439,047 giây (~24 phút), 1.391 request, loại 51 ứng viên theo namespace/redirect/scope và có một ảnh lỗi MIME. Report gốc được giữ nguyên trạng thái partial. Lượt sửa `crawl-212327e00883` tải thành công ảnh đó; audit acceptance kiểm tra artifact hiện tại trên đúng 200 page ID của lượt gốc. Không sửa report lịch sử thành thành công giả.

Số downloaded/cached trong report crawl đếm occurrence ở từng trang, không phải số file duy nhất. Các nhóm category có giao nhau. Dữ liệu của lượt thử trước vẫn được giữ, nên toàn thư mục raw/blobs có thể nhiều hơn tập mẫu được bàn giao; dùng danh sách `pages` trong report gốc để xác định tập 200.

## Trạng thái nghiệm thu từng phần

| Mục | Trạng thái và bằng chứng |
|---|---|
| Category và phân trang | Đã chạy, 2.602 ứng viên; categories.json ghi direct counts, union và độ sâu 1 |
| MediaWiki query/parse/imageinfo | Đã kiểm chứng trực tiếp, lưu HTML và revid cùng response |
| Dump | Special:RequestDump đọc được; current/full history đều chưa được tạo |
| fanapis | 7 resource, mỗi resource thử page 0/1, limit 2; chỉ khảo sát |
| So sánh 10 trang Fandom | **Chưa hoàn thành nội dung**: cả 10 bị dừng ở robots.txt HTTP 403; có URL và log |
| 200 trang và ảnh | Đủ tập mẫu, audit đạt; phạm vi section vẫn cần rà soát ở S2 |
| ADR-003 | Đã có dữ liệu 20 trang và đề xuất; **chờ review/chấp nhận** |
| Git/CI/Mentor | Chuẩn bị được mã và kiểm thử local; chưa có xác nhận CI/Mentor hoặc merge |

Vì vậy chưa đánh dấu cả Sprint 1 của TV2 là Done. Phần Fandom cần truy cập hợp lệ trở lại hoặc quyết định của team về chấp nhận giới hạn khảo sát; không đổi mục tiêu kế hoạch ngầm. TV2 có thể đóng phần prototype sau review, không cần đợi TV3 triển khai RAG ảnh.

## Cách chạy

Từ `backend/`, dùng Python trong venv; trên Linux thay `.venv/Scripts/python.exe` bằng `.venv/bin/python`:

```powershell
.venv/Scripts/python.exe -m ingest crawl --dry-run
.venv/Scripts/python.exe -m ingest survey
.venv/Scripts/python.exe -m ingest crawl --limit 200
.venv/Scripts/python.exe -m ingest crawl --page "Ranni the Witch"
.venv/Scripts/python.exe -m ingest.debug.heading_analysis --tokenizer data/research/tokenizer.json
.venv/Scripts/python.exe -m ingest.debug.audit_s1 --crawl-report data/reports/crawl-2301a25ddbc1.json
```

Cấu hình liên hệ `INGEST_CONTACT_EMAIL` đặt ở .env gốc repo (không commit, không ghi trong report). Nguồn và giới hạn ở ingest/config/sources.toml. Không chạy đồng thời hai CLI trên cùng data directory. Không cần API AI hoặc các service DB/vector để chạy prototype. Đọc ingest/README.md để biết cache, exit code và giới hạn.

## Vị trí bàn giao

- `backend/ingest/`: source interface, client, crawler, image store, CLI, công cụ khảo sát/đo/audit.
- `backend/data/raw/wikigg/`: raw JSON gồm HTML, revision, category, hash và URL.
- `backend/data/media/blobs/`: ảnh theo hash, tránh lưu nhiều bản cùng nội dung.
- `backend/data/media/manifests/wikigg/`: quan hệ page/revision/section với ảnh, caption/alt và quyền nguồn.
- `backend/data/reports/`: categories, source-probe, source-survey, crawl jobs, s1-acceptance, heading-analysis, media-review-20.
- `docs/data-sources.md`, `docs/adr/003-chunking.md`: khảo sát và đề xuất chunk.
- `planning/sprint_plan.json` là nguồn kế hoạch; docs/03_SPRINT_PLAN.md đã sinh đồng bộ bằng generator. Các bản Word export hiện vẫn là snapshot trước thay đổi và cần tái sinh khi team xuất tài liệu; không dùng chúng làm nguồn kế hoạch.

Dữ liệu raw/ảnh, tokenizer và báo cáo local nằm ngoài Git theo .gitignore. Khi TV3 cần dùng trên máy khác, chuyển tập artifact và kiểm checksum; không đẩy 1,67 GB ảnh vào Git. Hiện chưa đưa bộ mẫu vào dịch vụ lưu trữ bên ngoài.

## Quy tắc và điểm mở rộng

Mỗi nguồn triển khai `Source`. Mở rộng nguồn và cấu hình mà không ghép nghiệp vụ vào API online. Raw và media được lưu độc lập để S2 làm sạch/chunk lại mà không tải lại dữ liệu. Contract raw được mô tả trong ingest/README.md để review TV3; chưa thay toàn bộ core/types.py dùng chung.

Ảnh được nhận diện bằng bytes qua Pillow, đặt đuôi theo định dạng thực. MIME header sai được giữ ở declared_mime/mime_mismatch. Section của ảnh infobox là Infobox; caption trống được để trống. Một blob có thể có nhiều occurrence, mỗi occurrence giữ riêng ngữ cảnh nguồn.

## Sự cố và xử lý

- Brotli decoder lỗi trong môi trường: client yêu cầu Accept-Encoding identity.
- Một số query oldid gặp HTTP 403: prototype parse theo title, ghi revision thực tế cùng HTML; không vượt chặn.
- Category chung có lẫn DLC: bổ sung heuristic lead/infobox, giữ raw ngoài phạm vi với lý do và không đếm vào mẫu. Đây không thay thế rà soát toàn bộ section.
- File BlaiddWailingDunes.webp được server khai báo WebP nhưng bytes PNG: xác minh bằng Pillow, lưu .png và MIME thực, lưu dấu vết header.
- Ảnh rating giao diện 45px lọt ngưỡng kích thước ban đầu: thêm quy tắc riêng và kiểm thử; tính lại context trên raw, không tải lại ảnh.
- Fandom robots 403: dừng và ghi lỗi, không dùng proxy hoặc suy đoán nội dung.

## Việc còn lại và bàn giao đúng vai trò

1. TV2/TV3/Mentor review RawPage contract và ADR-003; ADR vẫn ở Proposed cho đến lúc chấp nhận.
2. Hoàn thành hoặc xin team ghi nhận giới hạn mục đối chiếu Fandom; chưa tick Done.
3. Rà soát section base game/DLC và lọc/chuẩn hóa lore trong S2. Raw hiện `game_scope=null`, `requires_section_review`; không gán base hàng loạt.
4. Toàn bộ 1.328 occurrence ảnh được giữ trong mẫu hiện thiếu thông tin giấy phép ở extmetadata; giữ unknown_review_required, cần rà soát trang File trước tái phân phối. TV4 nhận metadata attribution; không suy giấy phép ảnh từ footer bài viết.
5. TV3 thực hiện fanapis entities, embedding/indexing và quyết định RAG ảnh. TV2 chỉ cung cấp blob/manifest và quan hệ với section.
6. TV1 cung cấp schema PG/migrations; TV2 nối ingestion_jobs vào DB ở S2. Job file ở S1 chưa hoàn thành toàn bộ FR-ING-10.
7. Cập nhật tăng dần/xóa artifact và xóa chunk của trang bị xóa thuộc các sprint sau; prototype hiện kiểm revision/hash và dùng lại cache.
