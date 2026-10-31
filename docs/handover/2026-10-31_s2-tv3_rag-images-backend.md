# Bàn giao backend ảnh liên quan cho RAG

Ngày 31/10/2026, TV3 — MinhMuc, nhóm 4 Hollows.
Nhánh `feature/s2-tv3-rag-images` từ develop `b0f10a1` sau PR #44. Chưa commit/push/PR/merge.
chỉ sửa backend, contract/test và tài liệu; không sửa frontend/bot hoặc dữ liệu gốc.

## Đã triển khai

- [ImageCatalog/resolver](../../backend/app/services/images.py): catalog lazy, cache metadata giới hạn,
  nối source/revision/section/image_id; chỉ ảnh từ citation đã validate; dedup, max 3, giữ scope/unknown/spoiler.
- [Endpoint ảnh](../../backend/app/api/routes/images.py): raster bytes qua /api/v1/images/{id}, kiểm root,
  hash/MIME/extension/byte/pixel, verify/decode; không StaticFiles cả thư mục hoặc proxy remote URL.
- [Chat schemas](../../backend/app/api/schemas/chat.py) và [history](../../backend/app/api/schemas/conversation.py):
  thêm images default rỗng; event sources thêm images, không event mới hoặc opt-in bắt buộc.
- [Service](../../backend/app/services/chat.py), factory/main/router: wiring cùng catalog cho chat/endpoint;
  resolve sau generation validation, giữ cancellation/cleanup, lỗi ảnh fallback text.
- Settings, `.env.example`, Compose đồng bộ biến RAG_IMAGES_*; không sửa `.env` thật, key hoặc code retrieval/index.
- [Unit tests](../../backend/tests/unit/test_images.py), [audit read-only](../../backend/scripts/audit_images.py),
  [OpenAPI sinh lại](../api/openapi.json), [contract TV4](../api/images-tv4.md).

## Audit dữ liệu thật

[JSON audit](../testing/2026-10-31_images-audit.json) giữ thống kê, mẫu và ba ví dụ resolve/endpoint local.

- CSV 65.593 occurrence, occurrence_id unique; image_id là SHA-256 blob, cùng blob có thể xuất hiện ở nhiều trang.
- Association: exact_section 15.642; excluded_ui 42.000; review 7.951.
- Media status: downloaded 9.114; cached 14.472; excluded 42.000; failed 7.
- Catalog kỹ thuật nhận 15.642 occurrence / 7.603 blob; cả 7.603 file tồn tại. Đây chưa là kiểm bytes toàn bộ.
- Chunk JSONL 23.765, có image_ids ở 7.640 chunk (5.341 chunk EN), 5.358 image ID khác nhau.
- Mẫu 30 file theo hash sắp xếp khớp hash và Pillow; kiểm thêm Bloodhound's Fang, Ranni, Messmer;
  ba GET local ASGI HTTP 200, PNG/PNG/JPEG, body SHA khớp ID.
- Tất cả 65.593 occurrence license_status=unknown_review_required, không tự approve.
  Caption chỉ có ở 1.155 occurrence; alt có ở 65.466. Thiếu caption không bịa mô tả.
- Artifact hash CSV/documents/chunks khớp manifest bàn giao/report cũ, không sửa source.

Ảnh được chọn bằng liên kết section rõ ràng, không có hiểu nội dung pixel hoặc semantic image search.
Nếu source được trích không có liên kết ảnh, images=[] là đúng; không lấy gallery/infobox trang khác để lấp chỗ trống.
Không cấp nhãn an toàn cho ảnh thiếu spoiler_level. License unknown giữ nguyên, không chứng nhận quyền sử dụng.

## Dùng và bàn giao TV4

Đọc [images-tv4.md](../api/images-tv4.md) để có schema, payload JSON/SSE, URL, config và ví dụ test.
TV4 cần cập nhật types/parser/state/UI để hiển thị; client text hiện tại bỏ qua field mới và vẫn hoạt động.
SSE ảnh nằm trong event sources sau validation, trước done. History vẫn RAM, giữ images khi đọc lại message.
Discord cần URL public hoặc bot GET bytes rồi attach; chưa triển khai bot/gateway trong tác vụ.

**Không cần reindex.** Restart API để nạp code; catalog/path mặc định khớp artifact hiện có,
Compose dùng mount dữ liệu hiện tại. Clone mới cần metadata/blob riêng, không chỉ clone code.
Catalog reload bằng restart app; I/O/Pillow trong worker, không load model/scan files khi import hoặc dựng OpenAPI.

## Kiểm tra và giới hạn

Baseline **331 passed, 1 warning**, 13,96 giây. Kết thúc: **368 passed, 1 warning**, 16,66 giây,
gồm 37 case ảnh mới (parametrized), không skip. Warning dự kiến về payload indexes trong Qdrant memory.
Ruff check/format (170 file), OpenAPI check, pip check, UTF-8/local links và `git diff --check` đạt.
Đã kiểm riêng unit ảnh, web tests 21/21 + integration 9/9 qua backend mock, typecheck web đạt; không sửa web.
Client bot đã đọc và không reject field bổ sung; chưa chạy Discord thật.
Nguồn/ảnh local có kiểm trong TestClient với context giả, không tạo engine/LLM hoặc gọi Internet/server DB.
Symlink/junction escape được mô phỏng qua kết quả Path.resolve trong unit, chưa chứng nhận mọi race của filesystem.
GIF kiểm frame đầu; root media do backend quản lý, không có endpoint upload/ghi ảnh.
Chưa chạy DeepSeek, embedding/index, notebook/crawl hoặc browser render ảnh/container API thật.
Không tự ghi điểm eval, quyền ảnh approved hoặc task Done; không cập nhật Trello.

Các lệnh đã chạy từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
.venv/Scripts/python.exe -m pip check
```

Audit script đã chạy với sample-size mặc định 30; report cuối được promote về tên trong liên kết trên.
Muốn tự chạy lại, chọn tên report JSON mới ngoài backend/data, ví dụ:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.audit_images --output ../docs/testing/images-audit-rerun.json
```

Lệnh này chỉ đọc artifact/ảnh local và dùng ASGI TestClient với context giả; không gọi URL Internet, LLM hoặc Qdrant.
