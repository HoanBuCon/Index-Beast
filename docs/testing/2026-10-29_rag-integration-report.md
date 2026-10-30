# Kiểm thử IndexBeast với corpus và DeepSeek thật

Ngày 29/10/2026, múi giờ Asia/Saigon. Nhánh `feature/s2-tv3-corpus-pilot-rag`.
Người dùng đã cho phép sửa `.env`, chạy embedding/index và gọi DeepSeek thật; chưa yêu cầu commit/push.

## Trạng thái

Đã hoàn tất offline, index corpus thật và smoke test DeepSeek thật. Lượt QA cuối đạt các tiêu chí kỹ thuật
đã đặt ra; ba lượt trước có lỗi và được giữ nguyên trong báo cáo JSON. Chưa phải đánh giá lore độc lập.

## Offline và preflight

- Baseline trước tích hợp: **201 unit test đạt**; sau policy: **242**; kết thúc sửa lỗi thực tế: **259 passed, 1 warning**, 12,69 giây.
- Ruff check/format, OpenAPI và pip check đạt. Warning dự kiến: Qdrant memory không thực thi payload indexes như server.
- Dry-run toàn bộ 23.765 bản ghi, chọn 18.368 tiếng Anh; 5.397 không được chọn do ngôn ngữ; 0 bản ghi hỏng.
- Đã đếm token bằng tokenizer E5 local; giữ nguyên artifact và ID. Không gán approval giả.
- SHA-256 artifact: `95794a89485e6f86ff320ee9b2a9a707a794e1bdc040162f0b41e5b2c208d03e`.

## Cấu hình và hạ tầng đã kiểm tra

Container cũ còn publish cổng 5433/6333/6379, lệch quy ước/config backend. Đã recreate ba service với
volume PostgreSQL `index-beast_pgdata` và Qdrant `index-beast_qdrant` giữ nguyên. Không chạy migration hoặc xóa volume.
Redis là cache không có volume. Không thay mật khẩu/token/key.

| Thành phần | Cấu hình sau cập nhật |
|---|---|
| PostgreSQL | `127.0.0.1:15432`, image `postgres:18.6-bookworm` |
| Qdrant | `127.0.0.1:16333`, image `qdrant/qdrant:v1.19.2` |
| Redis | `127.0.0.1:16379`, image `redis:8.10.2-alpine` |
| API local | `127.0.0.1:18000` |
| Chat/corpus/ngôn ngữ | `rag` / `pilot` / `en` |
| Collection riêng | `indexbeast_tv3_integration_20261029_c1871afc` |
| Cache | `backend/models/notebook-fastembed` |
| Thread / batch | `4` / `8` |
| Rewrite | Tắt |
| LLM | `deepseek-flash`, giữ model từ Settings |
| Thinking RAG / budget | `RAG_THINKING_ENABLED=true`, `LLM_MAX_TOKENS=4096` |
| Evidence | `server_quote_ids_v1`, backend trích nguyên văn từ chunk |

Health probes thực của PostgreSQL/Redis/Qdrant đều đạt. API `/api/v1/health` trả HTTP 200,
`status=ok`, ba checks `true`. DeepSeek `/models` trả 200 và có model đang cấu hình.
Đây là kiểm server Docker của hạ tầng và API Python chạy local, chưa phải kiểm image/container API trên Linux.

## Model và phép đo hiệu năng

FastEmbed E5 thật trả dense 384 chiều, norm mẫu passage/query bằng 1.0; BM25 sparse có term.
Weights ONNX có sẵn, không đổi model:

- `intfloat/multilingual-e5-small`, snapshot `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- ONNX size: 470.268.510 byte.
- ONNX SHA-256: `ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665`.
- FastEmbed `0.9.0`, ONNX Runtime `1.31.0`, Qdrant client `1.19.1`.
- LangChain core `1.7.1`, DeepSeek integration `1.1.1`, OpenAI SDK `3.33.0`.
- Máy đo: AMD Ryzen 7 5800H, 8 core/16 logical processors; có tác vụ khác cùng chạy.

Phép đo trên cùng 32 bản ghi mẫu, max 449 token, model đã warm:

| Thread | Batch | Thời gian embedding 32 bản ghi |
|---:|---:|---:|
| 2 | 32 | 8,775 s |
| 4 | 32 | 5,955 s |
| 4 | 8 | 1,808 s |
| 4 | 16 | 3,177 s |
| 4 | 32, lượt đo batch sau | 5,668 s |

Upsert 32 point đo riêng khoảng 0,124 s. Đây là phép đo cục bộ có nhiễu tải, không phải benchmark toàn diện.
Batch nhỏ giảm padding trên mẫu này. Đã thêm `RAG_ENCODER_THREADS` (mặc định code 2, giới hạn 1–32),
truyền tới encoder của index/retrieval/API; `.env` máy thử đặt 4, batch 8. Không đổi model hay ID.

Lượt index đầu thread 2/batch 32 được dừng chủ động để tuning, không phải crash phần mềm.
Đã đối chiếu metadata của 4.480 point hoàn tất với artifact/policy trước khi bỏ qua chúng và tiếp tục
13.888 bản ghi còn lại bằng cùng `index_chunks`, encoder và QdrantStore. Không xóa collection hoặc tính lại ID.
Kết quả cuối, count và phép thử idempotency ghi ở [JSON index](2026-10-29_rag-index-results.json).

Qdrant count cuối **18.368**, bằng số bản ghi được chọn. Phần tiếp tục mất **809,058 giây** cho 13.888
bản ghi, không phải thời gian toàn bộ lượt index. Upsert lại mẫu 8 bản ghi không tăng count hoặc đổi payload,
kể cả timestamp. SHA-256 dữ liệu nguồn giữ nguyên. Collection trước khi thử chưa tồn tại; không đụng collection khác.

Mapping giữ nguyên `artifact-point-v1`: artifact `chunk_id=uuid5(doc_id, ordinal)` liên kết document;
Qdrant point ID là UUID riêng từ namespace và chuỗi `artifact-point-v1:{document_id}:{artifact_chunk_id}`.
Giữ artifact ID, ordinal và metadata trong payload, không lấy point ID làm chunk UUID PostgreSQL. Không ghi PostgreSQL.

## DeepSeek thinking và non-thinking đã chạy thật

Endpoint `/api/v1/dev/llm/test`, câu hỏi ngắn về Ranni, max_tokens 1024, reasoning_effort low khi thinking.

| Mode | HTTP | Finish reason | Input / output / total token | Reasoning token | Thời gian HTTP |
|---|---:|---|---|---:|---:|
| Non-thinking | 200 | stop | 33 / 36 / 69 | Không cung cấp | 1,479 s |
| Thinking | 200 | stop | 58 / 93 / 151 | 57 | 1,262 s |

Cả hai trả câu trả lời cuối không rỗng. Thinking có reasoning riêng từ provider nhưng không lưu nội dung
reasoning vào báo cáo, không ghi key/header. Các token trên chỉ thuộc hai request dev này, không phải tổng token của mọi bài test.

## QA, SSE, llm_only và contract

Đã chạy sau khi count đủ corpus. Bộ QA có 5 câu VI, 5 câu EN, gồm lore, DLC/quan hệ,
ngoài phạm vi và quan hệ không có đủ bằng chứng. Không đưa câu hỏi/đáp án kiểm thử vào corpus.

Runner thủ công: `backend/scripts/run_live_acceptance.py`. Phải chỉ định `--allow-paid`, URL chỉ cho loopback
không có credentials/query. Pytest chỉ kiểm guard, không thực hiện các request trả phí này.
Runner kiểm count đủ corpus trước QA, dừng nếu có ba lỗi API liên tiếp và ghi kết quả từng bước.
Không lưu private reasoning; snapshot retrieval chỉ có metadata, hash và excerpt ngắn.

Lịch sử ở [JSON đầy đủ](2026-10-29_rag-live-results.json),
[tổng hợp tiêu chí](2026-10-29_rag-live-summary.json) và [SSE lặp lại](2026-10-29_sse-repeat-results.json).
Tổng hợp được tính lại từ dữ liệu lưu; không gọi HTTP 200 hoặc exit code của runner cũ là đủ để đạt.

| Lượt | Thinking / budget | HTTP 200 | Kết quả |
|---|---|---:|---|
| 1 | false / 2048 | 10/10 | Không đạt: nhận nhầm đại từ EN01/EN03, EN05 grounded sai, SSE lỗi |
| 2 | false / 2048 | 6/10 | Không đạt: JSON/citation/evidence không hợp lệ, SSE lỗi |
| 3 | true / 2048 | 7/10 | Không đạt: ba lỗi 502 trước validation; SSE quote không nguyên văn |
| 4 | true / 4096 | 10/10 | Đạt: 8 câu có nguồn, 2 câu từ chối/thiếu bằng chứng đúng contract; SSE hoàn tất |

Ở lượt 3 chưa thu finish_reason nên chưa chứng minh lỗi 502 do hết token. Thinking, budget và evidence protocol
đã cùng thay đổi qua các lượt; chưa có thí nghiệm tách riêng tác động từng yếu tố.

Kết quả lượt cuối, từ 19:39:36 đến 19:40:28 ngày 29/10/2026:

| ID | Nội dung | Grounded / số nguồn | HTTP / giây |
|---|---|---|---|
| VI01 | Ranni và cha mẹ | true / 2 | 200 / 4,348 |
| VI02 | Godwyn, Prince of Death | true / 2 | 200 / 4,290 |
| VI03 | Messmer và phạm vi bản mở rộng | true / 2 | 200 / 8,783 |
| VI04 | Miquella và St. Trina | true / 2 | 200 / 7,453 |
| VI05 | Yêu cầu viết Fibonacci | false / 0 | 200 / 0,006 |
| EN01 | Melina, tham chiếu “she” | true / 2 | 200 / 4,027 |
| EN02 | Greater Will | true / 2 | 200 / 3,242 |
| EN03 | Rellana và Rennala | true / 2 | 200 / 4,394 |
| EN04 | Twinbird và Deathbirds | true / 3 | 200 / 3,111 |
| EN05 | Quan hệ Nightreign với ending Ranni | false / 0 | 200 / 1,444 |

Trung bình 10 câu **4,110 giây**, riêng 8 câu lore **4,957 giây**; lớn nhất 8,783 giây.
Quote của cả 8 câu có nguồn đều tìm thấy nguyên văn trong artifact, đúng URL nguồn server.
Đọc đáp án cho thấy VI01/EN03 trả lời đúng quan hệ được hỏi; VI04 phân biệt lời thoại nguồn;
EN04 giữ cách diễn đạt “is said to”; EN05 nói rõ chưa có bằng chứng và không trích nguồn gây hiểu nhầm.
VI03 giữ sự chưa chắc chắn của metadata release, nhưng câu trả lời còn dài và dè dặt; metadata candidate
chưa cho phép khẳng định release đã được thẩm định. Đây là nhận xét đọc smoke test, không phải điểm correctness độc lập.

SSE đạt **3/3**: một câu VI trong QA cuối, hai câu EN lặp lại (3,884 và 2,452 giây), có token, nguồn,
done grounded=true và không error. Các lượt lỗi trước chỉ phát error, không done thành công.
History HTTP 200 với 2 message, feedback 204, truy cập hội thoại khác channel trả 404.
`llm_only` gọi DeepSeek thật qua TestClient ASGI: HTTP 200, grounded=false, sources rỗng.
Channel Discord chỉ được mô phỏng qua API, chưa kết nối Discord Gateway hoặc kiểm UI web.

### Các lỗi đã sửa trong quá trình thử

- Gate đại từ không còn từ chối câu có tên nhân vật đứng trước “she”; vẫn hỏi lại khi tham chiếu đầu câu chưa rõ.
- Prompt trả lời trọng tâm, không lấy citation liên quan để biến câu thiếu bằng chứng thành grounded=true.
- Thêm flag thinking riêng cho RAG và tăng budget local; không đổi mặc định mock hoặc buộc llm_only thinking.
- Model chọn `quote_id` từ evidence units backend cung cấp; backend tự lấy đoạn nguyên văn, kiểm index,
  citation/evidence-set và insufficient. Quote literal cũ vẫn được hỗ trợ. ID sai hoặc mismatch vẫn bị từ chối.
  Không sửa chunk/index hoặc dùng fuzzy matching để hợp thức hóa quote sai.
- Validator chỉ log mã lỗi tĩnh. Runner mới exit 1 nếu vi phạm tiêu chí, kể cả response HTTP 200.

Kiểm citation/quote này không chứng minh entailment hay độ đúng mọi mệnh đề. Corpus pilot/en giữ review status
gốc và unknown, không tự approval; retrieval/context/index dùng chung policy. Thiếu spoiler_level không coi là an toàn.
Mẫu nhỏ, chưa benchmark reranker, prompt injection toàn diện hoặc độ ổn định dài hạn. History/feedback vẫn RAM.
Không tổng hợp chi phí/token các request chat vì API chat không cung cấp đầy đủ usage. Không lưu private reasoning/key.

## Tái lập

Từ `backend/`, với `.env` và hạ tầng như trên, lệnh index đầy đủ (có chạy embedding/ghi server):

```powershell
.venv/Scripts/python.exe -X utf8 -m ingest index --input data/chunk_runs/s2-full-v1/chunks.jsonl --policy pilot --languages en --tokenizer models/notebook-fastembed/models--intfloat--multilingual-e5-small/snapshots/614241f622f53c4eeff9890bdc4f31cfecc418b3/tokenizer.json
```

Sau khi API chạy bằng cấu hình `.env`, gọi bài kiểm thử trả phí:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.run_live_acceptance --allow-paid
```

Không cần chạy lại index khi chỉ muốn chat trên collection đã nạp. SRS/ADR phạm vi cũ chưa sửa trong tác vụ này.

API tạm dùng cho kiểm thử ở cổng 18000 được dừng sau khi hoàn tất; Docker và collection được giữ để bạn dùng tiếp.
Để chạy lại API từ backend (giữ `.env` hiện tại):

```powershell
.venv/Scripts/python.exe -X utf8 -m uvicorn --factory app.main:create_app --host 127.0.0.1 --port 18000 --no-access-log
```

Truy cập `http://127.0.0.1:18000/api/docs`. Lệnh này là hướng dẫn khởi động lại; không cần index lại.
Đã thực thi offline tests, dry-run, embedding/index, retrieval và QA thật nêu trên. Không chạy notebook/crawl,
không sửa artifact, không commit/push/merge, không tạo handover riêng. `.env` vẫn gitignored.
Các tài liệu cũ cần nhóm đồng bộ riêng: `docs/02_SRS.md`, `docs/adr/004-base-game-scope.md`;
đối chiếu thêm ADR-003, kiến trúc, techstack và planning. Tác vụ này chưa sửa chúng.
