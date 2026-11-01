# Báo cáo bàn giao Sprint 2 — IndexBeast (nhóm 4 Hollows)

| | |
|---|---|
| Sprint | 2 — *Pipeline dữ liệu & khung API*, 26/10 – 01/11/2026 (Bài KT 1). **Đã đóng** |
| Ngày lập | 31/10/2026; **cập nhật 01/11/2026 sau khi đóng sprint** (Asia/Saigon) |
| Người lập | TV1 (Hoanbucon), Tech Lead |
| Căn cứ | `develop` tại `5a72bd5` (sau PR #54); Trello đọc ngày 01/11; các handover S2 trong [`docs/handover/`](README.md); GitHub (review, CI); dữ liệu `backend/data` bản sao trên máy TV1; các lệnh kiểm tra ở mục 6 |

## 1. Tóm tắt

- **Trello:** 13/13 thẻ S2, thẻ mục tiêu sprint (5/5) và thẻ *Sprint 2 Review & Retro* (5/5) đều ở cột *Hoàn thành*.
- **Repo:** 27 PR S2 (#28–#54) đã merge vào `develop`. CI trên `5a72bd5` xanh (backend, web, bot).
- **Còn lệch Definition of Done:** **0/27 PR có lượt review** trên GitHub; nhiều PR do tác giả tự merge. DoD yêu cầu ít nhất 1 người approve (mục 3).
- **Dữ liệu:** 4.164 trang base + SotE → 23.765 chunk; đã nạp PostgreSQL và index 18.368 chunk tiếng Anh vào Qdrant, **kiểm lại trên máy TV1** (mục 6).
- **Chatbot chạy end-to-end** ở chế độ `rag`/`llm_only`, có rate-limit, xác thực bot và giới hạn thời gian (PR #48).
- **Phạm vi đã chốt:** base game + Shadow of the Erdtree, cả lore lẫn gameplay/build. Đã tạo thẻ CHANGE-REQ để lưu vết (mục 4).
- **Phát hiện dữ liệu quan trọng nhất của sprint:** cleaner làm mất bảng chỉ số infobox của khoảng 1.500 trang mà không để lại dấu vết. Đã sửa ở PR #53, nhưng dữ liệu chỉ số **chưa vào corpus** (mục 5.2).

## 2. Kết quả theo thành viên

| Thành viên | Thẻ S2 | Kết quả chính (theo handover) | PR |
|---|---|---|---|
| **TV1** Hoanbucon | Schema PG & migrations; API contract v1 + mock; Lỗi & logging | 8 bảng + migration `0001`; `/chat`, `/chat/stream`, `/feedback`, `/conversations/{id}`; lỗi chuẩn `{code, message, request_id}`; `docs/api/openapi.json` được CI kiểm tra. Ngoài thẻ: sửa 3 lỗi audit (#30), rate-limit/hội thoại bot/timeout (#48), báo cáo và tài liệu công nghệ (#49, #50), khảo sát dữ liệu (#52), sửa cleaner bảng chỉ số (#53) | #28–#30, #48–#50, #52, #53 |
| **TV2** Nông Hữu Thịnh | Crawl toàn bộ wiki.gg; Làm sạch; Chunking + metadata | Inventory 4.179 ứng viên → 4.164 raw (7 trang lỗi ảnh, vẫn có text); clean `s2-full-v2`: 22.419 record, 20.235 eligible; chunk `s2-full-v1`: **23.765 chunk**, tối đa 450 token; audit độ phủ toàn corpus (#51) | #31, #36–#38, #51 |
| **TV3** Nguyễn Quang Minh | fanapis → entities; Embedding & indexing; Retrieval hybrid; Golden set v1 | Index 18.368 chunk EN; retrieval warm median/p95 **31,9 / 57,9 ms**; pipeline LangChain `mock`/`llm_only`/`rag`; golden set **60 câu** (38 VI/22 EN). Cuối sprint thêm: ảnh minh họa từ backend, chẩn đoán và phục hồi lỗi JSON của DeepSeek, truy vấn VI→EN, định tuyến câu hỏi tổng quan | #34, #35, #39–#42, #45, #47, #54 |
| **TV4** Vũ Ngọc Quý | UI chat cơ bản; api.ts viết tay; Bot /ask gọi API mock | Web theo OpenAPI, integration test với backend mock; bot `/ask` gửi `external_ref`, embed có nguồn; ảnh minh họa câu trả lời, sidebar, favicon | #33, #44, #46 |

### Sản phẩm bàn giao của sprint (thẻ mục tiêu)

| Sản phẩm | Trạng thái |
|---|---|
| Dữ liệu wiki.gg đầy đủ trong Qdrant (dense + BM25) | Đạt. 18.368/23.765 chunk được index; 5.397 chunk ngôn ngữ khác (ja, unknown…) bị loại theo chính sách `pilot/en`. Thiếu dữ liệu gameplay/chỉ số (mục 5.2) |
| Schema PostgreSQL + migrations | Đạt, test tích hợp với Postgres thật |
| OpenAPI v1 + endpoint mock | Đạt |
| UI chat & /ask gọi API mock | Đạt |
| Golden set v1 (60 câu) | Trello tick đạt. Đủ 60 câu, nhưng phiếu review chéo `backend/eval/reviews/s2-golden-set-review.jsonl` vẫn ghi **60 pending, 0 approved** (kiểm ngày 01/11) |

## 3. Trello và repo còn lệch

| Điểm | Chi tiết |
|---|---|
| Review PR | Thẻ ở *Hoàn thành*, nhưng 0/27 PR (#28–#54) có lượt review trên GitHub |
| Golden set | Thẻ tick "TV2 review chéo", nhưng sidecar review ghi 0/60 approved |
| Thẻ fanapis → entities | Tick 3/3. Báo cáo chưa kiểm bảng `entities` có dữ liệu: trên máy TV1 chỉ mới nạp `documents`/`chunks` |

Đề nghị cho S3: bật branch protection trên `develop` (bắt buộc 1 approve), và chỉ tick review golden set khi sidecar có `approved`.

## 4. Phạm vi sản phẩm (đã chốt)

IndexBeast trả lời **cả lore lẫn gameplay/build** cho Elden Ring **base game + Shadow of the Erdtree**. Nightreign và Tarnished Edition vẫn ngoài phạm vi. Quyết định được ghi ở thẻ CHANGE-REQ [*[TV1] CHANGE-REQ: Phạm vi base + SotE, lore + gameplay/build*](https://trello.com/c/7Bm59z2N) (cột Sprint 3). Hai mục checklist còn mở: "Team quyết định" và "Cập nhật SRS + Changelog".

Tài liệu còn mô tả phạm vi cũ, cần sửa ở S3: SRS §1.2, ADR-004 (đang ghi base game, SotE là ngoại lệ), `docs/AGENTS.md`, tiêu chí golden set.

## 5. Kết quả code review và dữ liệu

### 5.1 Code review (Sprint 1 + Sprint 2)

| # | Mức | Vấn đề | Trạng thái 01/11 |
|---|---|---|---|
| 1 | Cao | API gọi LLM thật không có xác thực và rate-limit | **Đã sửa** (#48): rate-limit Redis theo IP/`external_ref`, kênh discord cần `X-Service-Token`, Redis lỗi thì từ chối |
| 2 | Cao | Bot không gửi `conversation_id` nên mất ngữ cảnh và đẩy hội thoại web ra khỏi bộ nhớ | **Đã sửa** (#48): dùng lại hội thoại theo `(channel, external_ref)`, thải theo LRU |
| 3 | Trung bình | Timeout bot 30 s ngắn hơn backend | **Đã sửa** (#48): backend hạn 45 s (504), bot 60 s |
| 4 | Trung bình | Câu hỏi dài vượt 512 token E5 trả 503 | Chưa sửa |
| 5 | Trung bình | `spoilers=false` loại mọi chunk vì corpus chưa có `spoiler_level` | Chưa sửa |
| 6 | Trung bình | Index lại không xóa point cũ trong Qdrant | Chưa sửa |
| 7 | Trung bình | Stream hiển thị chữ trước khi kiểm bằng chứng cuối | Chưa sửa |
| 8 | Thấp | Hash Discord user ID không có salt | Chưa sửa |
| 9 | Thấp | Mỗi câu hỏi thêm 2 lượt gọi Qdrant (`store.ready()`) | Chưa sửa |
| 10 | Thấp | Hai loader PostgreSQL gần giống nhau | Chưa sửa |

Còn treo từ audit PR #30: `/conversations/{id}` ở chế độ mock chưa kiểm chủ sở hữu; JSON 500 nằm ngoài CORS; index trùng `ix_chunks_document_id`. Kho hội thoại vẫn ở RAM từng worker, nên demo chế độ live phải chạy 1 worker.

### 5.2 Dữ liệu ([khảo sát và đề xuất đã duyệt](2026-10-31_s2-tv1_khao-sat-du-lieu-va-de-xuat.md))

- **Bản cuối:** raw `raw/wikigg/snapshots/` (4.164 trang), clean `clean_runs/s2-full-v2`, chunk `chunk_runs/s2-full-v1`; checksum khớp manifest.
- **Lỗi lớn nhất:** `html_clean.infobox()` bỏ qua `.pi-smart-group` nên mất bảng Attack Power, Attributes, Damage Negation, Resistance… của ~1.500 trang mà không ghi ledger. **Đã sửa ở #53**: chạy thật trên 4.164 trang giữ lại 1.551 khối chỉ số (1.503 trang); phần lore giữ nguyên từng dòng. Theo policy hiện tại, khối chỉ số vẫn nằm trong `review.csv`, chưa vào chunk.
- **Lỗi chặn nạp dữ liệu trên máy khác:** artifact ghi đường dẫn tuyệt đối của máy TV2, nên `load_full` hỏng. TV1 đã sửa trên nhánh `fix/s2-tv1-duong-dan-artifact` (commit `5359b2f`), **chưa push, chưa có PR**.
- Lỗi nội dung TV2 đã liệt kê (trang mẫu Talisman, nhãn ngôn ngữ 🇧🇷/🇹🇼, markup) chưa sửa.

## 6. Kiểm tra đã chạy

### Ngày 01/11 trên `develop` tại `5a72bd5`, máy Windows của TV1

| Lệnh | Kết quả |
|---|---|
| `ruff check .`, `export_openapi --check` (backend) | Đạt |
| `pytest` (backend) | **529 passed**, 15 deselected |
| `pytest -m integration` (Postgres/Redis/Qdrant local) | **15 passed** |
| `npm test` web / bot | **30/30** và **21/21** |
| CI GitHub trên `5a72bd5` | backend, web, bot: success |

Sau khi pull phải chạy lại `pip install -r requirements-dev.txt -c constraints.txt`, vì S2 thêm LangChain.

### Ngày 31/10, dữ liệu trên máy TV1 (code nhánh `fix/s2-tv1-duong-dan-artifact`)

| Bước | Kết quả |
|---|---|
| `load_full --validate-only` rồi nạp PostgreSQL | 4.164 document, 23.765 chunk, 0 lỗi; job `succeeded` |
| `ingest index` (pilot, en) vào `lore_chunks` | Tải model E5/BM25, 26 phút 38 giây; Qdrant **18.368 point, green** |
| Clean thử bằng code #53 vào `clean_runs/s2-full-v3-tv1-test` | 5 phút, keep trùng 73.559/73.559 dòng; chỉ là bản kiểm thử |

Chưa chạy: hỏi chatbot thật trên máy TV1. `.env` của máy này chưa có `DEEPSEEK_API_KEY` và các biến `CHAT_MODE`/`RAG_*`.

### Sự cố hạ tầng

Trong lúc index, ổ H: còn 1,9 GB và C: còn 2,3 GB; ngày 01/11 H: còn 15 GB, C: 3,6 GB. Chưa xác định chương trình ghi vào H: (nghi ổ ảo của Docker/WSL hoặc cache model). Docker có khoảng 12,9 GB image và 2,7 GB build cache dọn được, chưa dọn.

## 7. Chuẩn bị Sprint 3

1. **Review và merge `fix/s2-tv1-duong-dan-artifact`** (đề xuất dữ liệu #4) để mọi máy nạp được dữ liệu.
2. **Hoàn tất CHANGE-REQ:** team xác nhận, cập nhật SRS §1.2, ADR-004, `docs/AGENTS.md`.
3. **Đo baseline Recall@5/MRR** trước khi đổi corpus, thêm câu hỏi chỉ số/gameplay vào golden set (đề xuất #6).
4. **Nhận dữ liệu gameplay vào corpus** (đề xuất #2) và gộp infobox mỗi trang thành một chunk (#3); clean/chunk lại, index collection mới, so sánh rồi mới đổi `RAG_COLLECTION`.
5. **TV2 sửa lỗi nội dung** đã biết (#5) và review golden set.
6. **TV1:** lưu hội thoại vào PostgreSQL thay RAM; xử lý các lỗi review #4–#10.
7. **Quy trình:** bắt buộc review PR trước khi merge; kiểm tra và dọn dung lượng ổ H:/C:.
