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
| Dense, không rerank, web off | 95,6% | 96,7% | 4,5 s |
| Hybrid RRF, web auto | 95,6% | 97,8% | 5,2 s |
| **Hybrid + L12, web auto (mặc định)** | **97,8%** | 96,2% | 6,6 s |
| Hybrid + L12, web always | 96,7% | 98,4% | 14,6 s |
| Hybrid + API Jina, web auto (tham khảo) | 96,7% | 97,3% | 6,0 s |

- Retrieval: Hybrid + L12 đạt Recall@5 86,6% và MRR 0,739. RRF đạt 83,1% / 0,706; API Jina đạt 90,7% / 0,789.
- Mọi cấu hình đều nằm trong khoảng 95–98%. Khác biệt là 5 câu trên 183, phần lớn nằm trong nhiễu.
- **Web always không đáng bật mặc định:** độ đúng không tăng, độ trễ gấp đôi, chi phí tăng khoảng 50%, và có 1 câu lỗi 502.
- Chi phí DeepSeek là 0,22–0,28 USD mỗi lượt, và khoảng 0,35 USD với web always. Tổng 7 lượt hết 1,91 USD; số dư còn 3,05 USD.

## Đính chính lỗi chấm (24/11, sau commit 33e4262)

- Bản đầu báo cáo một lỗi "trích số nguồn không tồn tại". **Đây là lỗi của script chấm, không phải lỗi app.**
  - App chỉ trả các nguồn được trích và giữ số gốc trong `source.index`, ví dụ 1, 2, 4. Web và bot đều ghép `[n]` theo `source.index`.
  - Script tạo gói chấm lại đánh số nguồn theo vị trí 1, 2, 3.
  - Đếm lại bằng `source.index` trên cả 11 lượt: 0 câu sai.
- Đã trả 175 câu về faithfulness 2, và sửa thêm IB-GS-278 của `hybrid-norerank-always` từ pass thành fail cho thống nhất với các lượt khác.
- Sau khi sửa, faithfulness 2 là 96–99,5%. Bản cũ ghi 80–92%. Kết luận cũ "web always làm tụt faithfulness" là sai. Độ đúng hoàn toàn không đổi.

## Lỗi tìm thấy (chưa sửa, nên làm ở nhánh riêng)

1. **IB-GS-300 trả 502 ở cả hai lượt web always.**
   - Với web off và web auto, câu này trả lời đúng.
   - Validator từ chối vì `unknown_evidence_index`: model đưa evidence có index lớn hơn số đoạn context. Ở `hybrid-norerank-always`, lần đầu lỗi `insufficient_with_citations`.
   - Chỉ được thử lại 1 lần (`format_retries` ≤ 1), sau đó trả `upstream_error`.
   - Nguyên nhân gốc chưa rõ; cần tái hiện và ghi lại context đã đánh số.
2. **Câu thiếu dữ kiện đoán một giả thuyết thay vì hỏi lại.**
   - Pass 70,6–76,5%.
   - Số lượt fail trên 11 lượt: IB-GS-299 và 278 fail ở cả 11 lượt; 279 và 294 ở 10 lượt; 277 ở 9 lượt.
   - Đổi retrieval, reranker hay web không giúp được; đây là việc của prompt hoặc agent.

## Kiểm

- `tests/unit/test_eval_ablation.py` pass.
- ruff đạt trên các file eval đã sửa.
- Kết quả thô (`results.json`) nằm trong `backend/data/research_runs/2026-11-24-ablation/`, thư mục này bị gitignore. Lệnh tái lập ghi trong README của bộ đo.
