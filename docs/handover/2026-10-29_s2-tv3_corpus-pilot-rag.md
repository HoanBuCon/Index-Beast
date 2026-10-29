# Bàn giao tích hợp corpus pilot vào RAG LangChain

TV3 — MinhMuc, nhóm 4 Hollows. Ngày 29/10/2026, Asia/Saigon.

## Phạm vi và Git

- Nhánh: `feature/s2-tv3-corpus-pilot-rag`, đích review `develop`; không merge trong tác vụ này.
- Người dùng đã yêu cầu commit và đẩy nhánh sau giai đoạn làm local. Ghi chú “chưa commit/push” trong
  báo cáo kiểm thử phản ánh thời điểm kết thúc kiểm thử, trước yêu cầu Git mới này.
- Fetch trước khi commit xác nhận `origin/develop` đã là ancestor của HEAD, không cần rebase lại.
- Không cập nhật Trello, không đánh dấu task Done, không sửa dữ liệu gốc hoặc SRS/ADR cũ.
- `.env`, model và Qdrant data không nằm trong commit. Máy khác cần cấu hình và index riêng.

## Code và policy

- `backend/core/corpus.py`: policy pilot/en dùng chung ở admission, retrieval và context; giữ review status,
  release/game metadata và unknown. Admission kỹ thuật không tương đương approval hoặc xác minh lore.
- `backend/ingest/indexing.py`, `backend/ingest/__main__.py`: preflight JSONL, thống kê lựa chọn/lỗi,
  CLI index/dry-run, không tạo model/client trong dry-run. Giữ artifact ID và mapping Qdrant hiện có.
- `backend/core/vector/`, `backend/core/encoders/onnx.py`: E5 small ONNX, dense 384 cosine + BM25 IDF,
  hybrid RRF, prefix đúng một lần, thread cấu hình được và upsert idempotent.
- `backend/app/rag/`, `backend/app/services/factory.py`: LangChain LCEL, top-5, scope/prompt mới,
  metadata đầy đủ; model chọn evidence ID, backend lấy quote nguyên văn và kiểm citation.
- Settings, `.env.example`, Compose đồng bộ flag thinking và encoder thread. Mặc định code vẫn mock;
  thinking RAG mặc định false, chỉ bật rõ ràng khi triển khai.
- `backend/scripts/check_retrieval.py` kiểm retrieval thật; `run_live_acceptance.py` chỉ gọi trả phí khi
  có `--allow-paid`, không chạy qua pytest. Tests liên quan nằm trong `backend/tests/unit/`.

Corpus được phép chứa lore Elden Ring liên quan, gồm DLC; không tự gộp canon hoặc đoán unknown thành base.
Giữ filter scope/source/lang, từ chối instruction injection/gameplay optimization theo mục tiêu lore.
Spoiler thiếu nhãn không được coi là an toàn. Không khôi phục tùy tiện các section đã excluded khỏi artifact.

## Cách sử dụng

Hướng dẫn đầy đủ và lệnh từ backend ở [RAG README](../../backend/app/rag/README.md).
Artifact tích hợp: `backend/data/chunk_runs/s2-full-v1/chunks.jsonl`.
Chạy dry-run trước index; cùng policy/lang/collection ở index và API. Collection không tự đi theo Git.
Để chat trên máy đã nạp dữ liệu, khởi động lại API với `.env` hiện tại, không cần index lại.
Không đưa key vào frontend hoặc commit `.env`. API không cho client tự chọn chat mode/policy.

## Kiểm chứng đã thực hiện

- Baseline 201 unit test; cuối cùng **259 passed, 1 warning** (Qdrant memory payload index).
- Ruff lint/format, OpenAPI, pip check và Git whitespace check đạt.
- Artifact 23.765 bản ghi; chọn EN 18.368, không chọn do ngôn ngữ 5.397, invalid 0.
- Đã chạy embedding/index thật với quyền người dùng, Qdrant count đúng 18.368. Hash artifact giữ nguyên.
- Upsert lại mẫu 8 point không đổi count hoặc payload, kể cả timestamp.
- DeepSeek thinking/non-thinking gọi thật HTTP 200; QA cuối 10/10 câu đạt tiêu chí kỹ thuật,
  8 câu có nguồn và 2 câu ngoài phạm vi/thiếu bằng chứng; SSE 3/3.
- History 200, feedback 204, cách ly channel 404; llm_only thật không trả nguồn/grounding giả.
- API tạm đã dừng sau kiểm thử; hạ tầng Docker và collection giữ lại. Chưa kiểm frontend/Discord Gateway thật.

Chi tiết, kết quả từng lượt và giới hạn ở [báo cáo kiểm thử](../testing/2026-10-29_rag-integration-report.md).
Không tự chạy lại trả phí chỉ để commit. Kiểm thử mới cho thao tác Git chỉ là kiểm tra tĩnh và an toàn secret.

## Sự cố và giới hạn

Lượt index đầu được dừng chủ động để tuning rồi xác minh phần đã ghi và tiếp tục đủ dữ liệu.
Ba lượt QA đầu có lỗi đại từ/JSON/citation/SSE; dữ liệu lỗi được giữ, không gọi chúng là đạt.
Đã sửa gate đại từ, evidence ID phía server, thêm thinking riêng RAG và tăng budget ở máy thử.
Validation citation/quote không chứng minh entailment; 10 câu chưa là benchmark lore độc lập.
History/feedback vẫn RAM; chưa kiểm API container Linux, chất lượng dài hạn, frontend hoặc bot Discord thật.
Nhóm cần đồng bộ `docs/02_SRS.md`, `docs/adr/004-base-game-scope.md`, đối chiếu ADR-003/kiến trúc/planning
với quyết định corpus mới. Handover cũ giữ giá trị lịch sử.
