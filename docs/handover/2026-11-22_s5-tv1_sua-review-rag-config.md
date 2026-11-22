# Sửa review S5 · backend RAG/config (agent D2)

Nguồn: `2026-11-17_s5-tv2_ra-soat-ma-toan-he-thong.md`, kiểm lại trên origin/develop (4bb9e46). Nhánh `fix/s5-tv1-review-rag-config`.

## Đã sửa

- **#6 Chính sách domain Tavily.** Giữ mặc định đã đo `prefer`; SRS FR-RET-08 mô tả `prefer` mặc định, `restrict` tùy chọn. Thêm `web_hit_allowed(hit, settings)` (`adapters/tavily.py`), dùng ở `admit()` của Agent và ở `ChatPipeline._context` (điểm chung mọi evidence web, kể cả hit lấy lại từ `state["web_hits"]`). Ở `restrict`, hit ngoài allowlist bị loại. Hiện không còn đường khôi phục web evidence qua các lượt (task_plan đã bị xóa), nên bộ lọc là phòng thủ tại điểm chung.
- **#10 Catalog ảnh.** Mặc định `rag_images_catalog` = `data/delivery/final/clean/images.csv`. `ImageCatalog.preflight()` chạy trong lifespan: khi ảnh bật mà catalog hoặc documents thiếu/không đọc được thì log đúng một cảnh báo kèm đường dẫn; ảnh vẫn tắt qua `catalog_unavailable`, chat text tiếp tục. Agent C cần đồng bộ compose và `.env.example`.
- **#11 Tavily phụ thuộc RAG.** `web_content.py` (chỉ dùng `re`) chuyển sang `core/text/web_content.py` (git mv, hành vi giữ nguyên). Test mới quét `app/adapters` và khẳng định không import `app.rag`.
- **#21 Vòng import ảnh.** `CACHE` và `FORMATS` nằm ở `app/services/image_cache.py`; `images.py` và `answer_media.py` cùng import từ đó, bỏ import trì hoãn. Test `test_answer_media` patch `images.CACHE`.
- **#22 Schema Qdrant kiểm hai lần.** `MemoryVectors.validate()` có cờ `_validated` (một lần mỗi lifecycle; `setup()` ép kiểm lại; lỗi `query_points` đặt lại cờ). Test với client giả đếm `get_collection`.

## Không áp dụng

- **#12, #19**: `build_math.py` (commit 0c92ab8) và `build_data.py` (commit 441af43) đã bị xóa trong refactor True Agent; không còn tham chiếu trong `backend`.

## Cho agent D1

`SemanticMemory.sync` vẫn giữ dọn `conversation_exists` -> `vectors.delete_conversations` (PR #110) ở `semantic_memory.py`.

## Kiểm tra

Chạy trong `backend/`: `ruff check .` sạch, `ruff format --check .` 288 file sạch, `pytest tests/unit` 964 passed, 20 skipped. Không kiểm: thư mục dữ liệu thật trên VPS, compose/.env (agent C).
