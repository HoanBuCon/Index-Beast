# Rà soát và kiểm chứng live Jina reranker — 16/11/2026

## Phạm vi và điểm cố định

- Nhánh: `feature/s4-tv3-api-reranker`.
- Điểm cố định: `65a9b7301b90755ea55d69844a157e8176ade0da`; soát thay đổi chưa commit tại `git diff HEAD`, hai test reranker chưa được theo dõi và handover TV3 ban đầu. Không có commit mới trong phạm vi review.
- Meta-prompt và giới hạn live: [prompt review](../prompts/2026-11-16_tv3-review-reranker-live.md).
- Mọi kết quả API được giới hạn tối đa **5 câu hỏi chính, tính cả lượt hỏi tiếp**. Không tính bất kỳ phép thử độc lập có tính phí nào ngoài các ca này. Dùng embedding cache local; không tải model, không reindex.

## Kết quả review

### Standards

Không phát hiện vi phạm cứng nào có chứng cứ theo quy ước repo. Đã đối chiếu `docs/AGENTS.md`, `docs/quy_uoc.md`, cấu hình Ruff/pytest và quy trình review. Review tĩnh; không đọc `.env`, không chạy mạng hoặc gọi provider.

### Spec

Hai lỗi tích hợp đã được sửa trước khi đánh giá live:

1. Đường compatibility cũ phải hợp nhất các lượt retrieval trước khi gọi reranker một lần; không rerank từng nhánh truy vấn trước RRF. Dùng chung provider qua `HybridRetriever`, tránh gọi lại lần hai ở graph.
2. Hạn rerank phải nằm trong deadline còn lại của lượt chat. Deadline bắt đầu tại biên dịch vụ và được truyền qua JSON/SSE; khi hết hạn, reranker giữ nguyên thứ tự retrieval. Hủy tác vụ từ bên gọi vẫn được truyền tiếp.

Log structured mới cung cấp sự kiện attempt/outcome đã lọc dữ liệu nhạy cảm, đủ phân biệt thành công với fallback do HTTP status, timeout, lỗi mạng, response không hợp lệ hoặc cancellation. Ghi provider/model, số candidate, số đã rank, status, nhóm nguyên nhân và elapsed ms; không ghi query, document, key, response body hay chuỗi lỗi thô. Trạng thái được giữ theo biến cục bộ mỗi lần gọi.

## Kiểm thử local

| Phạm vi | Kết quả |
| --- | --- |
| Test adapter và log `backend/tests/unit/test_reranker.py` | 17 passed; Ruff và định dạng đạt |
| Wiring `backend/tests/unit/test_reranker_wiring.py` và bộ unit backend | 1.182 passed, 20 skipped; có hai cảnh báo đã biết liên quan Qdrant và Alembic |
| Kiểm tra cấu hình và diff | Ruff/format, Docker Compose config và `git diff --check` đạt |
| Provider Jina thật | 4 rerank thành công qua tối đa 5 ca live bên dưới |

Các test adapter dùng HTTP mock. Không tải model hoặc tạo index trong kiểm thử local. Lượt ban đầu ghi nhận các ca mock không gọi Jina; phần kiểm chứng live hiện tại là lượt riêng, không được suy diễn từ kết quả đó.

## Kiểm chứng live

**Trạng thái:** hoàn thành đúng 5 câu hỏi chính, gồm một lượt làm rõ (6 lượt HTTP tổng). Tất cả sáu HTTP response trả về 200. Corpus giữ nguyên 34.070 điểm trước và sau. Đối chiếu thủ công cho thấy cả năm đáp án cuối cùng khớp kỳ vọng. Có 4 lần gọi Jina, cả 4 trả về 30/30 ứng viên đã rank thành công; không có fallback. Ca hỏi Claymore dùng Tavily, cả tìm kiếm và trích xuất đều thành công.

| # | Câu hỏi chính | Follow-up | Jina outcome / HTTP | Công cụ quan sát | Câu trả lời / kiểm tra | Nhận xét |
| ---: | --- | ---: | --- | --- | --- | --- |
| RR-LIVE-01 | Blessed Dew Talisman · số học | 0 | `ok`, 30/30; 775 ms; HTTP 200 | Local RAG | 60 HP / 30 giây; khớp kỳ vọng | Tiếng Việt; Tavily off |
| RR-LIVE-02 | Người trao Spectral Steed Whistle | 0 | `ok`, 30/30; 1.357 ms; HTTP 200 | Local RAG | Melina; khớp kỳ vọng | English; Tavily off |
| RR-LIVE-03 | Kỹ năng Claymore mặc định | 0 | Không gọi; HTTP 200 | Tavily search + extract | Lion's Claw; khớp kỳ vọng | Cấu hình Tavily always |
| RR-LIVE-04 | Nơi nhận Flask of Wondrous Physick | 0 | `ok`, 30/30; 503 ms; HTTP 200 | Local RAG, SSE | Third Church of Marika; khớp kỳ vọng | Tiếng Việt; Tavily off |
| RR-LIVE-05 | Làm rõ talisman/loại kháng | 1 | `ok`, 30/30; 812 ms; HTTP 200 | Hỏi làm rõ rồi local RAG | Hỏi rõ Spelldrake Talisman +2/PvE; trả lời giảm 20% sát thương phép; khớp kỳ vọng | Tổng hai lượt HTTP |

Kết quả đã ghi nhận qua log outcome đã lọc query, document, key, response body và chuỗi lỗi thô; bảng nêu công cụ, follow-up và kết quả câu trả lời. Thời gian Jina là bốn lượt quan sát, không phải p95 hay SLA. Artifact chi tiết nằm trong thư mục ignored/nontracked `backend/data/research_runs/2026-11-16-reranker-review-live/` (không liên kết Markdown vì không được bàn giao). Không đưa key hoặc raw provider response vào tài liệu.

## Giới hạn kết luận

Năm câu hỏi tối đa chỉ là kiểm tra tích hợp có giới hạn. Chúng không chứng minh mức tăng chất lượng, độ chính xác tổng quát, độ trễ p95 hoặc đạt NFR-PERF-02. Muốn kết luận chất lượng cần benchmark có đối chứng và dữ liệu chấm đã chọn trước; lượt này không tự mở rộng ngân sách đó.
