# TV2 — Tái tạo dữ liệu từ raw với bảng có cấu trúc

Ngày bàn giao: 09/11/2026. Phạm vi P0/P1/P2 được người dùng chốt qua 4 câu hỏi:
giữ raw/ảnh/manifest/crawl state, xóa artifact cũ, tái tạo facts/clean/chunk,
phần chưa rõ review; không crawl bổ sung, embedding/index/LLM/push.

## Kết quả thực tế

| Artifact/kiểm tra | Kết quả |
|---|---:|
| Snapshot raw nguồn | 4.164 |
| File ảnh được giữ | 10.371 |
| Bảng HTML đã hạch toán | 8.506 |
| Ô nguồn đã gán quyết định/lý do | 255.039 |
| Bảng có dữ liệu/renderer được giữ, có thể giữ một phần | 4.083 |
| Bảng review | 2.134 |
| Bảng UI/references bị loại | 2.289 |
| Fact catalog tổng | 118.498 |
| Fact được giữ theo nhãn nguồn | 70.561 |
| Fact review | 47.937 |
| Dòng content_clean.csv | 29.239 |
| Dòng content_clean_all.csv, gồm review | 30.782 |
| Dòng review nội dung/node | 38.873 |
| Occurrence ảnh trong images.csv | 65.593 |
| Chunk | 39.551 |
| Chunk EN | 34.047 |
| Unit đã phủ | 39.457/39.457 |
| Chunk infobox_stats cũ được giữ | 1.551 |
| Fact trang bị regression còn trong chunk | 15/15 |
| Fingerprint raw/media manifest/crawl state đã kiểm | 8.330 |

Bảng keep có thể chỉ giữ một số trường; không hiểu là mọi ô trong bảng đã được
nghiệm thu. Số ô keep gồm header/quote và nội dung giao cho typed parser cũ;
không bằng số fact. Số review CSV gồm cả quyết định loại node, không bằng số
section review. Có 1 trang template cố ý không có chunk; 7 lỗi media nguồn còn giữ.

## Parser và quyết định

`core/text/structured_tables.py` dựng grid theo rowspan/colspan, giữ cell gốc,
header nhiều tầng, nhãn icon alt, level/variant/affinity và row identity. Rowspan=0
theo nhóm hàng; span xung đột/vượt cấu trúc đưa review. Không sửa raw hoặc nội suy.
`table_quality.py` xử lý placeholder phân cách và chú thích note chưa giải nghĩa.
Rule/parse thuần nằm trong core; orchestration/export nằm trong ingest.

- P0: upgrade/infobox. Xử lý đủ 375 bảng upgrade nhận diện trên 159 trang, giữ
  trường có nhãn rõ, review 1.024 ô Atk chưa rõ subtype và các header trùng chưa
  tách vai trò. Không gán damage type chỉ theo màu hoặc vị trí.
- P1: catalog, recipe, shop, drop, dialogue, patch, moveset và compatibility được
  phân nhóm/hạch toán. Recipe giữ riêng Item name / # và Material name / #;
  Required/Scaling mang Attribute. Dialogue nhiều cột tách EN/JP, giữ Location/
  Condition/Speaker nếu có. Dialogue một cột dùng typed parser cũ giữ trigger.
- P2: nhóm chưa đủ schema hoặc không rõ đối tượng vẫn review. Có 1.633 bảng
  thuộc category other_unclassified trong classifier hiện tại; một số có header
  tổng quát đủ rõ để giữ từng trường, phần còn lại review. Không ép tỷ lệ keep.

Compatibility chưa đủ subject/armament không được biến thành khẳng định rằng
mọi Ash of War liệt kê đều dùng được cho vũ khí mang tên trang. Các macro/list
trong raw có thể rộng hơn nội dung trang. Row identity của recipe cũng phải lấy
từ Item name, không lấy mặc định từ title của trang.

Các nguyên nhân review ô nổi bật: 36.545 ambiguous_repeated_header,
6.613 missing_header_or_row_identity, 3.499 unclassified_table_schema,
1.024 ambiguous_attack_subtype, 214 nested_table_container, 97 grid_conflict,
129 source_placeholder, 67 decorative_source_separator, 3 unresolved_source_note,
41 missing_attribute_or_field_identity. Đây là số ô theo reason, không phải số bảng.

## Ví dụ và lỗi đã sửa qua kiểm tra

Crystal Sword: nguồn rowspan=2, Atk +0 là hai hàng 106/68, +10 là 259/166.
68/166 được giữ ở catalog Atk/review, không nằm dưới Guard Boost. Guard Boost
33/36.3 và scaling D/0.45, C/0.81 có nhãn rõ được giữ. Dòng ↑/Lv tách vai trò
growth_rate; không tự tính các level chưa có trong nguồn.

Longsword giữ riêng 13 variant, gồm Standard, Heavy, Keen, Quality, Fire,
Flame Art, Lightning, Sacred, Magic, Cold, Poison, Blood và Occult. Không gộp
thành một đường nâng cấp. Metadata level giữ chuỗi nguồn (+0, Standard +3, …),
affinity chỉ điền khi có nhãn panel nguồn; không tự gán Standard.

Spelldrake Talismans tách từng item, gồm Name/Effect/Location với PvE/PvP và +1/+2/+3
nguyên nguồn. Không còn dựa vào chuỗi bảng `Icon | Name | …` để đọc giá trị.

Qua đọc mẫu đã sửa: header Move Name lặp không còn thành fact Phase/Damage Type;
Required có Attribute đi kèm; cột # item/material không trộn; dấu `-----` review;
chú thích [note …] chưa giải nghĩa review. Phép kiểm ngôn ngữ bỏ báo nhầm ký tự
bullet `・` trong mô tả cookbook EN là chữ Nhật.

## Kiểm chứng đã chạy

- 93 unit test dữ liệu đạt; 20 skip do bộ fixture/report 200 trang cũ đã xóa theo
  yêu cầu. 37 test chọn cho clean/table/chunk/stats đạt. Chưa chạy toàn backend suite.
- Ruff check/format và git diff --check đạt. Không thêm dependency/model mới.
- DictReader kiểm BOM, đủ cột, Unicode, dấu quote/newline; round-trip của các CSV
  được exporter đối chiếu nội dung. facts_clean chỉ có keep; content_clean chỉ có
  keep + chunk_eligible=True.
- Mỗi fact đối chiếu raw_cell_text và column_index với cell trong inventory;
  ID table/fact không trùng. 45.204 fact được chunk trỏ trực tiếp bằng fact_ids.
  Nhiều fact infobox còn biểu diễn trong chunk infobox_stats cũ, không có fact_ids
  trực tiếp; kiểm riêng 1.551 context và 15 ca baseline để tránh mất nội dung.
- Source coverage/slices, ID/hash, prefix/token theo tokenizer E5 local kiểm toàn
  bộ, lỗi 0; max token 450, max overlap 50. Không cắt hàng bảng giữa nhãn và số.
- Sample 20 trang chạy lại có ID/text/metadata chunk khớp full run khi bỏ updated_at.
- Load validate-only: 4.164 document / 39.551 chunk; database writes 0.
- Đọc 50 fact có chủ đích theo nhóm: 38 đúng cấu trúc/nhãn nguồn, 10 được quarantine
  đúng, 2 cần xem thêm applicability vì recipe item khác title trang. Review do
  assistant, human_approved=false; không dùng làm accuracy toàn corpus.

## Coverage còn thiếu và giới hạn

486 trang ứng viên equipment theo type infobox: 159 có bảng upgrade nhận diện,
327 chưa thấy trong snapshot. Đây là heuristic, không kết luận 327 trang crawl lỗi
hoặc live wiki không có dữ liệu. Không crawl lại hoặc bổ sung số liệu từ trí nhớ.

Keep chỉ chứng minh dữ liệu có nhãn/vị trí nguồn đủ để biểu diễn theo rule hiện tại,
không chứng nhận mọi nội dung wiki đúng về ngữ nghĩa, mọi patch hiện hành hoặc
mọi câu trả lời RAG. Một số header/tooltip/nested layout và compatibility chưa đủ
căn cứ vẫn review; damage_type có thể null, giá trị vẫn giữ trong stat_name nguồn.
source_updated_at/spoiler_level chưa có; fetched_at không thay thế patch timestamp.
Short/duplicate bodies được giữ nếu khác row/variant/source, không dedup số liệu toàn wiki.

Ảnh giữ file và manifest gốc; không tự sinh caption, không gắn toàn bộ ảnh trang
vào mọi row. License chưa rõ và 7 lỗi media vẫn cần review; chưa đánh giá multimodal RAG.
TV3 cần thử truy xuất có filter row subject/level/affinity và kiểm evidence/abstention
trong bước riêng; TV1 cần tích hợp version mới vào runner nếu nhóm duyệt.

## Artifact và cách chạy

Điểm vào local: `backend/data/delivery/final/README.md` và manifest.json.
Facts dùng `facts/facts_clean.jsonl` hoặc CSV; `facts/table_facts.*` là catalog có
cả review. Clean dùng `clean/content_clean.csv`; chunk dùng `chunk/chunks.jsonl`.
`report/verification.json`, `structured-structure.json`, sample50, coverage và
cleanup.json lưu kiểm chứng. Manifest bàn giao hash 28 artifact.

Các thư mục con final là Windows junction, không phải gói copy portable. Khi chuyển
máy phải copy đích vật lý và tạo lại junction. Data bị Git ignore, chưa upload GitHub.
Đã reset clean/chunk/report cũ, sau nghiệm thu xóa tiếp 15 thư mục chạy thử trung gian;
chỉ một clean_runs/structured-release và chunk_runs/structured-release còn lại.
Giữ local-setup vì là cấu hình khôi phục môi trường, không phải corpus cũ.

CLI đầy đủ ở `backend/ingest/README.md`; hai lệnh chính từ backend, chọn output mới:

```powershell
.venv/Scripts/python.exe -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --gameplay --structured-tables --output-dir data/clean_runs/<new>
.venv/Scripts/python.exe -m ingest.chunk.full --input-dir data/clean_runs/<new> --tokenizer <tokenizer.json-local> --output-dir data/chunk_runs/<new>
```

Script reset/publish là thao tác dữ liệu có xóa, chỉ chạy khi được ủy quyền, không
đưa vào CI hoặc dùng như lệnh test. Lượt này không chạy encoder, API, LLM, index,
không thay PostgreSQL/Qdrant, không commit/push/merge; chi phí API 0 USD.
