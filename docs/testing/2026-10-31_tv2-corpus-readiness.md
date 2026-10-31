# TV2 — Kiểm tra độ đầy đủ dữ liệu ngày 31/10/2026

## Kết luận

Corpus hiện đủ điều kiện kỹ thuật cho pilot lore có trích nguồn, nhưng **chưa đủ để
coi là bộ dữ liệu gameplay/thông số hoàn chỉnh**. Có nội dung bị loại theo chính sách
lore, có thiếu metadata và có lỗi lọt nội dung mẫu/nhãn ngôn ngữ. Không đánh đồng
coverage 100% phần eligible với giữ đủ nội dung raw hoặc trả lời đúng mọi câu hỏi.

Không cần crawl lại toàn bộ để phục hồi phần đã bị lọc. Một số thông tin không có
trong snapshot cần xác minh nguồn riêng; không điền bằng suy đoán.

## Phạm vi và phương pháp thực tế

- Đọc lại quy ước, AGENTS, SRS, kiến trúc, kế hoạch và handover TV2; đọc contract RAG,
  audit năng lực và ảnh mới của TV3. Nhánh nền origin/develop `bcefa26`.
- Inventory toàn bộ file trong raw/media/clean_runs/chunk_runs/crawl_runs/research_runs;
  các lượt thử và bản cũ không được cộng vào tập nghiệm thu.
- Tập được kiểm nội dung là **4.164 trang** từ manifest clean s2-full-v2, đối chiếu
  inventory/checkpoint/report crawl s2-full-20261028. Không chọn tùy ý toàn thư mục raw.
- Parse HTML của từng trang bằng Beautiful Soup; thống kê field infobox, bảng và heading.
- Kiểm checksum CSV, baseline fingerprints, provenance raw, document/chunk IDs,
  processed so với CSV, source slices, coverage, ngữ cảnh speaker/trigger, image IDs,
  encode lại từng embedding_text bằng tokenizer E5 local đúng hash. Không tải model.
- Hash toàn bộ **10.371 blob ảnh khác nhau được images.csv tham chiếu**; không chỉ lấy mẫu.
  Đây là kiểm byte/hash, chưa decode/Pillow mọi ảnh hoặc kiểm ngữ nghĩa pixel.
- Không crawl, gọi AI, embedding/indexing, ghi PostgreSQL hoặc sửa corpus gốc.
  Không truy vấn live DB/Qdrant: số liệu index trong tài liệu TV3 là bằng chứng lịch sử.

Script: `backend/ingest/debug/corpus_readiness.py`. Output local, không đưa data vào Git:

```text
D:/Index-Beast/backend/data/research_runs/s2-readiness-20261031/report.json
D:/Index-Beast/backend/data/research_runs/s2-readiness-20261031/pages.jsonl
D:/Index-Beast/backend/data/research_runs/s2-readiness-20261031/metadata-check.json
```

## Các kiểm tra kỹ thuật đã đạt

| Hạng mục | Kết quả chạy lại |
|---|---:|
| Inventory theo 196 category | 4.179 trang; queue rỗng |
| Text có clean và chunk | 4.164/4.164 trang |
| Inventory không có kết quả hoặc lý do loại | 0 |
| Trang bị loại bởi crawler | 15: missing/redirect/namespace; chưa xác minh lại website |
| Clean records | 22.419: keep/eligible 20.235; review 2.184 |
| Chunk | 23.765; ID duy nhất; cap tổng 450 token |
| Unit eligible kiểm source slice và không có gap | 23.659/23.659 |
| CSV review / images | 55.560 / 65.593 dòng |
| Ba CSV: sai số cột, thiếu ô, ID trùng | 0 |
| Clean: URL/revision/snapshot/lang/source_type/fetched_at rỗng | 0 |
| Clean text chứa Unicode replacement character U+FFFD | 0 |
| Baseline fingerprint entries khớp | 12.495 lượt kiểm; có path xuất hiện ở cả hai baseline |
| Blob ảnh được tham chiếu tồn tại và khớp SHA-256 | 10.371/10.371 |
| Lỗi integrity/source slice/token/image-link được script phát hiện | 0 |

Các kiểm tra integrity đạt không phủ định những lỗi nội dung/ngôn ngữ phía dưới.
Raw có 6.760 bảng ngoài navbox, 4.124 bảng có rowspan/colspan. Heuristic tìm được
2.726 bảng ứng viên stats trên 1.617 trang. Số này không đồng nhất với 228 bảng bị
rule numeric_stats_table loại: nhiều bảng bị chặn bởi section/infobox hoặc vào review.

## Thông số và nội dung bị thiếu ở clean/chunk

| Nhóm thiếu | Bằng chứng và ảnh hưởng |
|---|---|
| Weight | 1.376 field raw và 1.376 node bị loại với nhãn Weight |
| FP cost | Raw có 1.068 occurrence fp_cost; audit loại ghi 1.067 node FP Cost. Không suy ra mọi FP đã mất: một số còn được nhắc trong prose |
| HP/Runes | Node bị loại có 455 HP và 451 Runes; ảnh hưởng dữ liệu enemy/boss |
| Sức chứa | 974 Max. Held và 579 Max. Stored bị loại |
| Thông tin vật phẩm | 3.983 record gameplay_infobox_field, trên 3.313 trang; trộn type, effect, price, acquisition, requirements... |
| Effects/Acquisition/Stats và mục gameplay | 6.637 record gameplay_section, trên 3.510 trang |
| Bảng chỉ số/loadout | 228 numeric_stats_table, 79 combat_loadout_table; bảng khác có thể ở review |
| Bảng chưa phân loại | 1.639 record unclassified_structure; bao gồm bảng nâng cấp cần đọc header/affinity |

Các số trên là occurrence/node/record theo loại, không cộng thành số vật phẩm mất;
các nhóm có thể cùng xuất hiện trên một trang. Infobox numeric/production còn gồm
68 Voice actor, nên không đưa nguyên nhóm trở lại như thể đều là thông số.

Đối chiếu trực tiếp:

- **Moonveil (9267)**: raw có Weight 6.5, FP Cost `- (15 20)`, bảng Attack Power
  Physical 73/Magic 87; bảng riêng cho Guarded Damage Negation và requirements/scaling.
  Chuỗi Weight/FP không có trong chunk của trang. Một số effect/skill vẫn tồn tại.
- **Uchigatana (12549)**: raw có Weight 5.5, FP Cost `-(10 15)`, physical attack 115;
  không được diễn giải 45.0 của guarded physical negation thành attack.
- **Longsword (14536)**: bảng upgrade theo Standard/Heavy/Keen/... nằm ở review.
  Raw có bảng gộp ô, hàng +0, +25 và tăng theo cấp; không tự tạo giá trị +1..+24
  nếu nguồn không hiển thị những hàng đó. Affinity phải lấy từ tab cha, không từ suy đoán.
- **Malenia's Winged Helm (2500)**: raw có Weight 4.0, poise 4, damage negation và
  resistances. Không đủ chỉ giữ mô tả item để trả lời câu hỏi phòng thủ.
- **Fire Knight Armor (16564)**: snapshot HTML không có field Weight; stats phòng thủ
  vẫn có. Đây là thiếu ở snapshot cần đối chiếu nguồn, không phải chỉ sửa cleaner là
  có thể phục hồi Weight. Không điền con số từ trí nhớ.

Nhóm/type không tự chứng minh là một item riêng. Ví dụ các trang nhóm Incantations
không có fp_cost là hợp lệ; không báo tất cả thành lỗi thiếu FP. Talisman không có
weight còn bao gồm trang mẫu, không phải vật phẩm thật.

## Lỗi nội dung/ngôn ngữ được phát hiện

1. **Elden Ring Talisman Template (5474)** có 5 chunk, trong đó 3 EN, 1 JA, 1 unknown.
   Có code mẫu và `English line 1/2/3`, chưa được loại khỏi artifact. Cần chặn page role
   template/example với bằng chứng nội dung; không chỉ kiểm namespace.
2. Tab 🇧🇷 có **17 chunk bị gắn en**; đọc ví dụ Longsword thấy tiếng Bồ Đào Nha thật.
   Nguyên nhân map thiếu 🇧🇷 rồi fallback html_lang=en. EN hiện là nhãn heuristic,
   chưa thể bảo đảm corpus thuần EN chỉ bằng filter lang=en.
3. Tab 🇹🇼 có 15 chunk gắn unknown; cần xử lý nhãn ngôn ngữ nguồn, không mặc định EN.
4. Một chunk Great Épée (2723) mang tab 🇫🇷 nhưng nội dung `In-game item description /
   In-game stats` bằng EN: đây là ứng viên UI/context cần review, không tự đổi sang FR.
5. Serpent-God's Curved Sword (4612) còn markup `[[Skill: Ground Slam|Ground Slam]`
   trong Notes. Giữ facts/điều kiện và sửa markup, không xóa toàn đoạn gameplay.
6. 1.381 chunk có body <=20 ký tự: tập ứng viên kiểm fragment/tab label. Không xóa
   hàng loạt vì quote hoặc lời thoại ngắn có thể có nghĩa.

## Metadata và ảnh còn thiếu

- Toàn bộ 23.765 chunk chưa có giá trị metadata riêng cho patch_version, game_version,
  upgrade_level, affinity, ng_cycle, source_updated_at, spoiler_level, content_type,
  review_status. Một số nội dung vẫn xuất hiện trong text. Revision/fetched_at không
  thay thế patch/version. Không gán approved, spoiler_level=0 hoặc base hàng loạt.
- 4.164 document có source_updated_at=null; 8.737 section không có anchor (gồm cả
  Introduction/Infobox, không coi tất cả là lỗi). Vẫn truy nguồn bằng page/revision/DOM.
- 3.288 dialogue chunk có speaker=null; 4 thiếu trigger. Context khớp processed nhưng
  chưa chứng minh speaker đủ; chỉ bổ sung khi raw có căn cứ, không đoán từ tên trang.
- 1.801 chunk lang=unknown. Tổng nhãn EN 18.368 gồm cả các trường hợp sai ở trên.
- 65.593 occurrence ảnh: downloaded 9.114, cached 14.472, excluded UI 42.000, failed 7.
  7.640 chunk có image_ids; không có ảnh ở mọi chunk không tự là lỗi.
- 64.438 occurrence không caption; cả 65.593 giữ license_status unknown_review_required.
  Không tự sinh caption hoặc suy quyền ảnh. Không có đánh giá semantic image retrieval/OCR.
- 7 lỗi media gồm bản đồ Realm of Shadow/Lands Between không đạt kiểm an toàn/kích
  thước và 5 URL ngoài allowlist. Không bỏ giới hạn an toàn hoặc mở host hàng loạt để sửa.

## Thứ tự khắc phục đề xuất

1. **P0 chất lượng**: loại template/example đã xác minh; sửa map tab ngôn ngữ; review
   fragment/UI và markup còn lọt. Test âm: bản EN không chứa các đoạn Portuguese đã biết.
2. **P0 dữ liệu gameplay**: cập nhật policy đã duyệt, giữ field–value và Effects/Acquisition;
   parse bảng có rowspan/colspan, group header, units, 1h/2h, level/affinity; chưa rõ thì review.
3. **P1 metadata**: thêm content_type/page_role và context bảng/patch có bằng chứng vào
   artifact; giữ source_type riêng. Những field thiếu bằng chứng dùng unknown, không bịa.
4. Chạy 20 trang đa dạng, regression 200, rồi đủ 4.164; kiểm cell→fact→chunk, quotes/dialogue,
   ngôn ngữ, coverage/token/IDs/provenance. Dùng thư mục mới; không ghi đè bản đang phục vụ.
5. Bàn giao JSONL mới cho TV3 dry-run/index riêng và đánh giá câu hỏi stats/gameplay;
   chỉ thay corpus phục vụ sau review. TV2 không sửa embedding/retrieval hoặc schema TV1.
6. **P2**: đối chiếu các field thiếu từ raw, khắc phục 7 ảnh, bổ sung patch/spoiler/nguồn
   sửa khi có bằng chứng. Cần khảo sát website riêng nếu muốn chứng nhận độ phủ wiki hiện tại.

Không có bước clean/chunk lại, sửa DB/index, crawl bổ sung hoặc đổi phạm vi được thực hiện
trong audit này. Không thể kết luận toàn bộ kiến thức game đã đủ chỉ từ snapshot category.

## Chạy lại

Từ `D:/Index-Beast/backend`, dùng tokenizer local đã có và một output directory mới:

```powershell
.venv/Scripts/python.exe -X utf8 -m ingest.debug.corpus_readiness --output-dir data/research_runs/<audit-moi> --tokenizer '<duong-dan-tokenizer.json-local>'
```

Ruff check/format script đạt. Full audit đã chạy; metadata/semantic diagnostics được
chạy bổ sung bằng cùng hàm metadata_audit sau khi hoàn tất lượt scan chính. Script CLI
hiện gọi cả hai để chạy lại. Không chạy suite embedding/LLM/server trong tác vụ này.
