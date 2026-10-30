# Đo index toàn bộ corpus được chọn

Ngày 30/10/2026, Asia/Saigon. Nhánh `feature/s2-tv3-full-index-benchmark` từ develop `dbc6c6f`.
Người dùng cho phép chạy embedding lần nữa và upsert để đo đầy đủ cho demo, sau đó viết handover.

## Phạm vi phép đo

Một lượt **full re-embedding + upsert trên collection đã có**, không resume, không bỏ qua point đã tồn tại.
Toàn bộ ở đây là toàn bộ tập policy pilot/en chọn, không phải mọi ngôn ngữ của artifact:

- Input: `backend/data/chunk_runs/s2-full-v1/chunks.jsonl`.
- Tổng 23.765 chunk; chọn 18.368 EN; 5.397 ngôn ngữ khác không được chọn, không đổi nhãn unknown.
- Collection hiện tại của ứng dụng, không drop/recreate hoặc đổi tên.
- E5 `intfloat/multilingual-e5-small`, ONNX/FastEmbed; dense 384 cosine, sparse Qdrant/bm25 IDF.
- Thread 4, batch 8, CPU AMD Ryzen 7 5800H (8 core/16 logical processors).
- Model weights đã cache trên máy; encoder mới bắt đầu chưa load model, first load nằm trong embedding timing.
- Snapshot E5: `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Hash input trước chạy: `95794a89485e6f86ff320ee9b2a9a707a794e1bdc040162f0b41e5b2c208d03e`.

Đây không phải benchmark cold download hoặc tạo collection trống lần đầu. Máy có tác vụ khác,
không phải môi trường benchmark CPU độc lập. Docker startup nằm ngoài thời gian đo.
Không gọi LLM, chạy notebook/crawl hoặc sửa `.env`/artifact.

## Cách đo

Script [benchmark_index.py](../../backend/scripts/benchmark_index.py) gọi trực tiếp `index_chunks` đang dùng
trong CLI production, với wrapper đo thời gian encoder/upsert. Giữ schema, point ID và policy nguyên vẹn.
Script yêu cầu `--allow-write`; không có flag thì dừng trước Settings/client/model.

JSON được cập nhật atomic khoảng mỗi 30 giây và sau xác minh; trạng thái running/failed không được coi là hoàn tất.
Đếm embedded_records và completed_records riêng; upsert chỉ tính vào completed sau khi server acknowledge.

| Chỉ số | Định nghĩa |
|---|---|
| preflight_seconds | Đọc/validate toàn bộ JSONL với tokenizer local, không inference |
| embedding_seconds | Tổng thời gian E5 dense + BM25 từng batch; gồm lần load model đầu |
| upsert_seconds | Tổng thời gian chờ batch upsert acknowledged |
| index_seconds | Lượt `index_chunks` đầy đủ: prevalidation, schema check, embedding, upsert và ghi progress |
| verification_seconds | Count chính xác, payload mẫu và hash nguồn sau index |
| total_elapsed_seconds | Từ trước preflight đến sau final checks/client cleanup, gồm overhead; không gồm startup Docker/Python imports |

Count trước/sau giống nhau hỗ trợ kiểm idempotency về cardinality, không chứng minh mọi vector có chất lượng semantic.
Payload đối chiếu mẫu 8 point, không gọi đó là đối chiếu toàn bộ payload. Không đo retrieval accuracy/answer quality.

## Kết quả

**Hoàn tất, status=complete, tiến trình exit code 0.** Chạy liên tục từ 23:03:29 đến 23:20:18 ngày 30/10/2026.
Số liệu gốc ở [JSON benchmark](2026-10-30_full-index-benchmark.json); bảng dưới làm tròn 3 chữ số thập phân.

| Chỉ số | Kết quả |
|---|---:|
| Index đầy đủ — `index_seconds` | **999,802 giây ≈ 16 phút 40 giây** |
| Tổng có preflight/final checks/cleanup | **1.009,263 giây ≈ 16 phút 49 giây** |
| Preflight, kiểm token local | 9,011 giây |
| Embedding dense + sparse, gồm load model | 962,445 giây |
| Tổng batch upsert | 36,692 giây |
| Final verification | 0,075 giây |
| Tốc độ trong index | 18,372 chunk/giây |
| Embedded / upsert thành công | 18.368 / 18.368 |
| Số batch | 2.296 |
| Count collection trước / sau | 18.368 / 18.368 |
| Payload 8 point sau ghi khớp input | true |
| Payload 8 point cũ giữ nguyên, gồm timestamp | true |
| SHA-256 source giữ nguyên | true |

Collection: `indexbeast_tv3_integration_20261029_c1871afc`; không đổi cấu hình ứng dụng.
Không có invalid hoặc lỗi upsert; tất cả bản ghi được chọn đã encode lại, không dùng vector kết quả cũ để skip.
Tổng embedding/upsert là thành phần của index_seconds, không cộng thêm lần nữa vào thời gian index.
Total có thêm preflight, prechecks/client lifecycle và kiểm cuối, nên không bằng riêng index_seconds.

Phép đo này hoàn thành mục đo thời gian trọn lượt cho tập pilot/en phục vụ demo. Không thay thế benchmark
index trên collection rỗng, đa ngôn ngữ hoặc môi trường server khác. Không đánh giá chất lượng trả lời chatbot.

Sau khi benchmark kết thúc mới chạy unit tests để tránh thêm tải test vào phép đo: **317 passed, 1 warning**,
15,90 giây. Có 5 case benchmark dùng encoder/client giả; toàn suite chỉ collect `tests/unit` với cấu hình backend.
Warning dự kiến về payload index của Qdrant memory. Ruff check, format (161 file), OpenAPI,
UTF-8/local links và `git diff --check` đạt. Không đổi dependency, không chạy lại pip check.

## Lệnh đã chạy

Từ backend (inference CPU và ghi Qdrant thật):

```powershell
.venv/Scripts/python.exe -u -X utf8 -m scripts.benchmark_index --allow-write --input data/chunk_runs/s2-full-v1/chunks.jsonl --tokenizer models/notebook-fastembed/models--intfloat--multilingual-e5-small/snapshots/614241f622f53c4eeff9890bdc4f31cfecc418b3/tokenizer.json --report ../docs/testing/2026-10-30_full-index-benchmark.json
```

Script không ghi đè report đã tồn tại. Muốn tự đo lần khác, đổi tên report JSON mới.
Không cần chạy lại benchmark/index để demo nếu collection vẫn còn và cấu hình ứng dụng trỏ đúng.
Handover ở [bàn giao phép đo](../handover/2026-10-30_s2-tv3_do-thoi-gian-index-toan-bo.md).
