# TV2 — Audit và sửa dữ liệu phục vụ RAG, 08/11/2026

Tiếp nối sau audit: người dùng đã yêu cầu xóa dữ liệu cũ. Bản S2/trial trung gian
đã xóa; mô tả bảo toàn phía dưới là trạng thái tại lúc audit. Bản cuối và nguồn
được giữ tại delivery/final. Xem [bàn giao dọn dữ liệu](2026-11-08_s3-tv2_ban-cuoi-va-don-du-lieu-cu.md).

## Phạm vi và trạng thái

Người dùng yêu cầu tạo meta prompts, tự audit cấu trúc và khả năng tìm bằng chứng,
sửa data/clean/chunk TV2 trong bản thử riêng; RAG TV3 chỉ đề xuất. Sau làm rõ,
người dùng chọn hoàn tất offline/local, hoãn LLM. Đã thực hiện; không tuyên bố
đánh giá end-to-end. Nhánh `fix/s3-tv2-chat-luong-du-lieu`; chưa commit/push/PR
trong lượt này, chưa merge hoặc đổi manifest production.

## File và quyết định

- `backend/core/text/html_clean.py`, `lore_policy.py`: opt-in gameplay, giữ chỉ số
  có nhãn, dialogue trigger, ngôn ngữ tab, placeholder/editorial review.
- `backend/core/text/chunking.py`: gom infobox vừa cap, context cho bảng dài,
  exact char slices và tránh cắt giữa từ.
- `backend/ingest/transform/full.py`, `chunk/full.py`, `chunk/load_full.py`:
  điều phối version S3, metadata và validation; mặc định clean vẫn policy S2.
- `backend/ingest/debug/readiness_structure.py`, `readiness_retrieval.py`:
  audit toàn bộ và diagnostic E5 local riêng; không chỉnh runtime TV3.
- `backend/tests/unit/test_rag_readiness_clean.py`: regression các ca mất dữ liệu.
- `backend/ingest/README.md`: CLI tái chạy, flag `--gameplay` và giới hạn tích hợp.
- [Meta prompts](../prompts/2026-11-08_tv2-rag-readiness-meta-prompts.md).
- [Báo cáo đầy đủ, kết quả và hạn chế](../testing/2026-11-08_tv2-rag-readiness.md).

## Kết quả thực tế

Full cohort 4.164 trang: 29.405 dòng clean CSV, 40.387 dòng review,
65.593 occurrence ảnh; 31.055 chunk, 30.947/30.947 unit được phủ. Một template
không tạo chunk là chủ ý. 25.607 EN qua index dry-run, invalid 0; validate-only
4.164 documents thành công, không ghi PostgreSQL/Qdrant.

Trong pool nguồn cố định 201 trang, 15 ca thông số từ raw: trước có 1/15 bằng
chứng, sau có 15/15 và tìm đúng bằng chứng nguồn top5 15/15. Đây là diagnostic
đã dùng để sửa lỗi, không phải held-out Recall/MRR hoặc chất lượng toàn hệ thống.
Golden100 còn pending review. Ba câu thiếu căn cứ vẫn có cosine cao; không thể
dùng cosine làm bằng chứng câu trả lời đúng. LLM chưa chạy, API cost 0 USD.

50 mẫu EN cuối: 48 clean / 0 dirty / 2 review do assistant đọc trực tiếp, chưa
human approval. Hai review là Whips thiếu bảng theo sau và War Cry cần ngữ cảnh
đoạn trước. Bảng upgrade/affinity phức tạp chưa được phục hồi toàn bộ; không bảo
đảm có mọi thông số mọi patch. source_updated_at/spoiler_level còn thiếu, 7 media
lỗi, quyền ảnh chưa rõ vẫn cần review. Không sinh text/caption hoặc suy đoán số liệu.

## Artifact local và cách dùng

Điểm vào: `D:/Index-Beast/backend/data/delivery/final/manifest.json`.
Clean: `data/clean_runs/s3-quality-language-20261108/`.
Chunk: `data/chunk_runs/s3-quality-final-20261108/`.
Audit: `data/research_runs/s3-rag-readiness-20261108/`.
Các path rút gọn tính từ backend; data bị Git ignore, chưa được upload GitHub.

Lệnh tái chạy ở README ingest, luôn dùng output mới. Policy mới cần `--gameplay`.
Runner TV1 hiện chỉ auto-select version S2, chưa tích hợp S3; không chỉnh phần
việc TV1 trong nhánh này. Không tự re-index production. TV3 cần thử collection
riêng và kiểm citation/abstention/LLM khi có golden được duyệt.

## Kiểm chứng và bảo toàn

98 unit tests dữ liệu passed, Ruff check/format passed; diff check không lỗi.
CLI opt-in 20 trang mới tạo 711 chunk / 687 unit được phủ. CSV round-trip,
token cap 450/overlap 50, ID/hash/provenance/ảnh và exact source coverage đã kiểm.
711 chunk của lượt CLI20 mới có ID/text/metadata khớp cùng trang trong full run
sau khi bỏ updated_at; kết quả lưu trong rerun-stability.json.
Full backend suite chưa chạy vì thiếu langchain_core, integration DB/LLM chưa chạy.
Weights E5 pinned ONNX được tải cache theo ủy quyền kiểm embedding local; không
API trả phí. Fingerprint 8.330 input full clean kiểm lại không đổi.

Raw/media, corpus S2 và manifest giao S2 giữ nguyên. Stash
`04b001ca2192109ec379ee65dc8ed7b4f407122b` giữ nguyên. Không thay entities/schema,
route, UI hoặc retrieval/LLM runtime của thành viên khác.
