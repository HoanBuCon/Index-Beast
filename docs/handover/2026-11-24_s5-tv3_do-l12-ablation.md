# TV3 · Đo lại golden 200 với reranker L12 chạy trên máy, đủ 9 cấu hình (24/11/2026)

Nhánh `feature/s5-tv3-do-l12-ablation`, tạo từ `develop` sau PR #133. **Chưa commit.**

## Vì sao

- Key API Jina đã hết token.
- Reranker chốt dùng là `Xenova/ms-marco-MiniLM-L-12-v2`, chạy trên máy (`RAG_RERANKER_PROVIDER=local`). Xem `2026-11-24_s5-tv3_reranker-cuc-bo.md`.
- Cần đo lại bộ 9 cấu hình đổi từng trục (retrieval × reranker × web) bằng L12, để biết mỗi thành phần đóng góp bao nhiêu.

## Đã làm

- **Chạy tuần tự 7 lượt mới**, mỗi lượt 200 câu:
  - `hybrid-l12-auto`, `hybrid-l12-off`, `dense-norerank-off`, `dense-l12-auto`, `bm25-l12-auto`, `hybrid-l12-always`, `hybrid-norerank-always`.
  - Dùng lại 2 lượt RRF cũ (`hybrid-norerank-auto`, `hybrid-norerank-off`) và giữ 2 lượt API Jina làm số tham khảo.
  - Mọi lượt đều 200/200 câu, không có lỗi 402. Hai lượt web always có 1 câu 502, đều là IB-GS-300; xem bên dưới.
- **Claude chấm thay judge DeepSeek** theo rubric S4, cho cả 11 lượt (2.200 câu, gồm cả lượt cũ).
  - Trên `hybrid-norerank-auto`, Claude khớp correctness với judge v4-pro cũ ở 181/183 câu.
  - Quy ước chấm ghi ở `docs/testing/2026-11-24_golden-200-ablation/judge/quy-uoc-cham.md`.
- **Đo thêm retrieval** cho Dense + L12 và BM25 + L12.
- **Code eval:**
  - `eval/measure_retrieval.py`: thêm Precision@5. Nhãn `method` giờ ghi "rerank" chung, không còn ghi cứng "Jina".
  - `eval/summarize_ablation.py`: đổi tên trường `jina_ok`, `jina_fallback`, `jina_ok_pct` thành `reranker_ok`, `reranker_fallback`, `reranker_ok_pct`. Test `tests/unit/test_eval_ablation.py` sửa theo.
  - P@5 của các file `retrieval/*.json` cũ được tính lại từ `rows` có sẵn, không đo lại. Recall và MRR được kiểm bằng assert là không đổi.
- **Docs** trong `docs/testing/2026-11-24_golden-200-ablation/`:
  - `README.md`: báo cáo đầy đủ.
  - `summary.json`.
  - `judge/*.jsonl`: điểm Claude chấm; `*.v4pro.jsonl` là điểm của judge cũ.
  - `retrieval/*.json`.

## Kết quả chính

| Cấu hình | Đúng hoàn toàn | Faithfulness 2 | p50 câu đầu |
|---|---:|---:|---:|
| Dense, không rerank, web off | 95,6% | 91,8% | 4,5 s |
| Hybrid RRF, web auto | 95,6% | 91,3% | 5,2 s |
| **Hybrid + L12, web auto (mặc định)** | **97,8%** | 89,1% | 6,6 s |
| Hybrid + L12, web always | 96,7% | 82,5% | 14,6 s |
| Hybrid + API Jina, web auto (tham khảo) | 96,7% | 91,3% | 6,0 s |

- Retrieval: Hybrid + L12 đạt Recall@5 86,6% và MRR 0,739. RRF đạt 83,1% / 0,706; API Jina đạt 90,7% / 0,789.
- Mọi cấu hình đều nằm trong khoảng 95–98%. Khác biệt là 5 câu trên 183, phần lớn nằm trong nhiễu.
- **Web always không đáng bật mặc định:** độ đúng không tăng, faithfulness tụt khoảng 8 điểm, độ trễ gấp đôi, chi phí tăng khoảng 50%.
- Chi phí DeepSeek là 0,22–0,28 USD mỗi lượt, và khoảng 0,35 USD với web always. Tổng 7 lượt hết 1,91 USD; số dư còn 3,05 USD.

## Lỗi tìm thấy (chưa sửa, nên làm ở nhánh riêng)

1. **Trích số nguồn không tồn tại.** Câu trả lời ghi `[n]` lớn hơn số nguồn trả về.
   - Gặp ở 11–19 câu mỗi lượt. Với web always, con số này là 31–37 câu.
   - Đây là lý do chính làm faithfulness tụt.
   - Generator có bắt và thử lại, nhưng vẫn lọt.
2. **IB-GS-300 trả 502 ở cả hai lượt web always.**
   - Generator thử lại 2 lần đều hỏng: lần đầu `insufficient_with_citations`, lần sau `unknown_evidence_index`. Cuối cùng ứng dụng trả `upstream_error`.
   - Lỗi tái hiện được. Có thể là cùng gốc với lỗi 1.
3. **Câu thiếu dữ kiện đoán một giả thuyết thay vì hỏi lại.**
   - Pass 70,6–76,5%. Gần như lượt nào cũng fail cùng một nhóm câu: IB-GS-277, 278, 279, 294 và 299.
   - Đổi retrieval, reranker hay web không giúp được; đây là việc của prompt.

## Kiểm

- `tests/unit/test_eval_ablation.py` pass.
- ruff đạt trên các file eval đã sửa.
- Kết quả thô (`results.json`) nằm trong `backend/data/research_runs/2026-11-24-ablation/`, thư mục này bị gitignore. Lệnh tái lập ghi trong README của bộ đo.
