# Sửa đường dẫn raw trong artifact và nạp dữ liệu trên máy TV1

| | |
|---|---|
| Ngày | 31/10/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `fix/s2-tv1-duong-dan-artifact` (từ `origin/develop` tại `3983b45`, sau PR #53) |
| Căn cứ | Việc #4 trong [đề xuất dữ liệu đã duyệt](2026-10-31_s2-tv1_khao-sat-du-lieu-va-de-xuat.md); chuẩn bị demo Sprint 2 trên máy TV1 |

## Lỗi

`documents.jsonl` của chunk `s2-full-v1` ghi `source_snapshot` tuyệt đối theo máy TV2 (`D:\Index-Beast\backend\data\raw\...`). `ingest.chunk.load_full` đọc nguyên đường dẫn đó để kiểm hash raw, nên trên mọi máy khác lỗi `FileNotFoundError` và không nạp được PostgreSQL.

## Đã sửa

- `backend/ingest/chunk/load_full.py`: hàm `local_snapshot()` dùng đường dẫn ghi trong artifact nếu tồn tại; nếu không, tìm cùng file theo phần sau thư mục `raw` trong `data/` hiện tại. Kiểm tra hash raw và revision giữ nguyên, nên không thể nạp nhầm file.
- `backend/tests/unit/test_load_full_paths.py`: 3 test cho đường dẫn máy khác, đường dẫn đang tồn tại và đường dẫn không có `raw`.
- Không đổi artifact, schema hay chunk ID. Không đụng `ingest index`: lệnh này không đọc `source_snapshot` nên vốn chạy được trên máy khác.

## Đã chạy trên máy TV1

| Bước | Kết quả |
|---|---|
| `load_full data/chunk_runs/s2-full-v1 --validate-only` | 4.164 document, 23.765 chunk hợp lệ; 24 giây; 0 ghi DB |
| `load_full data/chunk_runs/s2-full-v1` | 4.164 OK, 0 lỗi, 23.765 chunk; 2 phút 11 giây; job `load_full_chunks` = `succeeded` |
| Đếm lại trong PostgreSQL | documents 4.164; chunks 23.765 (en 18.368, ja 3.447, unknown 1.801…) |
| `ingest index … --policy pilot --languages en --dry-run` | 18.368 nhận, 5.397 loại do ngôn ngữ, 0 invalid; SHA-256 đầu vào `95794a89…d03e` khớp benchmark TV3 |
| Backend unit test | 394 passed; ruff đạt |

`load_full` ghi đè `postgres-report.json` trong thư mục chunk. Bản gốc của TV2 được sao lưu thành `postgres-report.tv2-original.json` cùng thư mục, trước khi nạp.

## Chưa làm (cần người dùng duyệt hoặc tự làm)

- Tải model E5/BM25 vào `backend/models/fastembed` và index 18.368 chunk vào Qdrant `lore_chunks` (khoảng 17 phút CPU theo benchmark TV3).
- `.env` máy TV1 vẫn là bản Sprint 1: chưa có `DEEPSEEK_API_KEY`, `CHAT_MODE` và các biến `RAG_*`. Key phải do người dùng tự điền.
- Qdrant cổng 16333 trên máy TV1 đang chứa 6 collection không thuộc IndexBeast (`character_lore`, `memories`…). `lore_chunks` sẽ được tạo riêng, không đụng các collection đó.
