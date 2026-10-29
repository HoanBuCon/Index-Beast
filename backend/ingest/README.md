# Prototype ingest Sprint 1

Sprint 2 full base+SotE (ngoại lệ đã duyệt): `python -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --output-dir data/clean_runs/<ten-moi>`.
Artifact clean hiện hành: `data/clean_runs/s2-full-v2/content_clean_all.csv`; cột `decision`/`chunk_eligible`
phân biệt nội dung đủ điều kiện và review. Không gán scope base cho DLC; game_scope=elden_ring.
Xem handover 2026-10-29_s2-tv2_clean-full-base-sote.md, raw/media giữ nguyên.

S2: `python -m ingest clean --all --crawl-report <completed-report.json> --output-dir <new-dir>`
đọc inventory số trang bất kỳ, giữ nguyên chế độ mẫu mặc định. Xem handover clean-inventory.

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

Lệnh `clean` của TV2 S2 điều phối filter → transform → CSV offline như mô tả bên dưới. Lệnh chunk prototype được mô tả bên dưới; index/update chưa triển khai trong module này.

## Kiểm thử

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_ingest_s1.py -q
.venv/Scripts/python.exe -m ruff check ingest tests/unit/test_ingest_s1.py
.venv/Scripts/python.exe -m ingest.debug.source_survey
.venv/Scripts/python.exe -m ingest.debug.heading_analysis --tokenizer data/research/tokenizer.json
```

Hai lệnh đầu không gọi mạng. `source_survey` gọi mạng nhưng chỉ khảo sát, không ghi bảng entities. Heading analysis đọc tokenizer JSON local của `intfloat/multilingual-e5-small`; không tải model/không gọi API AI. Report lưu SHA-256 tokenizer để tái lập.


## Làm sạch và xuất CSV offline Sprint 2

Chạy từ backend, không cần key/email hoặc service DB cho lệnh clean:

```powershell
.venv/Scripts/python.exe -m ingest clean --limit 20 --crawl-report data/reports/crawl-adfa0d316047.json --output-dir data/clean_runs/sample-20-new
.venv/Scripts/python.exe -m ingest clean --limit 200 --crawl-report data/reports/crawl-adfa0d316047.json --output-dir data/clean_runs/sample-200-new
```

Output directory phải mới hoặc rỗng; không ghi đè raw/media/report nguồn. Không chỉ định crawl-report thì chọn report 200 trang gần nhất theo mtime. Không dùng cả 247 raw thay cho danh sách 200 ID trong report. `--limit 20` chọn cố định 20 trang đa dạng được khai báo ở transform/document.py; nếu bộ mẫu khác không có những trang đó, lệnh báo lỗi để tránh giả vờ đã kiểm tra cùng cohort. Các limit khác 1..200 lấy đầu danh sách được chỉ định.

Artifact từng bước:

- `filtered/wikigg/<id>.json` và `decisions.jsonl`: kết quả filter có section, vị trí DOM, scope/evidence và phần đã loại. Được ghi trước khi transform.
- `processed/wikigg/<id>.json`: đọc artifact filter, bổ sung metadata và image_ids; giữ cả section review/excluded cho kiểm tra.
- `lore_clean.csv`: một dòng mỗi section có căn cứ base và được giữ; `image_ids` là JSON array trong một ô.
- `review.csv`: section chưa rõ/ngoài scope và node bị loại, có lý do/vị trí nguồn. Một số bảng điều kiện được giữ nhưng đồng thời ghi note review; số dòng review không phải số section cần review.
- `images.csv`: mọi occurrence trong manifest, kể cả icon bị loại và ảnh chưa có scope rõ; không phải bảng file ảnh duy nhất.
- `report.json`: counts, rule/config hash, nguồn cohort, checksum CSV, kiểm chứng round-trip và input không đổi. Report chỉ được ghi sau khi validation thành công; thư mục có CSV nhưng thiếu report là lượt chưa nghiệm thu.
- `before-after-20.json`: dữ liệu kiểm tra trước/sau cho cohort 20 trang.

Ba CSV dùng UTF-8 BOM, quote mọi ô; nội dung nhiều dòng/dấu phẩy/dấu ngoặc kép được giữ nguyên qua csv.DictReader. ID ổn định theo source/DOM/section (occurrence ảnh thêm revision); không phụ thuộc thư mục output. Kiểm tra liên kết ảnh theo cùng source_id + revision + section, không chỉ theo hash ảnh toàn cục.

Cấu hình `[clean]` nằm trong sources.toml. `base` là phân loại heuristic có evidence từ địa danh trong lead/infobox/section, không phải xác minh thủ công mọi câu. Nội dung chứa marker DLC hoặc tên thuộc các trang explicit DLC trong scope_excluded của report được đưa vào review; heading DLC/cut content bị loại. Marker chưa đầy đủ vẫn có thể bỏ sót, phải review trước index production. Không gán base cho mọi trang trong tập mẫu.

Chỉ nhận diện in_game_text tự động khi block là bảng Dialogue. Description/quote không đủ căn cứ nguồn giữ unknown; lang unknown khi có nội dung CJK trộn. Caption không được sinh thêm. Ảnh chỉ gắn khi section khớp duy nhất; ảnh infobox giữ riêng, gallery hoặc section mơ hồ ở review. Quyền ảnh chưa rõ giữ unknown_review_required.

Hàm core/text thuần không gọi mạng. CLI clean đi vào nhánh offline trước khi tạo HTTP client. Không crawl lại, gọi LLM, chạy embedding hoặc ghi entities/PG/Qdrant.

Kiểm thử:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_cleaning_s2.py -q
```

Có regression độc lập cho các cấu trúc dễ mất nghĩa và 20 expectation từ mẫu local; các case cần raw local skip trên CI nếu dữ liệu không được cung cấp, không commit raw vào Git. Bộ test còn kiểm tra no-network, ID/hash ổn định, round-trip CSV, revision sai, ảnh gallery không gắn hàng loạt và từ chối ảnh khác trang/section.


## Chunking offline Sprint 2

Clean phiên bản s2-clean-2.0 bổ sung typed turns cho bảng hội thoại và anchor/variant context từ raw. Chạy lại clean vào thư mục mới trước khi chunk; bản CSV/processed v1 giữ nguyên để so sánh. Chunk yêu cầu tokenizer JSON local, không có cơ chế tải model hoặc tokenizer.

```powershell
.venv/Scripts/python.exe -m ingest clean --limit 20 --output-dir data/clean_runs/typed-20-new
.venv/Scripts/python.exe -m ingest chunk --input-dir data/clean_runs/typed-20-new --tokenizer "<tokenizer.json-local>" --output-dir data/chunk_runs/chunk-20-new
.venv/Scripts/python.exe -m ingest clean --limit 200 --output-dir data/clean_runs/typed-200-new
.venv/Scripts/python.exe -m ingest chunk --input-dir data/clean_runs/typed-200-new --tokenizer "<tokenizer.json-local>" --output-dir data/chunk_runs/chunk-200-new
```

Cap/overlap mặc định lấy từ [chunk] trong sources.toml (450/50), có thể override bằng --max-tokens / --overlap-tokens. Cap tính toàn bộ embedding_text gồm passage/title, section, variant, language, trigger/speaker khi có và special tokens. Encoder không được gọi trong bước này.

Prose được gom theo block nguyên vẹn trong cùng section. Section ngắn đủ nghĩa được giữ; các section khác nhau không bị ghép dựa duy nhất vào độ dài. Dialogue được chia theo các hàng th/nhóm điều kiện và nhãn English/Japanese của nguồn. Mỗi unit giữ nguyên mọi hàng gốc; speaker null nếu nguồn không cung cấp trường rõ. Title chỉ là page context, không được tự coi là xác nhận người nói.

Nếu một unit dài, chia theo đoạn/câu trước rồi mới dùng giới hạn ký tự có kiểm token thật. Các chunk giữ exact character slices và start_char/end_char trong unit. Chỉ có overlap trong cùng unit, không xuyên trigger/section. Mỗi chuỗi cuối được encode lại, không truncate âm thầm. Prefix quá dài được đưa vào review.jsonl, exit 2 để người dùng biết chưa hoàn thành.

Anchor lấy từ id của heading hoặc span.mw-headline. Nếu id heading lặp trong các tab, ưu tiên anchor panel của biến thể và giữ nhãn từ aria-labelledby/data-title. Chunk ID dựa trên section_record_id, unit, khoảng ký tự, chữ ký config/tokenizer và hash nội dung; không dùng một mình title+section làm khóa.

Artifact mới: wikigg/<doc>.jsonl, chunks.jsonl, chunks.csv UTF-8 BOM, coverage.json, review.jsonl và report.json. JSONL giữ metadata đầy đủ; CSV là bản dễ kiểm tra. image_ids chỉ kế thừa quan hệ section hợp lệ từ clean, image_association=section; không gắn ảnh của cả trang vào mọi chunk.

updated_at là thời điểm sinh artifact chunk; processed_at là thời điểm clean; fetched_at là thời điểm tải; source_updated_at còn null nếu raw chưa ghi thời điểm nguồn sửa. Không thay nguồn sửa bằng fetched_at. Do updated_at khác nhau, file hash của hai lượt có thể khác; logical_content_sha256 kiểm tính ổn định của ID/text/metadata sau khi bỏ updated_at.

Bước này chỉ chunk section scope base có căn cứ heuristic. Review/excluded được thống kê và không đưa vào chunks. Scope chưa được xác minh ngữ nghĩa toàn bộ, giấy phép ảnh chưa rõ vẫn phải review, và kết quả retrieval chưa đo. Prototype không ghi PostgreSQL/Qdrant/entities, không chạy embedding hoặc LLM.
