Quy ước Claude chấm (24/11), áp dụng mọi lô:
- Đoạn nguồn trong gói chấm bị cắt ở 450 ký tự: ý có thể nằm ở phần bị cắt thì không trừ faithfulness.
- Chi tiết phụ đúng game nhưng không có trong đoạn trích (đường đi chung, tên nơi phụ): không trừ.
- Ý chính trả lời câu hỏi hoặc chi tiết then chốt không có cơ sở: faithfulness 1. Kết luận chính sai thực thể: correctness 0.
- correctness 1: đúng thực thể nhưng thiếu ý bắt buộc của đáp án tham khảo, hoặc có chi tiết sai không đảo kết luận.
- insufficient_evidence: "nếu là X" mà chỉ đưa một khả năng = fail (vẫn là đoán); liệt kê có điều kiện ≥2 khả năng = pass.
