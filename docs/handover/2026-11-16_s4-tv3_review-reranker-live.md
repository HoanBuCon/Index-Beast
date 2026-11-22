# TV3 · Review và kiểm chứng live Jina reranker (16/11/2026)

## Phạm vi

- Review nhánh `feature/s4-tv3-api-reranker` từ fixed point `65a9b7301b90755ea55d69844a157e8176ade0da`; diff và test reranker chưa theo dõi, cùng handover ban đầu.
- Không commit, push, merge hoặc thay đổi fixed point. Giữ nguyên `.env` và mọi key của người dùng; không sao chép secret vào tài liệu.
- Báo cáo kiểm chứng: [review và kết quả live](../testing/2026-11-16_reranker-review-live.md). Phạm vi/budget: [meta-prompt](../prompts/2026-11-16_tv3-review-reranker-live.md).

## Kết quả

- **Standards:** không phát hiện vi phạm cứng có chứng cứ theo các quy ước repo.
- **Spec:** phát hiện và sửa luồng compatibility rerank trước RRF/hơn một lần; deadline rerank chưa được giới hạn theo thời gian còn lại của lượt chat. Các đường JSON/SSE truyền thời điểm bắt đầu thực tế; cancellation được giữ nguyên.
- **Observability:** log structured attempt/outcome đã lọc query, document, key, response body và chuỗi lỗi thô. Outcome ghi provider/model, candidate/ranked count, status, reason category, elapsed ms và HTTP status code khi lỗi status. Dữ liệu theo từng lần gọi.
- **Local tests:** backend suite 1.182 passed, 20 skipped; có hai cảnh báo đã biết liên quan Qdrant và Alembic. Test adapter/log có 17 test đạt; Ruff/format, Docker Compose config và `git diff --check` đạt.
- **Live:** hoàn thành 5 câu hỏi chính và 1 lượt follow-up, sáu HTTP response đều 200. Jina nhận 4 request với 30 ứng viên mỗi request; cả 4 outcome `ok`, không fallback. Một ca Tavily search/extract thành công. Cả 5 kết quả khớp kỳ vọng sau đối chiếu thủ công; corpus giữ nguyên 34.070 điểm.
- **Giới hạn:** đây là kiểm tra tích hợp nhỏ, không so với baseline có đối chứng; không kết luận reranker cải thiện chất lượng hoặc đạt NFR độ trễ. Artifact chi tiết ở đường dẫn ignored/nontracked `backend/data/research_runs/2026-11-16-reranker-review-live/`, không được sao chép raw trace vào handover.

## Tệp thay đổi trong phạm vi review

- **Review/đầu ra:** `docs/prompts/2026-11-16_tv3-review-reranker-live.md`, `docs/testing/2026-11-16_reranker-review-live.md`, handover này, `docs/handover/README.md`, và handover reranker ban đầu.
- **Tích hợp/runtime:** `backend/app/rag/reranker.py`, `retriever.py`, `pipeline.py`, `tool_agent.py`, `backend/app/services/chat.py`, `backend/app/services/factory.py`, `backend/app/context.py`, `backend/core/config.py`.
- **Test/cấu hình/tài liệu:** `backend/tests/unit/test_reranker.py`, `test_reranker_wiring.py`, `test_config.py`, `.env.example`, `docker-compose.yml`, `backend/app/rag/README.md`, `docs/indexbeast-system-pipeline.md`.
- Các thay đổi nằm trên working tree của người dùng; không commit/push/merge trong lượt này.

## Tệp liên quan

- [Mã reranker](../../backend/app/rag/reranker.py), [test adapter và log](../../backend/tests/unit/test_reranker.py).
- [Báo cáo kiểm chứng](../testing/2026-11-16_reranker-review-live.md).
- Handover ban đầu [TV3 · Jina Reranker](2026-11-16_s4-tv3_jina-reranker.md) giữ lại bối cảnh cấu hình ban đầu và được bổ sung trạng thái kiểm chứng hiện tại.

## Còn lại

- Nếu cần kết luận chất lượng hoặc SLA, chạy benchmark đối chứng riêng theo tập dữ liệu và ngân sách được duyệt.
