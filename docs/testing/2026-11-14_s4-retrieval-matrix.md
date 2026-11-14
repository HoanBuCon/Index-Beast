# Đánh giá E5, BM25 và rewrite của IndexBeast

Ngày 14/11/2026, chạy ma trận 3 phương pháp truy xuất × 2 chế độ truy vấn. Tập đo gồm 200 câu S4 và 12 câu bổ sung, tổng cộng 212 câu, gồm 116 câu Việt, 96 câu Anh, 64 dễ, 94 trung bình và 54 khó. Có 32 câu lỗi gõ hoặc tên, 8 câu Việt không dấu, 7 câu truy vấn nhiễu và 9 câu cần tính toán. Các nhóm có thể chồng lấp. [Thiết kế](../evaluation/s4-retrieval-ablation-meta-prompt.md) · [Câu bổ sung](../../backend/eval/s4_retrieval_supplement.jsonl) · [Lệnh tái lập](../../backend/eval/README.md#ma-trận-truy-xuất-và-rewrite)

## Phương pháp

- Thực hiện 1.272 lượt truy xuất và 1.272 kết quả trả lời với Tavily Off. Mỗi cấu hình dùng cùng 212 câu, corpus S4 tiếng Anh với 34.070 điểm, admission `pilot`, lấy tối đa 30 chunk rồi chọn tối đa 5 chunk phù hợp với ngân sách context. E5 dùng cosine, BM25 dùng sparse + IDF, Hybrid hợp nhất thứ hạng bằng RRF.
- Cấu hình **rewrite** dùng `search_query` từ `agent.decide()` của IndexBeast, không có history cho câu độc lập. Có 152/212 ca dùng truy vấn đã viết lại. Trong 60 ca giữ nguyên, 29 ca Agent giữ nguyên truy vấn, 8 ca dùng fallback sau kiểm tra, 15 ca hỏi lại và 8 ca từ chối. Toàn bộ retriever dùng chung cùng bản rewrite của từng ca.
- Cấu hình **gốc** đưa nguyên văn câu hỏi vào truy xuất. Cả hai cấu hình dùng cùng quyết định về ý định và câu hỏi gốc để sinh đáp án; do đó việc hỏi lại hoặc từ chối có thể giống nhau dù retrieval khác. Harness chạy một lần truy xuất, sử dụng generator hiện hành với `deepseek-flash`, thinking và temperature 0,2. Ma trận đo ảnh hưởng của thứ hạng và query mà không lẫn vòng lặp công cụ, bộ nhớ hay bộ kiểm tra phân bổ build của Agent đầy đủ. Mười một kịch bản hỏi lại được chấm theo hành vi ở lượt đầu.
- Recall@5 và MRR@5 tính theo 5 trang khác nhau đầu tiên trên 195 câu có nguồn. Context chunk recall tính độ phủ chunk tham chiếu đã gắn nhãn trên 183 câu S4. Accuracy tính tỷ lệ đạt điểm tối đa ở 195 câu dữ kiện. Độ bám nguồn tính trong số đáp án có trích dẫn. Câu hành vi có mẫu số riêng là 17.
- Dùng DeepSeek Flash chấm theo [rubric](../evaluation/s4-rubric.md), ẩn phương pháp truy xuất và chế độ rewrite trong dữ liệu chấm. Lưu cả lý do chấm. Một số output chấm thêm metadata `type=json_object`; runner đọc lại các mục chưa hợp lệ sau khi nhận diện trường này. Cuối lượt không còn kết quả thiếu điểm. Codex đối chiếu thủ công các ví dụ bên dưới, chưa có lượt chấm độc lập toàn bộ. Điểm LLM có thể đánh giá phần trả lời hữu ích khắt khe hơn cách chấm tay, ví dụ với IB-GS-296.

## Kết quả sáu cấu hình với Tavily Off

| Truy xuất | Query | Recall@5 | MRR@5 | Context chunk recall | Accuracy | Bám nguồn đủ |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| E5 | Gốc | 82,82% | 0,728 | 61,38% | 149/195 · 76,41% | 95,32% |
| E5 | Rewrite | 88,63% | 0,742 | 59,84% | 152/195 · 77,95% | 97,19% |
| BM25 | Gốc | 79,83% | 0,590 | 46,63% | 138/195 · 70,77% | 95,88% |
| BM25 | Rewrite | 87,69% | 0,690 | 55,83% | 158/195 · 81,03% | 98,90% |
| Hybrid | Gốc | 86,41% | 0,701 | 62,80% | 155/195 · 79,49% | 96,61% |
| Hybrid | Rewrite | **90,34%** | **0,767** | **64,07%** | **160/195 · 82,05%** | 98,38% |

Ở lượt Off, cả sáu cấu hình đạt 17/17 ca hành vi theo chấm tự động, với cổng ý định dùng chung. Bảy câu có đáp án bị cổng này chặn ở cả sáu cấu hình, gồm năm ca hỏi lại và hai ca từ chối. Lượt đo này không so trực tiếp Accuracy với báo cáo 100 ca trước đó vì thay đổi tập câu, quy trình Agent và người chấm.

### Accuracy theo nhóm

| Nhóm | n | E5 gốc | E5 rewrite | BM25 gốc | BM25 rewrite | Hybrid gốc | Hybrid rewrite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| S4 có đáp án dữ kiện | 183 | 78,14% | 79,23% | 71,04% | 81,42% | 80,87% | 83,06% |
| Tập bổ sung | 12 | 50,00% | 58,33% | 66,67% | 75,00% | 58,33% | 66,67% |
| Tiếng Việt | 103 | 66,99% | 70,87% | 59,22% | 78,64% | 70,87% | 78,64% |
| Tiếng Anh | 92 | 86,96% | 85,87% | 83,70% | 83,70% | 89,13% | 85,87% |
| Dễ | 59 | 86,44% | 84,75% | 81,36% | 84,75% | 88,14% | 86,44% |
| Trung bình | 87 | 82,76% | 82,76% | 72,41% | 87,36% | 86,21% | 86,21% |
| Khó | 49 | 53,06% | 61,22% | 55,10% | 65,31% | 57,14% | 69,39% |
| Tính toán | 9 | 6/9 | 7/9 | 5/9 | 5/9 | 6/9 | 7/9 |
| Lỗi gõ hoặc tên | 32 | 21/32 | 22/32 | 18/32 | 22/32 | 22/32 | 22/32 |
| Truy vấn nhiễu | 7 | 1/7 | 2/7 | 4/7 | 5/7 | 3/7 | 3/7 |
| Tiếng Việt không dấu | 8 | 0/8 | 5/8 | 5/8 | 7/8 | 3/8 | 6/8 |

Recall@5 của Hybrid tăng từ 80,58% lên 87,22% ở câu Việt, từ 62,24% lên 71,77% ở câu khó và từ 50,00% lên 93,75% ở tiếng Việt không dấu. Ở nhóm nhiễu, Hybrid + rewrite có Recall@5 92,86% nhưng BM25 + rewrite trả đúng nhiều hơn (5/7 so với 3/7). Hai nhóm thử nhỏ cần được đo thêm trước khi dùng để đổi cấu hình mặc định.

## Tavily Auto trên tập khóa trước

Chạy 18 câu × 6 cấu hình, trong đó có 16 câu dữ kiện, 2 ca hành vi. Khi assessor thấy thiếu bằng chứng, harness có thể thực hiện một lần Tavily Search → Extract, rồi sinh lại với context chọn được. Cùng tập Off dùng làm đối chiếu. Có 35 lượt thử tìm web, gồm 32 lượt có kết quả và 3 lượt timeout. Có 21 câu trả lời trong 108 lượt dẫn ít nhất một nguồn web.

| Cấu hình | Đúng đủ Off | Đúng đủ Auto | Lượt Auto có trích dẫn web |
| --- | ---: | ---: | ---: |
| E5 gốc | 10/16 | 11/16 | 3/18 |
| E5 rewrite | 10/16 | 12/16 | 3/18 |
| BM25 gốc | 8/16 | 10/16 | 6/18 |
| BM25 rewrite | 11/16 | 11/16 | 4/18 |
| Hybrid gốc | 9/16 | 11/16 | 3/18 |
| Hybrid rewrite | 12/16 | 12/16 | 2/18 |

Tavily giúp Hybrid + rewrite trả đúng vị trí **St. Trina** ở IB-SUP-09. IB-GS-253 cải thiện một phần về công thức hai loại Pot. Điểm chung của cấu hình này giữ 12/16, do một ca khác rơi từ đủ xuống một phần dù Auto xác định nguồn local đủ. Hai lượt sinh độc lập có thể cho mức chi tiết khác nhau ngay cả khi không tìm web.

Chạy kiểm tra bổ sung qua API JSON/SSE của Agent đầy đủ trên 6 câu đại diện. Cả 6 có phản hồi cuối qua 7 request HTTP 200. IB-GS-278 hỏi lại rồi trả 20% giảm sát thương phép PvE. IB-SUP-06 tính đúng 425/400 HP và chênh 25 HP. IB-GS-228 vẫn thiếu mốc đỉnh tháp sau Commander Niall. Agent báo nguồn local đủ cho cả sáu và không gọi Tavily trong phép kiểm tra API này.

## Ca chẩn đoán và lựa chọn cấu hình

- **IB-SUP-08** gõ `STONESWROD`. Cả sáu cấu hình tìm được trang Stonesword Key, nhưng bước hiểu yêu cầu đã quyết định hỏi lại trước khi dùng bằng chứng. Đây là lỗi ưu tiên nếu muốn xử lý lỗi gõ linh hoạt hơn.
- **IB-GS-119 và 120** hỏi về Soap trong Elden Ring bằng ngữ cảnh ngầm. Cổng ý định từ chối cả hai, minh họa lỗi phạm vi độc lập với việc xếp hạng.
- **IB-GS-296** có đủ trang tham chiếu ở BM25 và vẫn thiếu đoạn chứng minh Carian Slicer cần 14 Intelligence và cách mở mua. Cần đo chunk dùng được và chọn đúng đoạn có yêu cầu, không chỉ đo trúng trang.
- **IB-GS-245 và IB-SUP-06** cùng dùng tỷ lệ Prawn/Crab. Hybrid + rewrite đưa hai tỷ lệ vào context để phân biệt chênh lệch 5 điểm phần trăm với kết quả chênh 25 HP ở tình huống 500 sát thương giả định.
- Với dữ liệu này, giữ **Hybrid + rewrite** làm cấu hình mặc định. Chênh Accuracy so với BM25 + rewrite chỉ là 2 câu trong 195 câu. Xem xét giữ query tiếng Anh gốc khi đã rõ và chỉ bật rewrite khi cần; cần đợt đo riêng trước khi đổi hành vi.

Đầu ra local trong `backend/data/research_runs/2026-11-14-s4-retrieval-matrix/`. `rewrites.jsonl` giữ query và quyết định, `retrieval.jsonl` giữ hạng và context, `answers-off.jsonl` và `answers-auto.jsonl` giữ đầu ra, `scores-off.jsonl` và `scores-auto.jsonl` giữ điểm và lý do. `summary.json` giữ tất cả các bảng theo nhóm. `agent-auto/report.json` giữ kiểm tra qua API. Checkpoint chỉ chứa tập câu kiểm thử và dữ liệu bằng chứng, không cần đưa bí mật cấu hình vào báo cáo.
