# TV3 · Jina Reranker API tùy chọn (16/11/2026)

## Phạm vi và nhánh

- Bổ sung tích hợp reranker Jina tùy chọn cho truy xuất RAG local, cấu hình API key an toàn và hướng dẫn bật/tắt.
- Nhánh: `feature/s4-tv3-api-reranker`. Không commit, push hoặc mở PR trong lượt này.
- Thay đổi repo: `backend/app/context.py`, `backend/app/rag/reranker.py`, `backend/app/rag/retriever.py`, `backend/app/rag/pipeline.py`, `backend/app/rag/tool_agent.py`, `backend/app/services/factory.py`, `backend/core/config.py`, `backend/tests/unit/test_config.py`, `backend/tests/unit/test_reranker.py`, `backend/tests/unit/test_reranker_wiring.py`, `.env.example`, `docker-compose.yml`, `backend/app/rag/README.md`, `docs/indexbeast-system-pipeline.md` và handover này.

## Quyết định và cách dùng

- `RAG_RERANKER_ENABLED=false` mặc định. Đặt `RAG_RERANKER_ENABLED=true` và điền `JINA_API_KEY` vào `.env` cục bộ; khởi động lại API để nạp cấu hình. Tạo key tại [Jina AI](https://jina.ai/?sui=apikey); endpoint dùng là `https://api.jina.ai/v1/rerank`, tài liệu [Jina Reranker](https://jina.ai/reranker/).
- Thiếu key, key rỗng hoặc `change-me` thì `reranker_available` là false; nếu cờ đã bật, context dùng `NoReranker` và giữ thứ tự RRF. Không ghi key vào Git hoặc tài liệu.
- Mặc định model `jina-reranker-v2-base-multilingual`, tối đa 30 ứng viên và timeout 3 giây (giới hạn cấu hình tối đa 10 giây). Timeout rerank tách biệt với timeout truy xuất.
- Reranker chỉ sắp xếp lại phần đầu danh sách; tail giữ nguyên. Lỗi HTTP, timeout hoặc response sai cấu trúc giữ lại toàn bộ thứ tự ban đầu. `Hit.score` và payload không bị thay; Agent vẫn quyết định tối đa 5 evidence cuối cùng.
- Một `JinaReranker` trong lifespan dùng chung cho `HybridRetriever`; đường Tool Agent và legacy đều chạy qua retriever này đúng một lần. Legacy pipeline mặc định vẫn có `NoReranker` khi không inject provider.
- Không cần tải model hoặc reindex. `.env.example` giữ key rỗng và cờ tắt; `.env` local được cập nhật riêng để bật cờ nhưng key vẫn để trống cho tới khi người dùng cung cấp.

## Tài liệu và kỹ năng cục bộ

- `backend/app/rag/README.md` ghi cách bật và giới hạn; sơ đồ tại `docs/indexbeast-system-pipeline.md` thể hiện bước rerank sau RRF.
- Trong cùng lượt công việc, đã cài 72 skill cục bộ (Matt 39, Addy 25, Cloudflare 1, Obsidian 7) vào `C:\Users\nguye\.codex\skills`; bảy tài liệu tham chiếu bổ trợ của Addy được chép vào `C:\Users\nguye\.codex\references` để các liên kết tương đối tới `../../references` hoạt động. Không chỉnh sửa skill hệ thống.
- Subagent Luna thực hiện phần cấu hình và tài liệu; Terra thực hiện adapter, test, review và xác minh đầy đủ; main điều phối và tích hợp các phần. Không có số liệu benchmark reranker hoặc khẳng định chất lượng được cải thiện.

## Kiểm tra đã chạy

- Backend unit offline: **1169 passed, 20 skipped**. Có hai warning đã biết liên quan Qdrant local và Alembic.
- Ruff check và format check cho 10 file Python thay đổi: đạt.
- `docker compose config --quiet` và `git diff --check`: đạt.
- Các test provider dùng HTTP mock. Không gọi Jina API thật; chưa kiểm tra key thật hoặc chất lượng rerank trên corpus.

## Cập nhật review/kiểm chứng — 16/11/2026

- Nội dung trên ghi nhận sự kiện setup ban đầu: khi viết handover đó chưa có lần gọi Jina thật. Bản review tiếp theo dùng fixed point `65a9b7301b90755ea55d69844a157e8176ade0da`; hoàn tất 5 câu chính gồm 1 lượt hỏi tiếp, 6/6 HTTP response 200, 4/4 lần gọi Jina thành công và 5/5 câu trả lời khớp kỳ vọng khi đối chiếu thủ công. Chi tiết ở [báo cáo review/live](../testing/2026-11-16_reranker-review-live.md).
- Các sửa đổi review đưa legacy path về RRF rồi một lần rerank, ràng buộc deadline theo thời gian còn lại của chat, truyền đúng thời điểm bắt đầu qua JSON/SSE, và ghi structured outcome đã lọc dữ liệu nhạy cảm.
- Mẫu live nhỏ không có baseline đối chứng; không kết luận chất lượng cải thiện hoặc đạt SLA. Xem báo cáo để biết cách chạy và giới hạn kết luận.

## Còn lại

- Người dùng cần điền `JINA_API_KEY` thật vào `.env` cục bộ và restart API nếu muốn bật provider. Không cần gửi key trong chat.
- Muốn kết luận hiệu quả cần benchmark có kiểm soát với Jina API (phát sinh quota) trên tập query/corpus đã chọn, so sánh metric retrieval với cùng điều kiện và ghi nhận chi phí/độ trễ. Chưa thực hiện trong lượt này.
