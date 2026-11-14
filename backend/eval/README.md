# Đánh giá IndexBeast · Sprint 4

[Golden set mặc định](golden_set.jsonl) gồm 200 câu mới, ID `IB-GS-101`–`IB-GS-300`. Bản 100 câu trước đây được lưu tại [golden_set_s3.jsonl](golden_set_s3.jsonl) để tái lập các báo cáo cũ.

| Độ khó | Tiếng Việt | Tiếng Anh | Tổng |
| --- | ---: | ---: | ---: |
| Dễ | 33 | 27 | 60 |
| Trung bình | 49 | 41 | 90 |
| Khó | 28 | 22 | 50 |
| Tổng | 110 | 90 | 200 |

Câu hỏi bao phủ trang bị, cơ chế, nhân vật, sự kiện, tuyến đường, nhiệm vụ và yêu cầu ngoài phạm vi. Đáp án tham chiếu dùng để chấm theo ý. Các ca hành vi dùng `expected_answer` để mô tả phản hồi cần đạt.

[Rubric Sprint 4](../../docs/evaluation/s4-rubric.md) quy định cách chấm đáp án, hành vi, lượt bổ sung, trích dẫn và chỉ số truy xuất.

[Phiếu review S4](reviews/s4-golden-set-review.jsonl) giữ quote nguyên văn, ID đoạn, URL và hash của nguồn S4 cho các ca có dữ kiện. Trường `case_tags` đánh dấu ca gõ sai, không dấu và hỏi bổ sung. `followup` lưu câu bổ sung, kết quả kỳ vọng và bằng chứng cho lượt cuối. `variant_pair` nhóm các biến thể cùng ý. Khi chia tập hoặc tính độ bất định, giữ các biến thể cùng ý trong cùng nhóm. Trường `assistant_review` ghi kết quả rà soát theo rubric TV2, do Codex thực hiện. Trạng thái ký duyệt của UncleThing vẫn là `pending`.

Từ thư mục backend, xác thực bộ mặc định và bằng chứng trong bản dữ liệu đã nạp.

```powershell
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --corpus data/chunk_runs/s4-wiki-release/chunks.jsonl
```

[Manifest baseline S4](s4_baseline_25.json) dùng 25 câu chính riêng. Baseline kiểm tra luồng RAG–LangGraph với DeepSeek và Tavily Auto qua API, gồm JSON và SSE. Runner có thể tiếp tục câu hỏi phụ đã được chuẩn bị khi Agent yêu cầu làm rõ. Một câu hỏi chính và các lượt bổ sung của nó được tính là một ca.

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/s4_baseline_25.json --max-cases 25
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/s4_baseline_25.json --max-cases 25 --execute --allow-llm --allow-web --allow-embedding --output data/research_runs/s4-baseline-25-new
```

Lệnh đầu in kế hoạch. Lệnh thứ hai chạy thật, cần dịch vụ PostgreSQL, Redis, Qdrant, cache encoder và key API. Runner dùng DB và collection bộ nhớ thử riêng. Corpus được đọc từ collection trong cấu hình. Kết quả chạy ngày 14/11/2026 nằm trong [báo cáo baseline S4](../../docs/testing/2026-11-14_s4-baseline-25.md).

Các lệnh `scripts.diagnose_golden`, `scripts.diagnose_gameplay` và `scripts.diagnose_agent_memory` vẫn có thể tái lập các tập chẩn đoán cũ bằng bản S3 đã lưu. Các báo cáo đánh giá cần ghi rõ phiên bản bộ câu, số ca thực chạy và tiêu chí chấm.

[Tập đánh giá 100 ca](s4_evaluation_100.json) được chọn trước khi chạy. Xem [báo cáo đánh giá S4](../../docs/testing/2026-11-14_s4-evaluation-100.md) để biết cấu hình, kết quả theo nhóm và phương pháp chấm.

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/s4_evaluation_100.json --max-cases 100 --execute --allow-llm --allow-web --allow-embedding --output data/research_runs/s4-evaluation-100-new
.venv/Scripts/python.exe -X utf8 -m eval.measure_retrieval --manifest eval/s4_evaluation_100.json --output data/research_runs/s4-retrieval-100-new.json
```

Lệnh truy xuất đọc chỉ mục Qdrant với câu hỏi nguyên văn và lưu danh sách xếp hạng. Recall@5 và MRR@5 đối chiếu các trang vàng trong năm trang khác nhau đầu tiên, theo thứ tự trả về của retriever.

Để đo cùng chỉ mục với E5 dense-only, thêm `--mode dense-only` và dùng đường dẫn đầu ra mới. Chế độ mặc định là `--mode hybrid`.

[Báo cáo chạy lại 100 ca sau khi sửa Agent](../../docs/testing/2026-11-14_s4-retest-100.md) đối chiếu cùng manifest. Lệnh sau tổng hợp điểm đã chấm rồi ghi lượt đo vào PostgreSQL của môi trường đang chọn.

```powershell
.venv/Scripts/python.exe -X utf8 -m eval.summarize_scores --manifest eval/s4_evaluation_100.json --scores ../docs/testing/2026-11-14_s4-retest-100-scores.jsonl --name s4-auto-100-retest --output data/research_runs/s4-retest-scores.json
.venv/Scripts/python.exe -X utf8 -m scripts.eval_runs add --from-json data/research_runs/s4-retest-scores.json
```

Nếu một ca đang chờ câu trả lời bổ sung, dùng `--resume --answer-pending CASE_ID "Câu trả lời thực tế"` cùng manifest, ngân sách và thư mục đã dùng. Runner tiếp tục từ ID hội thoại và ID hỏi bổ sung đã lưu. Ghi rõ các lượt bổ sung phát sinh khi đối chiếu kết quả.

## Ma trận truy xuất và rewrite

[Thiết kế thí nghiệm](../../docs/evaluation/s4-retrieval-ablation-meta-prompt.md) dùng 200 câu S4 và [12 câu bổ sung](s4_retrieval_supplement.jsonl). Harness chạy truy xuất một lần mỗi cấu hình, dùng context của cấu hình đó cho generator và ghi điểm theo [rubric](../../docs/evaluation/s4-rubric.md). Tắt hoặc bật rewrite để thay truy vấn tìm kiếm. Giữ nguyên bước nhận diện ý định, câu đưa vào generator, collection và bộ lọc của cả hai nhánh. Tavily Auto có tập 18 ca đặt trước. [Báo cáo kết quả](../../docs/testing/2026-11-14_s4-retrieval-matrix.md)

```powershell
.venv/Scripts/python.exe -X utf8 -m eval.s4_retrieval_matrix --output data/research_runs/s4-retrieval-matrix
.venv/Scripts/python.exe -X utf8 -m eval.s4_retrieval_matrix --output data/research_runs/s4-retrieval-matrix --execute
.venv/Scripts/python.exe -X utf8 -m eval.summarize_retrieval_matrix data/research_runs/s4-retrieval-matrix --output data/research_runs/s4-retrieval-matrix/summary.json
```

Lệnh đầu chỉ đếm ca. Lệnh có `--execute` gọi DeepSeek, thực hiện truy xuất Qdrant bằng encoder đã có cache và gọi Tavily trong nhóm Auto. Có thể chạy tiếp với cùng thư mục để dùng checkpoint. Dùng thư mục mới khi đổi tập câu, cấu hình hoặc muốn lặp lại thí nghiệm từ đầu.
