# TV3 · Bàn giao đánh giá RAG Sprint 4

Các phép đo thực hiện ngày 14/11/2026. Bổ sung bàn giao ngày 15/11/2026 theo giờ Việt Nam. Phụ trách đánh giá là TV3, MinhMuc. Mã và báo cáo của đợt đánh giá đã vào `develop` qua PR #105, commit merge `01cf475`. Phiếu rà soát vẫn ghi `pending` cho xác nhận của TV2.

## Công việc đã thực hiện

- Rà bộ 200 câu S4, chỉnh 26 ca hoặc hồ sơ bằng chứng và đối chiếu artifact dữ liệu với 183 câu dữ kiện và 11 lượt bổ sung. Khóa manifest 100 ca và hoàn thiện rubric để tách độ đúng, hành vi hỏi lại và độ bám nguồn. [Phiếu rà soát](../../backend/eval/reviews/s4-golden-set-review.jsonl) · [Rubric](../evaluation/s4-rubric.md)
- Sửa cách Agent phục hồi khi quyết định tra tên sai schema, xác minh tên gõ nhầm hoặc rút gọn và hỏi rõ chủ thể mơ hồ. Bổ sung cách chạy tiếp lượt hỏi đang chờ và tổng hợp điểm đánh giá. Đối chiếu hai lượt đo trong `eval_runs` trên PostgreSQL local. Cập nhật test Web qua Vite proxy để kiểm đủ ba trường của API capabilities. [Agent](../../backend/app/rag/agent.py) · [Tra tên](../../backend/app/rag/entity_spelling.py) · [Runner](../../backend/scripts/benchmark_agent.py) · [Test Web](../../web/tests/integration/chat.test.ts)
- Đo E5, BM25 và Hybrid RRF với câu gốc và một rewrite dùng chung từ Agent. Bộ đo gồm 200 câu S4 và 12 câu bổ sung. Cả sáu cấu hình dùng cùng corpus S4, bộ lọc và quyết định về ý định. Lượt Auto dùng 18 câu đại diện. [Meta-prompt](../evaluation/s4-retrieval-ablation-meta-prompt.md) · [Mã chạy](../../backend/eval/s4_retrieval_matrix.py) · [Mã tổng hợp](../../backend/eval/summarize_retrieval_matrix.py)

## Kết quả đã ghi nhận

| Phép đo | Kết quả |
| --- | --- |
| 100 ca hồi quy với DeepSeek và Tavily Auto | 100/100 ca có phản hồi cuối, 111/111 request HTTP 200. Accuracy ở lượt đầu tăng từ 71/83 lên 76/83 (91,57%). Ca hỏi bùa từng trả 502 đã hỏi lại đúng và trả lời sau khi người dùng bổ sung. |
| Ma trận truy xuất với Tavily Off | 1.272 lượt truy xuất và 1.272 kết quả trả lời. Hybrid + rewrite đạt Recall@5 theo trang 90,34%, MRR@5 0,767 và Accuracy 160/195 (82,05%). |
| Tavily Auto và kiểm API riêng | 108 lượt trong ma trận Auto. Hybrid + rewrite đạt 12/16 câu dữ kiện ở cả Off và Auto, có ca St. Trina được nguồn web bổ sung. Agent đầy đủ hoàn tất riêng 6 ca qua 7 request JSON/SSE HTTP 200. |
| Kiểm thử mã | Đợt sửa Agent đạt 1.138 unit test backend và 5 test tích hợp. Web đạt 49 unit và 9 test tích hợp, bot đạt 33 test. Đợt ma trận đạt 22 test liên quan. |

[Báo cáo chạy lại 100 ca](../testing/2026-11-14_s4-retest-100.md) · [Báo cáo ma trận](../testing/2026-11-14_s4-retrieval-matrix.md)

## Tái lập và phần còn lại

Từ `backend`, xem mục **Ma trận truy xuất và rewrite** để lập kế hoạch, chạy thật hoặc tổng hợp checkpoint. Lệnh có `--execute` gọi dịch vụ thật. Kết quả thô của lượt đã đo lưu local trong `backend/data/research_runs/2026-11-14-s4-retrieval-matrix/`, gồm query, hạng, context, đáp án và điểm. [Lệnh tái lập](../../backend/eval/README.md#ma-trận-truy-xuất-và-rewrite)

Hai báo cáo Accuracy đo trên tập và luồng khác nhau. Lượt 100 ca dùng Agent đầy đủ và được Codex chấm. Ma trận dùng một lượt truy xuất, chấm bằng DeepSeek ẩn cấu hình và đối chiếu thủ công một số ca. Khi báo cáo trước giảng viên, nêu rõ phương pháp và mẫu số đi cùng từng chỉ số.

- **TV2** có thể đối chiếu các ca còn tranh luận và xác nhận phiếu rà soát.
- **TV3** ưu tiên lỗi hỏi lại dù tìm đúng trang (`STONESWROD`) và lỗi chọn thiếu đoạn chứa chỉ số (Carian Slicer).
- **Nhóm demo** chạy lại kịch bản gõ sai tên, hỏi bổ sung về Spelldrake Talisman +2 và tính sát thương Boiled Prawn/Crab trên giao diện và đường dẫn trình chiếu. Các kịch bản đã có kết quả qua API local.
