# TV2 — khảo sát raw toàn corpus và kế hoạch clean/chunk

Ngày 29/10/2026. Trạng thái: **đề xuất để duyệt**, chưa chạy clean/chunk production toàn corpus.
Phạm vi: ba thẻ TV2 S2, ADR-004 base game; không embedding, entities, retrieval hoặc thay schema TV1.

## 1. Tập dữ liệu thực tế

Nguồn là report + checkpoint của crawl-full-02f289b359204e4a9030556add4da79b,
run s2-full-20261028. Inventory 4.179 ứng viên đã xử lý: 4.157 thành công,
15 bị loại ở bước crawl, 7 lỗi media. Report chưa phải nghiệm thu full lore base game.

Khảo sát đọc **4.164 snapshot**: 4.157 trang thành công và 7 trang có raw hợp lệ nhưng media lỗi.
Không quét mọi revision/S1/trial trong thư mục raw để cộng thành corpus. Đối chiếu ID,
revision, content_hash; fingerprint snapshot/report/checkpoint/inventory/manifest trước–sau.
Không có parse failure hoặc đầu vào bị thay đổi. Không đọc pixel/sinh caption, không crawl mạng,
không API AI, không encoder/DB write. Lần audit v1 dừng vì lỗi đường dẫn tương đối; chỉ v2 được nghiệm thu.

Artifact local: `backend/data/research_runs/s2-full-scope-20261029-v2/`:

- summary.json: số liệu và mô phỏng token.
- pages.jsonl: từng trang, partition tạm, lý do, lead/location, revision, snapshot, URL.
- sections.jsonl: heading/anchor/location, excerpt, token, loại block và kết quả heuristic cũ.
- input-fingerprints.json: checksum các file nguồn được đọc.
- examples.json và simulation-pages.json: ví dụ và trang thử chunk.

Đây là **research**, không phải lore_clean.csv cuối hoặc dữ liệu đã sẵn sàng index.

## 2. Phân vùng scope cần duyệt

| Vùng tạm thời | Trang | Căn cứ và xử lý đề xuất |
|---|---:|---|
| base_context_candidate | 1.295 | Địa danh base theo cấu hình trong lead/location; ưu tiên review để chọn section, không tự duyệt mọi câu |
| dlc_candidate | 524 | 415 có câu định nghĩa trực tiếp thuộc SotE; 109 có marker trong title/location. Tách hai mức bằng chứng, kiểm tra trước khi loại cả trang |
| mixed_or_dlc_review | 566 | Có nhắc DLC trong nội dung, chưa chứng minh cả trang ngoài scope. Tách section/block để cứu phần base |
| unresolved_review | 1.779 | Chưa có bằng chứng dương về base; giữ chờ review, không coi là rác hoặc tự gán base |

Phân vùng dùng marker hữu hạn, có thể bỏ sót hoặc bắt nhầm tên. Không khẳng định đã đếm hết DLC.
Ngoài scope release còn phải xét content_role: lore, mô tả item, dialogue, gameplay/stats,
editorial/navigation. Không dùng một nhãn scope để đồng thời quyết định mọi loại nội dung.

Các phát hiện cần sửa ở luật hiện tại:

- Lấy hai paragraph đầu kể cả rỗng làm mất định nghĩa trang. Cần lấy paragraph có nghĩa,
  bỏ UI/notice, giữ DOM locator cho phần được dùng làm bằng chứng.
- 353 trang có cả generic intro ELDEN RING (2022) và dấu hiệu DLC. **Nhãn năm không là bằng chứng base.**
- 557 base-context candidate hiện bị heuristic cấp trang đưa vào review; không chữa bằng cách gán base hàng loạt.
- Messmer the Impaler có định nghĩa trực tiếp là boss SotE; Scadutree Fragment có nhãn 2022 nhưng marker DLC.
- Erdtree nhắc Scadutree: không loại cả bài; kiểm tra nguồn từng đoạn.
- Elden Remembrance thiếu địa danh ở lead; không bỏ mô tả item chỉ vì không khớp base_places.
- Ranni có location/lead/heading cần kiểm tra cùng nhau, không suy người nói từ tên trang.

## 3. Cấu trúc và nhiễu thực đo

| Đặc điểm | Số liệu |
|---|---:|
| Trang có bảng / tổng bảng | 3.340 / 8.506 |
| Trang có infobox | 3.837 |
| Trang có tab | 3.399 |
| Trang có gallery | 832 |
| Section sau parse chẩn đoán | 24.723 |
| Heading Description / Background / Dialogue | 2.937 / 245 / 95 |
| Bảng được parser nhận là dialogue / typed turn | 192 / 3.236 |
| Turn có trigger / speaker tường minh | 3.232 / 0 |
| Section còn source_type unknown / lang unknown | 9.896 / 3.796 |

Parser cũ cho 6.033 section base heuristic, 16.900 review, 1.790 excluded. Đây là kết quả
chẩn đoán, **không phải 6.033 section đã duyệt**. Một số bảng chưa nhận dạng vẫn ở nhóm table.
Các từ khóa suy đoán như perhaps/possibly cũng chưa đủ để kết luận source_type đáng tin.

Nhiễu được parser nhận: 7.248 UI/navigation nodes, 23.108 reference/edit markers,
6.736 field số liệu/production, 228 stats tables, 79 combat-loadout tables,
149 quote-display duplicates. Không suy rằng mọi reference là rác: giữ bằng chứng citation
trong provenance; chỉ bỏ ký hiệu/backlink khỏi text dùng cho RAG.

## 4. Chính sách clean đề xuất

1. Tạo manifest text riêng theo ID/revision/hash. Ghi text_status và media_status riêng;
   7 trang lỗi ảnh không tự mất text. Không sửa report crawl partial thành completed để vượt kiểm tra CLI.
2. Phân vùng page bằng chứng dương, rồi xét section/block. Ledger gồm decision, reason,
   locator, evidence, rule_version và override thủ công có người/ngày review.
3. Giữ Description, Background/Overview/Lore, hội thoại với trigger, thứ tự dòng và
   nhãn ngôn ngữ; lưu quan hệ family/identity trong infobox khi có ích cho lore.
4. Bỏ menu, navbox, edit/backlink marker và stats thuần. Patch Notes, Strategies,
   Frame data, Moveset, crafting/boosting và acquisition hướng dẫn không vào lore tự động;
   chỉ giữ đoạn có nội dung lore được xác nhận. Cut/unused và bảng hỗn hợp vào review.
5. Tách clean cấu trúc khỏi phân loại scope/source_type. Không xóa toàn bộ bảng/infobox.
   Không lấy min_chars=200 làm điều kiện loại cứng: mô tả item ngắn vẫn có nghĩa.
6. Chỉ khử display duplicate có bằng chứng DOM; không dedup mọi câu lặp qua trang/section.
   Không viết lại hoặc thêm lore. Không chốt source_type chỉ dựa heading hay vài từ khóa.
7. Giữ tiếng Anh/Nhật thành block riêng khi nguồn có nhãn. Không đặt toàn section là en
   hoặc suy speaker từ page title. Chưa chắc thì null/unknown + review.

## 5. Chunk theo loại nội dung

Section body token: p50=43, p90=177, p95=267, p99=834, max=25.768;
562 section có body >450 token. Nhiều section ngắn, không ép mọi chunk đủ 350 token.
Body <=450 vẫn có thể cần split sau khi thêm title/heading/context.

| Nội dung | Cách chia |
|---|---|
| Mô tả item/quote ngắn | Giữ nguyên block và title/heading; không ghép nhiều item |
| Lore dài | Theo heading, paragraph/câu; cap toàn chuỗi 450, overlap tối đa 50 trong cùng unit |
| Hội thoại | Theo turn/trigger/biến thể/ngôn ngữ; split turn quá dài, lặp context nguồn khi cần; không overlap xuyên trigger |
| Infobox có lore | Giữ nhãn field–value có nghĩa, tách ngữ cảnh Infobox; không đưa số stats trở lại |
| Bảng hỗn hợp | Phân loại hàng/cột và giữ header cần thiết; chưa hiểu cấu trúc thì review |
| Notes/Trivia | Xét scope và nguồn từng block, không gán speculation hàng loạt |

Mô phỏng 35 trang có phân tầng cấu trúc/scope, 5 trang dialogue và 10 trang có section dài nhất:
1.195 chunk chẩn đoán, max=450, p95=445, không unit review/error. Mẫu có nội dung DLC/review
để kiểm tra kỹ thuật, **không là corpus được chấp nhận**, không suy ra số chunk toàn bộ hoặc chất lượng retrieval.
Đếm bằng tokenizer local multilingual-e5-small, không encoder/model download. 450/50 là
baseline ADR-003 Proposed, vẫn cần TV3/Mentor review và đánh giá retrieval của TV3.

Metadata tối thiểu giữ theo SRS; doc/chunk ID theo core.ids. Bổ sung provenance artifact:
revision, snapshot/hash, section anchor, source location, unit/offset, language/trigger,
clean/chunk version, image occurrence IDs. Phân biệt fetched_at, source_updated_at và
processed_at. Không ép unknown vào enum DB; không tự sửa schema TV1. Review với TV3
DB text/embedding_text và passage prefix để tránh thêm prefix hai lần.

## 6. Ảnh

65.593 occurrence: 42.000 bị bộ lọc ảnh loại, 23.586 downloaded/cached, 7 failed.
Đây là occurrence, không phải số file duy nhất. Cả 23.593 occurrence không bị loại đều
có license unknown_review_required; không coi tải được là được phép tái phân phối.
Manifest không lệch revision trong tập khảo sát.

Chỉ gắn occurrence cùng page/revision/section, ảnh infobox giữ ngữ cảnh riêng; chưa rõ
vào review. Giữ alt/caption nguyên nguồn, không sinh caption, không OCR hoặc image embedding.

## 7. Thứ tự thực hiện sau khi duyệt

1. Chốt manifest text/media, vocabulary quyết định và bằng chứng base; kiểm tra 15 excluded + 7 media errors.
2. Review 20 trang theo rủi ro: 4 item, 4 NPC, 3 lore/location, 3 DLC, 3 mixed, 3 cấu trúc đặc biệt.
   Lưu expectation ngắn có provenance, kiểm tra trước/sau trực tiếp và fixture tái lập được trên CI.
3. Sửa luật cấu trúc/metadata tại core/text và ingest filter/transform trên nhánh clean riêng.
   Chạy 20 trang, hồi quy mẫu 200, rồi toàn text manifest; xuất CSV/processed/review/report vào thư mục mới.
4. Trên nhánh chunk: chạy subset đã duyệt, đối chiếu coverage/token/context/ảnh, sau đó corpus đủ điều kiện.
   Kiểm tra DB tạm (rerun/rollback), mới nạp PG local; giữ các document chưa đủ metadata trong review.
5. Báo số lượng vào/ra/review/excluded theo nguyên nhân và phân bố, không tuyên bố sạch hoàn toàn.

Nghiệm thu: không mất câu thoại/trigger/heading, không xuyên scope, truy nguyên mọi quyết định,
ngân sách token toàn chuỗi <=450, CSV round-trip đúng Unicode/newline, ID ổn định, raw/media
không đổi, không có bỏ sót không giải thích. Chưa bắt đầu nhánh mở rộng hệ thống thứ tư.

## Tái lập khảo sát

Từ backend, dùng output mới và tokenizer local đang có:

```powershell
.venv/Scripts/python.exe -m ingest.debug.raw_scope_study `
  --run-dir data/crawl_runs/s2-full-20261028 `
  --tokenizer '<duong-dan-tokenizer.json-local>' `
  --output-dir data/research_runs/<ten-moi>
```

Module chỉ đọc raw và ghi research; không tự nạp chunks hoặc DB. Không sửa planning/SRS/ADR
hay trạng thái Trello trước khi duyệt. docs/04_ARCHITECTURE.md, ADR-003/004 và planning/sprint_plan.json
là ràng buộc cho triển khai tiếp theo.
