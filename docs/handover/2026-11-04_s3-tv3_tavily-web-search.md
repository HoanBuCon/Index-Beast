# Tavily Search/Extract, auto/always trên web và Discord auto

Ngày 04/11/2026 · TV3 MinhMuc · nhánh `feature/s3-tv3-tavily-web-search`.
Nhánh tạo từ nhánh local sửa 502, giữ nguyên toàn bộ thay đổi chưa commit từ tác vụ trước;
chưa stash/reset/rebase, commit/push/merge. Không cập nhật Trello.

## Kết quả và quyết định

Cập nhật theo yêu cầu mới nhất: thay checkbox bằng nút tạm ba chế độ
**OFF → ON → ALWAYS → OFF**, mapping off/auto/always, giữ mặc định ON (auto).
Nút có type=button để không submit form; khóa khi busy/unavailable/demo, unavailable hiển thị OFF.
Send và retry truyền mode đang chọn; Discord vẫn auto. TV4 có thể thay giao diện sau mà giữ mapping.
Thêm `web/src/components/chat/searchMode.ts`; đổi props composer/page/CSS và test handler chu kỳ.
Sau cập nhật nút: web **34/34** test, TypeScript + production build đạt; không cần chạy lại backend
vì không sửa backend trong lượt đổi nút. Chưa commit/push hoặc gọi model/search thật.

Thực hiện yêu cầu trong attachment và điều chỉnh mới: nút trên web trực tiếp điều khiển request,
ban đầu tắt=auto/bật=always, sau đó thay ba trạng thái như cập nhật trên. Discord luôn auto;
công tắc server chỉ là quyền vận hành.
Key được nhận từ .env hiện có, không sửa .env. Đọc Settings chỉ xác nhận key có và capability true,
không in secret hoặc tạo model/client khi kiểm tra cấu hình.

Các file:

- `core/config.py`, `.env.example`, Compose: key, mode, quyền, domain và budget.
- `app/adapters/tavily.py`: AsyncClient, Search/Extract batch, URL exact allowlist, lỗi an toàn,
  response-size cap, block extraction không cắt bảng, WebHit có provenance/unknown rõ.
- `app/rag/web_search.py`, `prompts/assess.md`: assessment đủ/thiếu/mơ hồ với evidence references,
  fallback search khi assessor lỗi, không dùng score như confidence, không chứng minh entailment.
- `pipeline.py`: node web sau rerank và trước context, auto/always/off, ngân sách và metadata context.
  Chọn typed WebHit riêng với policy local, không giả payload approval. Top-5 giữ nguyên.
- `rewrite.py`/prompt: continuation topic, bảo vệ tên Marika, không giữ “Gia” trong “Gia phả” như tên riêng;
  rewrite lỗi ở câu nối tiếp không tìm bằng query thiếu chủ thể mà làm rõ.
- `context.py`, factory: client Tavily theo lifespan; không mở client trong mock/llm_only/missing key.
- `generator.py`, service chat: Source.origin đúng local/web, ảnh chỉ xét citation local.
- API ChatOptions và GET capabilities; `docs/api/openapi.json` xuất lại.
- Web types/options/page/composer/CSS: nút accessible, status auto/always/unavailable, khóa khi busy,
  request JSON/SSE mang lựa chọn; không viết lại frontend. Bot types/ask gửi auto.
- Backend `test_web_search.py`, frontend tests chat/searchToggle, bot ask regression.
- [Contract và hướng dẫn](../api/web-search-tv4.md), README RAG, danh sách handover.

## Kiểm chứng và sự cố

- Baseline đúng cấu hình backend: 563 passed, 1 warning Qdrant memory, 19,09 giây.
- Backend lần cuối sau triển khai: 593 passed, 1 warning, 20,23 giây. File test web search có 30 case,
  gồm policy, network mock, timeout/cancel, nguồn web JSON/SSE và capability; fake không đo recall.
- Web 33/33 test, typecheck/build đạt. Bot 27/27, typecheck và formatting đạt.
- Ruff check/format các file Python thay đổi, OpenAPI --check, pip check đạt.
- Vòng test đầu phát hiện merge dedup local làm mất chunk có cùng URL/text nhưng khác ID;
  đã sửa giữ nguyên local khi không có web. Assertions cũ giữ nguyên, toàn bộ unit đạt sau sửa.
- Web integration ban đầu 500 vì fixture `SimpleNamespace(health_checks={})` không có settings,
  trong khi guard hiện có đọc ctx.settings. Sửa bộ gá mock thêm Settings explicit mock,
  không thay guard/route để lách auth hoặc rate limit. Thêm kiểm capability false qua proxy.
- Sau sửa bộ gá, web integration 9/9 đạt (10,31 giây), gồm JSON/SSE/feedback/cancel/timeout/422.

Không gọi Tavily/DeepSeek thật, không tải/chạy embedding, index/crawl/notebook hay ghi DB/server.
Mock API integration chạy process/cổng riêng. Dữ liệu/collection và .env thật giữ nguyên.

## Hạn chế và vận hành

Xem contract cho budgets, fallback và smoke test. Restart backend/web, refresh trang, TV4 restart bot.
Không cần đăng ký slash command hoặc reindex. Chưa benchmark live, chưa kiểm bảng gameplay đầy đủ,
không hứa hướng build tối ưu. UI đã typecheck/build và SSR test, chưa kiểm layout bằng screenshot trình duyệt.
Web context unknown spoiler bị loại khi spoilers=false. Truy xuất local hỏng vẫn lỗi riêng.
Không bật pretrained fallback và không đóng giả lỗi provider thành insufficient để tránh 502.
