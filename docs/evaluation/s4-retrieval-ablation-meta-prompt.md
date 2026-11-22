# Meta-prompt đánh giá truy xuất IndexBeast

**Vai trò.** Thực hiện đánh giá NLP cho IndexBeast và kiểm chứng từng số liệu từ đầu ra đã lưu.

**Tập đo.** Khóa 200 ca S4 và một tập bổ sung riêng cho phép tính, dấu câu, lỗi khoảng trắng, gõ nhầm tên và truy vấn thiếu dấu. Giữ nguyên nhãn vàng, đối chiếu nguồn của ca bổ sung với artifact local. Dùng cùng câu, ngôn ngữ, collection và bộ lọc cho mọi cấu hình. Chọn tập Auto trước khi xem kết quả.

**Thiết kế.** Đo E5, BM25 và Hybrid RRF với câu gốc và query do Agent hiện hành đề xuất. Ghi quyết định, query, lý do fallback và số lượt gọi. Dùng cùng bản rewrite cho cả ba phương pháp. Đo theo trang và trích đoạn được gắn nhãn, ghi thứ hạng và context thật. Giữ thứ tự retriever khi cấp context cho cùng một generator. Dùng câu gốc để sinh đáp án nhằm đo tác động của rewrite lên retrieval. Nếu chạy thêm Auto, ghi riêng lượt tìm web và nguồn được dùng. Mô tả khác biệt giữa harness và pipeline hội thoại đầy đủ.

**Chấm.** Ghi từng câu và lỗi. Chấm đủ ý, bám nguồn, tính toán và hành vi hỏi lại hoặc ngoài phạm vi theo rubric S4. Khi dùng LLM chấm, ẩn tên cấu hình, ghi model, lưu lý do và báo rõ phạm vi đối chiếu bằng tay. Tách Accuracy dữ kiện khỏi ca hành vi. Báo phân nhóm ngôn ngữ, độ khó, phép tính, lỗi gõ và truy vấn có nhiễu. Giữ mẫu số, tỷ lệ fallback và số ca chưa hoàn thành. Không gộp số liệu Auto với Off.

**Thực thi.** Chạy kiểm tra nhỏ trước, sau đó hoàn thành ma trận thật. Ghi kết quả trung gian để tiếp tục được và kiểm tra số hàng theo mỗi cấu hình. Đọc collection hiện tại qua truy vấn. Giữ cấu hình ứng dụng và dữ liệu vàng S4. Báo cáo kết quả, giới hạn, lệnh tái lập và dẫn đến đầu ra có thể kiểm tra lại.
