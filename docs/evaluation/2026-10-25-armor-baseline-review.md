# Chấm RAG baseline armor — 25/10/2026

**Lượt chạy:** `20261025T144625694379Z`

**Model:** `deepseek-flash`

**Dữ liệu:** 240 dòng armor, top-5 nguồn, 5 câu Việt và 5 câu Anh.
**Người đánh giá:** trợ lý Codex, đối chiếu câu hỏi, đáp án tham chiếu và đoạn CSV đã lưu. Không chạy lại notebook hoặc gọi API.

Điểm theo thang 0–2 hiện có. Correctness đo trả lời đúng và đủ cho câu hỏi; faithfulness đo các claim được hỗ trợ bởi ngữ cảnh. Tính tập trung/ngắn gọn được nhận xét riêng, không tự trừ điểm chỉ vì có thêm chi tiết đúng nguồn.

| Câu | Correctness | Faithfulness | Nhận xét |
|---|---|---|---|
| VI01 | 2 | 2 | Trả lời đúng người mặc là Gideon Ofnir, the All-Knowing; trích [2] đúng All-knowing Armor, không dùng nhầm bản altered ở hạng 1. Ngắn gọn, đúng trọng tâm. |
| VI02 | 2 | 2 | Đáp án 'đọc vận mệnh trong các vì sao' đúng và được [1] hỗ trợ. Giữ đúng sắc thái 'được cho là' của nguồn. Câu thêm về glintstone sorcerers cũng có nguồn nhưng không được hỏi; nên bỏ để tập trung hơn. |
| VI03 | 2 | 2 | Trả lời đúng hiệu ứng che/giảm tiếng bước chân và dẫn [2] đúng bản Armor thường. Toàn bộ thông tin được nguồn hỗ trợ. Cụm 'làm nghẹt tiếng bước chân' chưa tự nhiên; nên dùng 'làm giảm tiếng bước chân'. |
| VI04 | 2 | 2 | Xác định đúng gia đình hoàng gia Carian và trích [2] đúng Carian Knight Armor thay vì Gauntlets ở hạng 1. Đáp án đủ ý, một câu, không thêm diễn giải ngoài nguồn. |
| VI05 | 2 | 2 | Trả lời đúng quý tộc ở kinh đô và dẫn [1]. Câu thêm về Shattering và cuộc sống vô tận có trong nguồn nhưng không cần để trả lời câu hỏi. Nên bỏ câu thứ hai; nếu giữ, dịch 'undead' chính xác hơn thành 'những người chết sống lại'. |
| EN01 | 2 | 2 | Đúng cả hai ý được hỏi: Gideon Ofnir mặc giáp và run sợ khi nhìn vào ý chí Queen Marika; đều trích [1]. Không tự diễn giải nguyên nhân sâu hơn điều nguồn nêu. Đủ ý và ngắn gọn. |
| EN02 | 2 | 2 | Đúng khác biệt bản altered nhẹ hơn, trích [1] và [2] khớp hai biến thể. Các trọng lượng 3.2 và 4.1 có trong payload nên không phải bịa. Có thể rút còn một câu nếu chỉ cần khác biệt theo phần mô tả. |
| EN03 | 2 | 2 | Nêu đúng ý chính 'the night sky no longer cradles fate', trích [1] phù hợp và giữ 'said to be' cho thông tin nguồn. Phần về hậu duệ glintstone sorcerers không cần cho câu hỏi night sky/fate; có thể bỏ. |
| EN04 | 2 | 2 | Trả lời đúng nguồn gốc được đồn là Numen với quan hệ gần gũi với Marika, trích [1]. Giữ nguyên 'rumored', không chuyển tin đồn thành sự thật chắc chắn. Chi tiết all women cũng có trong nguồn. |
| EN05 | 2 | 2 | Xác định đúng man-wolf Blaidd từ [2]. Câu về Gauntlets được [3] hỗ trợ nhưng hỏi riêng Blaidd's Armor nên không cần thêm. Giữ câu đầu là đủ trọng tâm. |

## Tổng hợp

| Ngôn ngữ | Số câu | Hit@5 | MRR@5 | Correctness | Faithfulness |
|---|---|---|---|---|---|
| vi | 5 | 5/5 | 0.700 | 10/10 | 10/10 |
| en | 5 | 5/5 | 0.900 | 10/10 | 10/10 |

Tổng correctness **20/20**, faithfulness **20/20** trên chính 10 câu demo này. Đây là mức phù hợp với nội dung CSV đã truy xuất, chưa xác minh tính chính xác của nguồn so với game. Các câu đã được chọn từ armor có trong subset nên không suy rộng thành chất lượng 100% của chatbot.

## Điểm cần cải thiện

- VI02, VI05, EN03 và EN05 còn thêm thông tin không được hỏi. Có thể nhấn mạnh trong prompt: chỉ trả lời khía cạnh được hỏi, bỏ các fact phụ dù có trong nguồn.
- VI03 nên dịch “muffles the sound of footsteps” thành “làm giảm tiếng bước chân”.
- VI01, VI03, VI04 và EN05 có đúng tài liệu ở hạng 2, trong khi hạng 1 là biến thể hoặc món khác. Model đã chọn được nguồn phù hợp trong top-5, nhưng retrieval vẫn có chỗ cải thiện.
- Bổ sung câu không có đáp án, câu dễ nhầm biến thể, câu diễn đạt lại không chứa nguyên tên armor và bộ test độc lập trước khi kết luận chất lượng.

## File liên quan

- [Notebook](../../backend/notebooks/01_rag_baseline_e5_bm25.ipynb), cell MANUAL_REVIEW đã điền điểm và nhận xét.
- [Kết quả JSON](../../backend/data/notebook-baseline/20261025T144625694379Z_9204a4b5615b.json), giữ nguyên đáp án và nguồn, bổ sung điểm cùng metadata đánh giá.

Để hiển thị tổng hợp mới trong notebook, chỉ chạy cell MANUAL_REVIEW và cell tổng hợp. Không cần chạy lại cell gọi DeepSeek.
