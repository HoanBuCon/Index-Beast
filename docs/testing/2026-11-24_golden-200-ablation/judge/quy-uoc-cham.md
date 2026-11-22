Quy ước Claude chấm (24/11), áp dụng mọi lô:
- Đoạn nguồn trong gói chấm bị cắt ở 450 ký tự: ý có thể nằm ở phần bị cắt thì không trừ faithfulness.
- Chi tiết phụ đúng game nhưng không có trong đoạn trích (đường đi chung, tên nơi phụ): không trừ.
- Ý chính trả lời câu hỏi hoặc chi tiết then chốt không có cơ sở: faithfulness 1. Kết luận chính sai thực thể: correctness 0.
- correctness 1: đúng thực thể nhưng thiếu ý bắt buộc của đáp án tham khảo, hoặc có chi tiết sai không đảo kết luận.
- insufficient_evidence: "nếu là X" mà chỉ đưa một khả năng = fail (vẫn là đoán); liệt kê có điều kiện ≥2 khả năng = pass.
- Số trích `[n]` phải so với `source.index` của từng nguồn, **không so với vị trí trong danh sách**. App chỉ trả các nguồn được trích và giữ số gốc, nên danh sách có thể bị hở số (ví dụ 1, 2, 4).
  - Sửa ngày 24/11: trong các lô đầu, gói chấm đánh số lại nguồn theo vị trí. Vì vậy 175 câu bị trừ faithfulness oan vì "trích số không tồn tại", và đã được trả về faithfulness 2. Mỗi câu được sửa có ghi chú trong `reason`.
  - 5 câu vẫn giữ faithfulness 1 vì còn lỗi bám nguồn khác.
