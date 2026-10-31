# Báo cáo bàn giao Sprint 2 — IndexBeast (nhóm 4 Hollows)

| | |
|---|---|
| Sprint | 2 — *Pipeline dữ liệu & khung API*, 26/10 – 01/11/2026 (Bài KT 1) |
| Ngày lập | 31/10/2026 (Asia/Saigon) |
| Người lập | TV1 (Hoanbucon), Tech Lead |
| Căn cứ | `develop` tại `b0f10a1` (sau PR #44); Trello đọc ngày 31/10; các handover S2 trong [`docs/handover/`](README.md); GitHub API (review, CI); các lệnh kiểm tra ở mục 6 |
| Giới hạn | Dữ liệu game của TV2 (raw, clean, chunk, Qdrant) **không có trên máy lập báo cáo**: trong Git chỉ có golden set. Mọi số liệu dữ liệu dưới đây lấy từ handover của TV2/TV3, chưa được đối chiếu lại trên artifact |

## 1. Tóm tắt

- **Trello:** 13/13 thẻ S2 đã tick đủ checklist và nằm ở cột *Review / QA*. Thẻ mục tiêu sprint còn thiếu mục *Golden set v1 (60 câu)*. Thẻ *Sprint 2 Review & Retro* chưa tick mục nào.
- **Repo:** cả 13 thẻ có code/tài liệu trên `develop`. CI trên `b0f10a1` xanh (backend, web, bot).
- **Chưa đạt Definition of Done:** cả 13 PR của S2 (#30–#44) đều **0 lượt review**. Nhiều PR do chính tác giả tự merge. DoD yêu cầu ít nhất 1 người approve, nên chưa thẻ nào được kéo sang Hoàn thành.
- **Dữ liệu (theo handover):** 4.164 trang base + SotE đã crawl, clean và chunk thành 23.765 chunk, nạp PostgreSQL. 18.368 chunk tiếng Anh đã index vào Qdrant. Retrieval warm có median 32 ms.
- **Chatbot đã chạy được end-to-end** ở chế độ `rag` và `llm_only`, sớm hơn kế hoạch S3. Nhưng API **chưa có xác thực và giới hạn tốc độ**, và web đang được mở qua LAN/VPN (mục 5).
- **Phạm vi sản phẩm đã đổi hai lần trong sprint** (mục 4). Team cần chốt chính thức trong buổi Review.

## 2. Kết quả theo thành viên

| Thành viên | Thẻ S2 | Kết quả chính (theo handover) | PR |
|---|---|---|---|
| **TV1** Hoanbucon | Schema PG & migrations; API contract v1 + mock; Lỗi & logging | 8 bảng + migration `0001`; `/chat`, `/chat/stream`, `/feedback`, `/conversations/{id}`; lỗi chuẩn `{code, message, request_id}`; `docs/api/openapi.json` được CI kiểm tra; audit sửa commit-sau-response và id ổn định | #28, #29, #30 |
| **TV2** Nông Hữu Thịnh | Crawl toàn bộ wiki.gg; Làm sạch; Chunking + metadata | Inventory 4.179 ứng viên → 4.164 raw (7 trang lỗi ảnh, vẫn có text); clean `s2-full-v2`: 22.419 record, 20.235 eligible; chunk `s2-full-v1`: **23.765 chunk**, tối đa 450 token, nạp PG 4.164 docs, chạy lại không đổi | #31, #36, #37, #38 |
| **TV3** Nguyễn Quang Minh | fanapis → entities; Embedding & indexing; Retrieval hybrid; Golden set v1 | Index 18.368 chunk EN trong ~16 phút 40 giây; retrieval cold 1,86 s, warm median/p95 **31,9 / 57,9 ms**; pipeline LangChain `mock`/`llm_only`/`rag`; golden set **60 câu** (38 VI/22 EN) | #34, #35, #39, #40, #41, #42 |
| **TV4** Vũ Ngọc Quý | UI chat cơ bản; api.ts viết tay; Bot /ask gọi API mock | Web theo OpenAPI, integration test 9/9 với backend mock; bot `/ask` gửi `external_ref`, embed có nguồn; web 21/21 test, bot 21/21 test | #33, #44 |

### Sản phẩm bàn giao của sprint (thẻ mục tiêu)

| Sản phẩm | Trạng thái |
|---|---|
| Dữ liệu wiki.gg đầy đủ trong Qdrant (dense + BM25) | Đạt theo handover. Chỉ 18.368/23.765 chunk được index: 5.397 chunk ngôn ngữ khác (ja, unknown…) bị loại theo chính sách `pilot/en` |
| Schema PostgreSQL + migrations | Đạt, test tích hợp với Postgres thật |
| OpenAPI v1 + endpoint mock | Đạt |
| UI chat & /ask gọi API mock | Đạt |
| Golden set v1 (60 câu) | **Chưa đạt:** đủ 60 câu nhưng phiếu review chéo của TV2 ghi **60 pending, 0 approved**. SRS đặt mục tiêu ≥100 câu cho FR-EVAL-01 |

## 3. Trello và repo không khớp

| Điểm | Chi tiết |
|---|---|
| Review PR | Checklist Trello đã tick, nhưng 0/13 PR có review trên GitHub |
| Golden set | Thẻ TV3 tick 4/4 (gồm "TV2 review chéo"), nhưng sidecar review ghi 0 approved |
| Thẻ fanapis → entities | Tick 3/3. Báo cáo này chưa kiểm tra bảng `entities` có dữ liệu (cần DB của TV3) |
| Retro | Thẻ *Sprint 2 Review & Retro* 0/5 |

## 4. Thay đổi phạm vi cần team xác nhận

1. **Base game → base + Shadow of the Erdtree.** Ngoại lệ được duyệt ngày 29/10, đã ghi vào ADR-004 và SRS. `game_scope` của corpus là `elden_ring`, còn `release_scope` mới là nhãn heuristic (base_candidate, sote_candidate, unknown). Retrieval chế độ `pilot` nhận cả `base` và `elden_ring`. Bản export Word của kế hoạch chưa sinh lại.
2. **Chatbot lore → trợ lý Elden Ring** (gameplay, build, vị trí, chiến thuật boss). Thay đổi này nằm trong handover TV3 ngày 29/10, **không có thẻ CHANGE-REQ**. Nó ảnh hưởng tới bộ golden set (câu build/gameplay không còn là ngoài phạm vi), báo cáo môn NLP và câu chữ trên web và bot.

Đề nghị: trong buổi Review, chốt cả hai bằng thẻ CHANGE-REQ rồi cập nhật SRS §1.2, README và golden set cho khớp.

## 5. Kết quả code review (Sprint 1 + Sprint 2)

Review toàn bộ backend runtime (API, service chat, pipeline RAG, retrieval, encoder, store), loader ingest, bot `/ask` và client web. Không chạy LLM, không tải model. Xếp theo mức độ.

| # | Mức | Vấn đề | Vị trí | Hướng xử lý |
|---|---|---|---|---|
| 1 | Cao | **API gọi LLM thật không có xác thực và rate-limit.** Chế độ `rag`/`llm_only` đã chạy, web được mở qua LAN/VPN. Ai vào được web đều tốn tiền DeepSeek không giới hạn (NFR-COST-01) | `app/api/deps.py`, `app/main.py` | Trước khi mở rộng truy cập: rate-limit theo IP/`external_ref` bằng Redis và kiểm tra `X-Service-Token` cho bot (kéo một phần S4 lên S3) |
| 2 | Cao | **Bot không bao giờ gửi `conversation_id`**, nên mỗi `/ask` tạo hội thoại mới: câu hỏi tiếp theo mất ngữ cảnh (FR-CHAT-03). Kho hội thoại trong RAM dùng chung giới hạn 500 cho web và bot, nên một server Discord đông sẽ đẩy hội thoại web ra ngoài | `bot/src/commands/ask.ts:43`, `app/services/chat.py` (`_state`) | Backend tra hội thoại theo `(channel, external_ref)` khi không có `conversation_id`; chuyển lưu hội thoại sang PostgreSQL (schema đã có) ở S3 |
| 3 | Trung bình | **Timeout bot 30 s ngắn hơn backend** (LLM timeout 60 s × tối đa 2 lần thử lại). Bot báo lỗi trong khi backend vẫn chạy tiếp và tính tiền token | `bot/src/api/client.ts:38`, `core/config.py:63-64` | Đặt tổng thời gian chờ phía backend nhỏ hơn timeout của bot (vd. LLM 20 s, 1 lần thử lại), hoặc tăng timeout bot cho khớp |
| 4 | Trung bình | **Câu hỏi dài hợp lệ có thể trả 503.** Hợp đồng cho phép 2.000 ký tự; nếu câu hỏi vượt 512 token E5, encoder ném lỗi và retriever đổi thành 503 "Không thể truy vấn kho tri thức" | `core/encoders/onnx.py` (kiểm tra 512 token), `app/rag/retriever.py` (`_search`) | Với truy vấn (`query=True`) thì cắt bớt thay vì báo lỗi; giữ kiểm tra chặt cho passage khi index |
| 5 | Trung bình | **Tắt spoiler thì không bao giờ có câu trả lời.** Corpus chưa có `spoiler_level`, nên `spoilers=false` loại mọi chunk và luôn trả "chưa tìm được nguồn". Web và bot đang gửi cố định `spoilers: true` nên lỗi chưa lộ ra | `core/corpus.py` (`exclusion_reason`) | Ghi rõ trong OpenAPI là tùy chọn chưa hỗ trợ, hoặc trả 422 cho tới khi có nhãn (FR-ING-11, S4) |
| 6 | Trung bình | **Index lại không xóa point cũ.** `index_chunks` chỉ upsert; khi chunk lại làm số chunk của trang giảm hoặc id đổi, point cũ vẫn nằm trong Qdrant và vẫn được trích dẫn | `ingest/indexing.py` (`index_chunks`) | Trước khi upsert một document thì xóa point theo `document_id` (đã có payload index), hoặc đối chiếu tập id |
| 7 | Trung bình | **Stream hiển thị chữ trước khi kiểm tra bằng chứng xong.** Câu được gửi dần sau khi qua kiểm tra trích dẫn từng phần; nếu kiểm tra cuối (quote nguyên văn, khớp evidence) thất bại, người dùng đã đọc đoạn chưa được xác minh rồi mới nhận lỗi | `app/rag/generator.py` (`Generator.stream`) | Web gạch hoặc ẩn phần đã hiện khi nhận event `error`; ghi rõ giới hạn này trong báo cáo đánh giá |
| 8 | Thấp | **Hash Discord user ID không có salt.** SHA-256 của snowflake có thể dò ngược bằng cách thử các ID đã biết, nên chưa phải ẩn danh thật (NFR-PRIV-01) | `bot/src/commands/ask.ts:39` | Dùng HMAC với secret của bot |
| 9 | Thấp | **Mỗi câu hỏi tốn thêm 2 lượt gọi Qdrant** (`collection_exists` và `get_collection`) qua `store.ready()` | `core/vector/store.py:19` | Kiểm tra collection một lần lúc khởi động hoặc cache kết quả |
| 10 | Thấp | **Hai loader PostgreSQL gần giống nhau** (`ingest/chunk/postgres.py` bản pilot và `load_full.py` bản full). README chỉ dùng `load_full`, nhưng test tích hợp vẫn kiểm bản cũ | `backend/ingest/chunk/` | Xóa bản pilot và chuyển test sang `load_full` |

Đã xử lý trong S2 (PR #30): commit DB chạy sau khi đã trả response (lỗi bị che sau 200), id document ngẫu nhiên, câu hỏi toàn khoảng trắng. Các rủi ro còn treo từ đợt audit đó: chưa kiểm tra chủ sở hữu khi đọc `/conversations/{id}` theo kênh (chế độ live đã kiểm `channel`/`external_ref`, mock thì chưa), JSON 500 nằm ngoài CORS, index trùng `ix_chunks_document_id`.

## 6. Kiểm tra đã chạy khi lập báo cáo

Trên `develop` tại `b0f10a1`, máy Windows của TV1:

| Lệnh | Kết quả |
|---|---|
| `ruff check .`, `ruff format --check .` (backend) | Đạt, 166 file |
| `python -m scripts.export_openapi --check` | Đạt (sau khi cài lại dependency, xem dưới) |
| `pytest` (backend) | **311 passed, 20 skipped**, 15 deselected. 20 ca skip vì mẫu raw không nằm trong Git |
| `pytest -m integration` (Postgres/Redis/Qdrant local) | **15 passed** |
| `npm test` web / bot | **21/21** và **21/21** |
| `npm run typecheck` web / bot | Đạt |
| CI GitHub trên `b0f10a1` | backend, web, bot: success |

Venv local thiếu `langchain_core` sau khi kéo `develop` (S2 thêm LangChain). Phải chạy `pip install -r requirements-dev.txt -c constraints.txt` thì backend mới import được. **Mọi thành viên cần cài lại dependency sau khi pull.**

Không chạy: notebook, crawl, embedding, index, gọi DeepSeek; không kiểm tra artifact dữ liệu và collection Qdrant (không có trên máy).

## 7. Việc cần làm trước khi đóng Sprint 2

1. Mỗi PR #30–#44 có ít nhất 1 người review (có thể review gộp theo thành viên); sau đó mới kéo thẻ sang Hoàn thành.
2. TV2 review chéo golden set (60 câu đang pending), ưu tiên 30 câu mới và ID 027.
3. Chốt hai thay đổi phạm vi ở mục 4 bằng thẻ CHANGE-REQ.
4. Buổi Review & Retro: demo số liệu index, web và bot; chạy thử truy vấn hybrid trên dữ liệu thật.
5. TV2 chia sẻ artifact dữ liệu (kèm checksum) để các máy khác tái lập được index; dữ liệu không đưa lên Git.

## 8. Chuẩn bị Sprint 3

- **Ưu tiên an toàn chi phí (mục 5, #1)** trước khi mở chatbot thật cho người ngoài nhóm.
- Lưu hội thoại và tin nhắn vào PostgreSQL thay kho RAM, tra cứu theo `external_ref` (#2), tạo session riêng trong generator cho route SSE.
- Thống nhất timeout giữa bot, web và backend (#3).
- Đo retrieval (Recall@5, MRR) trên golden set đã được review, không dùng bộ đang pending để kết luận chất lượng.
- Quyết định có index 5.397 chunk không phải tiếng Anh (ja, unknown) hay giữ chính sách `pilot/en`.
