# Ingest

## Chạy nhanh: `scripts/data_pipeline.py`

Một lệnh cho mỗi bước, gọi lại đúng các CLI bên dưới với mặc định an toàn. Chạy từ `backend/`
(Windows: `.venv\Scripts\python`; Linux/Docker: `python`), hoặc từ gốc repo bằng `make data STEP=<bước>`:

| Lệnh | Việc làm |
|---|---|
| `python -m scripts.data_pipeline status` | Bản crawl, clean, chunk mới nhất (chỉ tính lượt chạy đủ toàn bộ trang) |
| `python -m scripts.data_pipeline crawl` | Resume lượt crawl `s2-full-20261028` (gọi mạng, rất lâu; cần `INGEST_CONTACT_EMAIL`) |
| `python -m scripts.data_pipeline clean` | Clean toàn bộ raw vào `data/clean_runs/clean-<thời-gian>` |
| `python -m scripts.data_pipeline chunk` | Chunk bản clean mới nhất vào `data/chunk_runs/chunk-<thời-gian>`; tự tìm tokenizer E5 trong `models/` |
| `python -m scripts.data_pipeline load` | Kiểm tra rồi nạp chunk mới nhất vào PostgreSQL (`--validate-only` để chỉ kiểm) |
| `python -m scripts.data_pipeline index --dry-run` | Kiểm tra chunk trước khi index, không tải model |
| `python -m scripts.data_pipeline index --collection lore_chunks_v2` | Embedding và ghi Qdrant (lâu, CPU); bắt buộc chỉ định collection |
| `python -m scripts.data_pipeline all` | clean → chunk → load → index `--dry-run` |

Mọi bước nhận `--input` (chọn bản khác bản mới nhất) và `--output` (đặt tên thư mục). Đầu ra luôn là thư mục mới,
không ghi đè bản đang phục vụ. Index vào collection mới rồi mới đổi `RAG_COLLECTION`, vì index đè không xóa point cũ.

# Prototype ingest Sprint 1

Sprint 2 full base+SotE (người dùng duyệt): dùng `python -m ingest.chunk.full --input-dir data/clean_runs/s2-full-v2 --tokenizer <local-tokenizer.json> --output-dir data/chunk_runs/<ten-moi>`.
Nạp PostgreSQL bằng `python -m ingest.chunk.load_full data/chunk_runs/s2-full-v1` (thêm `--validate-only` để kiểm offline).
game_scope=elden_ring; không thêm passage prefix lần hai khi index DB chunks.text. Xem handover
2026-10-29_s2-tv2_chunk-full-base-sote.md. Các lệnh prototype dưới vẫn là chế độ cũ cho mẫu base-only.
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

## S3: bản thử chất lượng full corpus, bật rõ gameplay

Phần prototype 200 trang phía trên giữ policy riêng. Với full cohort base + SotE
đã được duyệt, `ingest.transform.full --gameplay` bật policy `s3-full-clean-1.2`:
giữ thông số infobox có nhãn, gameplay prose và nguồn ngôn ngữ theo tab. Không có
flag này vẫn dùng policy S2. Không tự đưa trial S3 vào runner/manifest chính thức.

Chạy từ `backend`, dùng output mới và tokenizer/model local đã chuẩn bị:

```powershell
$modelCache = Join-Path $env:USERPROFILE '.cache/huggingface/hub/models--intfloat--multilingual-e5-small/snapshots/614241f622f53c4eeff9890bdc4f31cfecc418b3'
$tokenizerPath = Join-Path $modelCache 'tokenizer.json'
.venv/Scripts/python.exe -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --gameplay --limit 20 --output-dir data/clean_runs/s3-new-20
.venv/Scripts/python.exe -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --gameplay --output-dir data/clean_runs/s3-new-full
.venv/Scripts/python.exe -m ingest.chunk.full --input-dir data/clean_runs/s3-new-full --tokenizer $tokenizerPath --output-dir data/chunk_runs/s3-new-full
.venv/Scripts/python.exe -m ingest.chunk.load_full data/chunk_runs/s3-new-full --validate-only
.venv/Scripts/python.exe -m ingest index --input data/chunk_runs/s3-new-full/chunks.jsonl --policy pilot --languages en --tokenizer $tokenizerPath --dry-run
```

Chunk S3 version `s3-full-chunk-1.3` giữ infobox vừa cap trong cùng unit, lặp
header khi phải chia bảng dài, max 450/overlap 50. Giữ exact offsets và provenance.
CSV dùng UTF-8 BOM; JSONL có `content_type`, `table_header`, `language_evidence`.
Các lệnh trên không chạy encoder hoặc ghi DB. Không bỏ `--validate-only`/`--dry-run`
khi chỉ muốn kiểm offline. `scripts/data_pipeline.py` thuộc TV1 hiện nhận prefix
S2; tích hợp version S3 cần review riêng.

Đánh giá local dưới đây chỉ chạy khi người dùng cho phép embedding. Cần weights
ONNX local đúng revision; script không tự tải model và không gọi LLM:

```powershell
.venv/Scripts/python.exe -m ingest.debug.readiness_structure --chunks data/chunk_runs/s3-new-full --clean data/clean_runs/s3-new-full --tokenizer $tokenizerPath --output data/research_runs/s3-rag-readiness-20261108 --name rerun
.venv/Scripts/python.exe -m ingest.debug.readiness_retrieval evaluate --artifact data/chunk_runs/s3-new-full/chunks.jsonl --model-path $modelCache --output data/research_runs/s3-rag-readiness-20261108 --name rerun
```

Thư mục research phải có protocol đã đóng băng từ lượt đầu. Để tạo diagnostic
mới: `python -m ingest.debug.readiness_retrieval prepare --output
data/research_runs/<thu-muc-moi>`; sau đó evaluate before/after trong cùng thư mục.
Sau khi dọn dữ liệu cũ theo yêu cầu, prepare mặc định dùng inventory tại
`data/delivery/final/chunk/documents.jsonl`. Dùng `--baseline-documents <path>`
để chọn baseline khác; file chunks.jsonl phải nằm cùng thư mục inventory. Cần tạo
thư mục output trước. Protocol đã đóng băng trước đây giữ nguyên, không prepare lại.
Không sửa protocol sau khi xem kết quả. Review 50 mẫu do assistant chưa thay cho
human gold. Xem [báo cáo và giới hạn](../../docs/testing/2026-11-08_tv2-rag-readiness.md)
và điểm vào dữ liệu local `data/delivery/final/manifest.json`.

### CSV sạch và bảng cần review

Từ S3 clean 1.2, dùng **`content_clean.csv`** cho nội dung được giữ (`decision=keep`,
`chunk_eligible=True`). `content_clean_all.csv` là catalog đối soát chứa cả review,
không đưa nguyên file này vào embedding. `review.csv` giữ nội dung chưa đủ cấu
trúc kèm lý do, source snapshot và DOM locator; raw không bị sửa.

Bảng quest item có ô nhắc tới “dialogue” không được coi là hội thoại. Bảng hội
thoại nhiều cột chưa được parser tách rõ vai trò đưa review với lý do
`unresolved_multicolumn_dialogue`. Không lọc theo dấu `|` chung: giữ bảng chỉ số
đã gắn nhãn và hội thoại một cột có trigger. Khi bổ sung parser nhiều cột, có thể
khôi phục nội dung từ review/raw thay vì crawl lại.

## S3: tái tạo với bảng có cấu trúc (P0/P1/P2 đã được duyệt)

Người dùng chốt giữ raw/ảnh/crawl state, dọn artifact cũ và tái tạo offline toàn
bộ phạm vi P0/P1/P2. Bật cả `--gameplay --structured-tables`; không có flag mới
thì cleaner vẫn dùng policy cũ. Policy mới `s3-full-clean-2.0`, chunk `s3-full-chunk-2.0`.

```powershell
# Từ backend, tokenizer local như các lệnh phía trên. Chọn output mới.
.venv/Scripts/python.exe -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --gameplay --structured-tables --output-dir data/clean_runs/<new>
.venv/Scripts/python.exe -m ingest.chunk.full --input-dir data/clean_runs/<new> --tokenizer $tokenizerPath --output-dir data/chunk_runs/<new>
.venv/Scripts/python.exe -m ingest.chunk.load_full data/chunk_runs/<new> --validate-only
```

Thêm `--sample-ids 363,52,...` để thử các source ID có trong cohort. Danh sách mẫu
20 trang đã kiểm tại `docs/testing/2026-11-08_structured-sample20.json` từ root repo.
Chạy `ingest.debug.verify_structured --help` và `ingest.debug.readiness_structure --help`
để kiểm artifact offline; không gọi encoder. `reset_derived.ps1` là thao tác xóa
artifact chỉ chạy khi được ủy quyền rõ ràng; không chạy như bước kiểm tra thông thường.

Trong clean output:

- `content_clean.csv`: chỉ dòng keep, dùng chuẩn bị RAG; `content_clean_all.csv`
  là catalog gồm cả review, không đưa nguyên vào embedding.
- `tables/tables_inventory.jsonl`: mọi bảng/cell nguồn, span, header, tri-state và lý do.
- `tables/table_facts.jsonl` và `.csv`: giữ cả fact keep và review, phải lọc
  `decision=keep` khi sử dụng. Mỗi fact có source/revision/snapshot/hash,
  table/row/cell ID, row_key, raw value, stat_name, grade/coefficient nếu tách rõ,
  level và affinity có căn cứ; metadata không rõ giữ null/unknown. CSV null là ô rỗng.
- `tables/tables_review.csv` và `.jsonl`: ô review hoặc excluded, giữ text và DOM.
- `tables/facts_clean.jsonl` và `.csv`: chỉ fact keep, đây là file facts bàn giao
  để chuẩn bị RAG. Nhãn keep là xác nhận cấu trúc theo nguồn/rule, chưa phải human gold.
- `images.csv`: manifest ảnh hiện có; không tự sinh caption hoặc nối ảnh không rõ.

Grid mở rộng ô gộp nhưng mọi giá trị vẫn trỏ ô gốc; xung đột/nested container hoặc
cột lặp chưa rõ đưa review. Parser dùng header nhiều tầng, source icon alt khi
header là icon, tên item/material và điều kiện để giữ đúng vai trò. Không dùng
màu sắc để tự gán damage type, không nội suy /Lv, không đổi dấu '-' thành số 0.
Thư viện hiện tại được dùng lại, không cần model/API mới.

Hội thoại một cột tiếp tục dùng typed parser cũ để giữ trigger/speaker; bảng nhiều
cột tách locale khi có nhãn rõ. Bảng quote giữ nội dung nguồn. Các định dạng còn
chưa hiểu trong P1/P2 được hạch toán review, không ép mọi bảng thành fact sạch.
Số ô keep có cả header/quote và nội dung giao cho parser cũ, không bằng số fact.

Chunk table_fact nguyên theo hàng, mang Row/Variant/title/section và fact_ids.
Hàng quá dài chuyển review, không cắt giữa nhãn và số. Những fact infobox đã giữ
có thể được biểu diễn bởi chunk infobox_stats cũ nên không phải mọi fact keep đều
có fact_id trực tiếp trong chunk; kiểm cả provenance và stats regression.
Chưa tích hợp runner TV1 tự nhận version mới, chưa embedding/index/LLM/push.
