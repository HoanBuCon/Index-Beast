# Tiêu chí đánh giá IndexBeast Sprint 4

Đơn vị chấm là một câu hỏi chính, gồm cả các lượt bổ sung trong cùng hội thoại. Cố định câu hỏi, đáp án tham chiếu, nguồn, điều kiện và bản dữ liệu trước khi chạy. Chấm từ nội dung trả về và bằng chứng được trích. Giữ cùng rubric và tập câu khi đối chiếu hai phiên bản.

| Tiêu chí | 2 điểm | 1 điểm | 0 điểm |
| --- | --- | --- | --- |
| Độ đúng của đáp án dữ kiện | Đủ ý bắt buộc, đúng chủ thể, điều kiện và ngôn ngữ yêu cầu | Có ít nhất một ý đúng nhưng thiếu ý quan trọng hoặc thêm chi tiết sai không làm đảo ngược kết luận chính | Sai kết luận chính, nhầm thực thể, không trả lời, hỏi lại dù đề đã đủ chi tiết hoặc xảy ra lỗi |
| Độ bám nguồn | Các khẳng định dữ kiện quan trọng được trích đoạn hỗ trợ trực tiếp hoặc suy ra từ điều kiện đã nêu | Nguồn xác nhận một phần, còn ít nhất một khẳng định đáng kể chưa có căn cứ trong các đoạn đã trích | Trích dẫn không hỗ trợ kết luận chính, sai chủ thể hoặc mâu thuẫn với nội dung câu trả lời |
| Lượt sau khi hỏi bổ sung | Câu trả lời cuối dùng đúng thông tin mới và đủ ý trong đáp án lượt sau | Dùng thông tin mới nhưng trả lời thiếu ý hoặc giữ chi tiết cũ đã bị người dùng thay thế | Lỗi, hỏi lặp khi dữ kiện đã đủ, bỏ qua thông tin mới hoặc chọn sai thực thể |

- **Ca hành vi** chấm đạt hoặc chưa đạt. Ca ngoài phạm vi đạt nếu nhận diện đúng và trả lời phù hợp. Ca mơ hồ đạt nếu hỏi thông tin thực sự cần để phân biệt các khả năng, hoặc trả lời có điều kiện khi đáp án tham chiếu cho phép. Khi ca có kịch bản lượt sau, ghi thêm điểm riêng của lượt cuối.
- **Accuracy** là số ca dữ kiện đạt 2 điểm chia cho tất cả ca dữ kiện đã chạy, kể cả ca lỗi. Mẫu số độ bám nguồn là số ca có trích dẫn. Ghi riêng số ca dữ kiện không có trích dẫn để chỉ số bám nguồn không che tình trạng thiếu nguồn.
- **Recall@5 và MRR@5** đối chiếu URL chuẩn hóa của năm trang local khác nhau đầu tiên với các trang tham chiếu. Recall@5 tính tỷ lệ trang tham chiếu được tìm thấy trên từng câu. MRR@5 dùng nghịch đảo hạng của trang tham chiếu đầu tiên, bằng 0 nếu cả năm trang đều thiếu. Tổng hợp trung bình theo câu có nguồn tham chiếu.
- **API và thời gian** ghi số câu chính, lượt bổ sung, HTTP, lỗi SSE và độ trễ từ gửi đến kết thúc ca. SSE chỉ hoàn tất khi có `done`. So sánh độ trễ khi cách chạy và mức song song tương ứng. HTTP 200 không chấm thay độ đúng.
- **Rà soát bằng chứng** kiểm tra nguồn đúng phiên bản, chủ thể, vị trí và điều kiện. Khi hai đáp án hợp lệ hoặc nhãn chưa đủ rõ, ghi chú điểm tranh luận và giữ nguyên điểm theo phiên bản đã khóa. Sửa nhãn trong phiên bản tập câu kế tiếp.

Mỗi dòng điểm cần có ID, phiên bản lượt đo, người chấm, điểm áp dụng và lý do khi bị trừ. Dùng `null` khi tiêu chí không áp dụng. Lượt chấm của Codex và xác nhận của người review được lưu riêng. [Báo cáo gốc](../testing/2026-11-14_s4-evaluation-100.md) · [Bộ câu và cách chạy](../../backend/eval/README.md)
