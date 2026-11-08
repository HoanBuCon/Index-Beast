# Đề xuất xử lý bảng raw cho RAG — chờ người dùng duyệt

Cập nhật 09/11/2026: người dùng đã chốt qua 4 câu hỏi và cho thực hiện toàn bộ
P0/P1/P2, giữ raw/ảnh/crawl state, dọn artifact cũ và tái tạo offline. Phần “chờ
duyệt” bên dưới ghi lại thời điểm khảo sát; phạm vi mới ở meta prompts
`docs/prompts/2026-11-08_tv2-rebuild-structured-tables.md`.

Ngày 08/11/2026, TV2. Người dùng chỉ yêu cầu khảo sát toàn bộ raw và lập đề xuất;
**chưa cho chạy parser chuyển đổi mới, clean, chunk, embedding, index hoặc xóa dữ liệu**.
Lượt này chỉ đọc snapshot và artifact hiện tại, ghi báo cáo khảo sát riêng.

## 1. Khảo sát thực tế

Đọc đủ 4.164 snapshot theo bộ cuối, kiểm content_hash và fingerprint file trước/sau.
Không có lỗi đọc hoặc thiếu article body. Có 8.506 bảng HTML tổng cộng; 1.746 bảng
được heuristic nhận diện UI/ngoài article; 6.760 bảng còn lại nằm trên 2.843 trang.
Đây là số bảng cấu trúc, chưa phải số bảng có thể nghiệm thu về ngữ nghĩa.

| Nhóm nhận diện | Bảng | Trang |
|---|---:|---:|
| Infobox | 2.391 | 1.679 |
| Nâng cấp/chỉ số theo level | 375 | 159 |
| Hội thoại | 185 | 96 |
| Danh mục item, effect/location | 180 | 165 |
| Công thức crafting | 259 | 259 |
| Shop/đổi vật phẩm | 127 | 66 |
| Drop rate | 197 | 139 |
| Affinity/compatibility | 45 | 45 |
| Chỉ số/combat khác | 145 | 96 |
| Loadout/moves | 155 | 117 |
| Lịch sử patch | 384 | 381 |
| Bảng bố cục quote | 246 | 243 |
| References/citations | 543 | 543 |
| Rỗng/bố cục media nhận diện được | 1 | 1 |
| Chưa đủ căn cứ phân loại | 1.527 | 895 |

Phân nhóm loại trừ nhau theo thứ tự ưu tiên của script, nhưng số trang giữa các
nhóm giao nhau. Không cộng số trang để suy ra coverage toàn bộ trang.
Lxml được dùng để khảo sát nhanh; cleaner BeautifulSoup hiện tại không đổi.

Các dấu hiệu rủi ro trên 6.760 bảng article:

| Dấu hiệu | Bảng | Trang |
|---|---:|---:|
| Có ô gộp hàng/cột | 4.044 | — |
| Rowspan | 1.331 | 879 |
| Colspan | 3.526 | 2.004 |
| Có xuống dòng/block trong ô | 3.951 | 2.222 |
| Có nhiều số trong một ô | 1.082 | 880 |
| Có inline color | 624 | 368 |
| Cặp grade + coefficient, ví dụ D 0.45 | 256 | 40 |
| Dòng tăng trưởng /Lv hoặc per level | 260 | 44 |
| Placeholder ?, TBA/TBD/Unknown | 65 | 59 |
| Có CJK | 94 | 91 |
| Chứa bảng lồng | 108 | 107 |

Các dấu hiệu giao nhau, không cộng lại. Màu sắc và nhiều số là tín hiệu khảo sát,
không tự chứng minh bảng bị lỗi hoặc xác định loại damage. Bảng quote và icon
thuộc media không được tự coi là rác chỉ vì định dạng bố cục.

Trong nhóm nâng cấp, hai header phổ biến là:

- 169 bảng `Level | Atk | STR Scaling ... | Grd Boost`.
- 85 bảng tương tự có thêm Passive Effects.
- Các biến thể còn lại dùng Attack Power / Attribute Scaling / Guarded Damage
  Negation, header nhiều tầng hoặc bảng chứa bảng. Không dùng một regex cho cả nhóm.

Đối chiếu dữ liệu hiện tại: đúng 159 source_id của 375 bảng nâng cấp đều xuất hiện
ở review.csv: 305 dòng review/unclassified_structure và 70 dòng bị loại bởi
numeric_stats_table. Không có cơ sở nói RAG hiện đã bao phủ bảng nâng cấp.
Các prose nói về Level/Scaling vẫn có thể hữu ích, không xóa theo từ khóa này.

## 2. Ví dụ và giới hạn nguồn

Crystal Sword, source_id 363, revision 85144: bảng dùng rowspan=2. Ở +0, Atk
có hai hàng 106 và 68; Guard Boost là 33. Ở +10, Atk có 259 và 166; Guard Boost
là 36.3. STR có grade/coefficient D/0.45 hoặc C/0.81 trong cùng ô. Nối bằng text
làm 68/166 có vẻ thuộc cột Guard Boost. Đây là lỗi mất quan hệ ô, không phải rác.
Chưa đủ căn cứ từ vị trí/màu đơn thuần để tự đặt tên loại damage cho hai hàng Atk.

Longsword có 13 bảng nâng cấp được nhận diện trong raw, cho thấy cần giữ variant/
affinity; không gộp tất cả thành một đường nâng cấp. Spelldrake Talismans có bảng
effect/location hữu ích, cần tách từng item/version, không xóa toàn bộ vì header Icon.
Stranded Souls và Finger Reader Crone cần parser dialogue nhiều cột riêng.

Snapshot Moonveil, Uchigatana và Blasphemous Blade hiện không có heading Upgrade
Information hoặc bảng nâng cấp nhận diện được. Khảo sát coverage theo type infobox
lưu riêng tại equipment-coverage.json; là heuristic, chưa phải danh sách trang bị
được xác minh thủ công. Không thể khôi phục giá trị không có trong raw bằng cleaner.
Heuristic theo type infobox ghi nhận 486 trang ứng viên vũ khí/shield/staff/seal:
159 có bảng nâng cấp nhận diện được, 327 chưa thấy trong snapshot. Không xem 327
là số trang crawl lỗi: có thể trang/revision nguồn không chứa bảng, thuộc loại
không cần đường nâng cấp tương ứng hoặc thông tin được trình bày khác schema.
Chưa crawl bổ sung; nếu cần, trình duyệt kế hoạch thu thập riêng sau khi phân biệt
trang nguồn thiếu thông tin với crawler bỏ sót nội dung.

## 3. Quy tắc đề xuất

**Giữ và chuẩn hóa** bảng có thông tin truy xuất được: chỉ số, nâng cấp, effect,
drop, crafting, shop, compatibility, dialogue và quote có nguồn. **Loại khỏi text
RAG** phần UI/nav/edit/backlink và placeholder biên tập có bằng chứng. **Review**
những hàng/ô hoặc bảng chưa xác định được cột, variant, đơn vị, phiên bản hoặc nguồn.
Không xóa hàng loạt table/infobox, không coi mọi dấu | là lỗi và không gán số còn thiếu.

1. Filter nhận diện bảng và ngữ cảnh: title, section, tab, affinity, level, patch,
   ngôn ngữ; quyết định keep/review/excluded kèm lý do và XPath/DOM. Giữ raw nguyên vẹn.
2. Transform mở rộng grid rowspan/colspan có kiểm tra xung đột, kể cả rowspan=0
   nếu gặp; mỗi ô lặp vẫn trỏ về cùng ô gốc. Giữ header nhiều tầng, cell raw text,
   chú thích, icon title/alt, màu/class và nguồn legend trước khi chuẩn hóa số.
3. Parser theo schema tách grade/coefficient và nhóm attack/guard/resistance.
   `0` là giá trị; `-` không được tự đổi thành 0. `↑/Lv` là dòng quy tắc riêng,
   không nội suy mức chưa có trong bảng. Có nhiều số trong ô phải có nhãn/vai trò
   nguồn mới tách nghĩa; chưa rõ giữ review, không đưa chuỗi nhập nhằng vào clean.
4. Đọc nhãn/legend/link/attribute để xác định loại damage. Không hardcode cyan=magic
   hoặc suy luận theo thứ tự từ kiến thức game. Không có căn cứ thì damage_type
   unknown và đánh review cho yêu cầu cần loại damage đó.
5. Giữ điều kiện/speaker/ngôn ngữ khi tách dialogue, quantity/material khi tách
   crafting, PvE/PvP và biến thể +1/+2/+3 khi tách effect. Không tách số khỏi điều kiện.
6. Khử trùng chỉ khi cùng context và có bằng chứng là bản hiển thị trùng; giữ
   khác biệt level/affinity/patch/locale. Không dedup toàn corpus theo câu hay số.

## 4. Artifact và chunk đề xuất

TV2 xuất artifact offline riêng, không đổi schema PG/entities hoặc runtime TV3:

- `tables_inventory.jsonl`: provenance, cấu trúc gốc, loại và quyết định.
- `table_facts.jsonl` và CSV tương ứng: table_id/row_id, source_id/title/revision,
  source_snapshot, section/DOM, table_type, item/variant/affinity/level, stat_name,
  damage_type nếu có căn cứ, grade/coefficient/value/unit, raw_cell_text,
  source_cell, language, quality_status, reason, parser_version.
- `tables_review.csv`: bất định, placeholder, ô ghép xung đột, thiếu legend;
  giữ nội dung và vị trí nguồn. Không ghi đè review/data hiện tại.
- `content_clean.csv` và chunk từ facts đã đủ căn cứ, kèm chỉ số coverage.

Một chunk gom theo item + affinity + level + nhóm chỉ số. Giữ nguyên nhãn trong
embedding_text, lặp context khi chia nhóm, giới hạn 450 token/overlap tối đa 50
theo tokenizer local. Không cắt ở giữa hàng hoặc giữa nhãn và số. Dòng quá dài
chia theo nhóm chỉ số có tên đầy đủ; còn bất định phải review trước chunk.
Không dùng bảng Markdown thô hoặc chuỗi nối bằng | làm định dạng chuẩn cuối.

TV3 chỉ nhận đề xuất dùng entity/level/affinity metadata để tìm đúng fact và dẫn
nguồn; vector score không được coi là bằng chứng số liệu. Thiết kế lookup chính
xác/collection/index thuộc TV3/TV1, không tự triển khai trong phần việc TV2.

## 5. Lộ trình xin duyệt

Ước lượng 2–3 ngày làm việc cho P0 và nghiệm thu nội bộ nếu không phát hiện thêm
schema lớn. Đây là ước lượng triển khai, không phải cam kết phục hồi đủ mọi item.

| Bước | Nội dung | Điều kiện chuyển bước |
|---|---|---|
| P0.1, khoảng nửa ngày | Đóng schema + fixture khoảng 20 bảng thuộc các họ header, Crystal Sword, Longsword, infobox, catalog, dialogue | Duyệt cách biểu diễn ô và giá trị chưa rõ |
| P0.2, khoảng một ngày | Grid parser + parser nâng cấp/infobox, rules review, artifact thử | Không shift cột, không đoán đơn vị/loại damage, giữ provenance |
| P0.3, khoảng nửa đến một ngày | Chạy thử fixture rồi toàn bộ nhóm 375 bảng nâng cấp; xuất bản thử clean/chunk và report | 100% bảng được hạch toán keep/review/excluded; ô chưa rõ không vào clean |
| P1, duyệt riêng | Catalog/effect, crafting/shop/drop, compatibility, dialogue, patch | Schema/test theo từng nhóm, không mở đồng loạt |
| P2, duyệt riêng | Xử lý 1.527 bảng chưa phân loại, xem thiếu raw và đề xuất crawl bổ sung | Có evidence và phạm vi thu thập rõ |

Không gọi API AI hoặc chạy encoder để parse bảng. Chi phí API cho P0 dự kiến 0.
Giữ phạm vi base + SotE đã duyệt. Không auto re-index, deploy, merge hay xóa corpus.

## 6. Tiêu chí nghiệm thu đề xuất

- Fixture có rowspan/colspan, header nhiều tầng, nested table, grade/coefficient,
  passive effects, growth rate, màu/legend, số 0, dấu -, placeholder và CJK.
- Crystal Sword bắt buộc ghép 68/166 về cột Atk, không nhầm sang Grd Boost;
  không đặt tên loại damage khi chưa chứng minh bằng raw.
- Longsword giữ riêng 13 bảng/variant được nhận diện, không trộn affinity.
- Mỗi ô dữ liệu hoặc fact có provenance; mọi nội dung không chuyển đổi được có
  quyết định/lý do. Không đạt schema thì review; không ép đạt tỷ lệ keep 100%.
- Đọc lại CSV bằng csv.DictReader, kiểm Unicode/quote/newline và hash; ID ổn định
  khi chạy lại. Không mất 15 fact trang bị và 1.551 chunk stats đang giữ.
- Đo coverage theo bảng/hàng/fact/level và số review, phân biệt thiếu raw với
  parser không hiểu. Chọn 30–50 bảng/fact để người dùng review thêm theo rủi ro.
- Chunk đủ title/variant/level/đơn vị/nguồn, không vượt token, không truncate;
  giữ liên kết ảnh có context, không sinh caption hay gán ảnh hàng loạt.
- Báo cáo trước/sau chỉ trên bản thử. Đánh giá retrieval/LLM là bước xin phép riêng.

## 7. Kết quả khảo sát có thể kiểm tra

`backend/data/research_runs/s3-table-survey-20261108-v2/`:
report.json, tables.jsonl (8.506 occurrence), input-fingerprints.json,
equipment-coverage.json, current-policy-comparison.json.

Script khảo sát `backend/ingest/debug/table_survey.py` chỉ đọc raw và ghi thư mục
báo cáo mới. Lượt v1 là khảo sát sơ bộ; v2 sửa nhầm dấu backlink ↑ thành growth
rate và tách references/recipe/patch/quote để phân loại rõ hơn. Không dùng v1
để ước lượng nhóm /Lv. 17 checksum artifact cuối được kiểm lại và không đổi.
Chưa thực hiện bất kỳ bước P0/P1/P2 nào của kế hoạch chuyển đổi phía trên.
