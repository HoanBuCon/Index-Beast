# Meta-prompt · Rà soát golden set S4 thay phần việc TV2

## Vai trò và ủy quyền

Thực hiện phần việc TV2 (UncleThing) theo yêu cầu của TV3 ngày 16/11/2026. Người dùng cho biết TV2 nhận trách nhiệm và giao AI làm thay. Codex là bên thực hiện; không mô tả đây là thao tác kiểm tra trực tiếp của con người. Nếu ghi nhận duyệt thay TV2, lưu rõ hình thức ủy quyền, người thực hiện và nguồn ủy quyền trong từng hồ sơ.

## Phạm vi

Rà đủ 200 câu IB-GS-101–300 cùng bằng chứng, bao gồm 26 hồ sơ có `assistant_review.outcome=revised` và mọi lượt bổ sung. Chỉ đọc corpus/artifact/report local. Không gọi DeepSeek/Tavily, không truy cập web, không chạy model, embedding, indexing hay cập nhật dịch vụ. Không commit/push/merge.

## Quy trình

1. Kiểm tra Git, giữ thay đổi có sẵn, dùng nhánh riêng theo quy ước. Đọc rubric, validator, golden set, phiếu review và handover liên quan.
2. Kiểm schema, ánh xạ ID, URL, chunk ID, vị trí quote và SHA-256 trên corpus S4. Lưu hash đầu vào để tái lập.
3. Đọc từng câu, đáp án và đoạn nguồn. Kiểm chủ thể, điều kiện, con số, phép tính, ngôn ngữ, mức độ khó, phạm vi và sự cần thiết của hỏi lại/từ chối. Với ca không có nguồn, kiểm ý định và kịch bản hành vi. Với 26 ca sửa, đọc nhận xét cũ và kiểm lại độc lập theo cùng tiêu chí.
4. Không suy rằng hash khớp là đáp án đúng. Tìm thêm trong corpus khi quote thiếu. Không dùng lời đáp model làm bằng chứng nguồn. Nhãn release `unknown` không đồng nghĩa ngoài phạm vi.
5. Ghi nhận xét theo từng ID. Chỉ duyệt ca đủ bằng chứng; ca mơ hồ, thiếu hoặc mâu thuẫn ghi `changes_requested` với lý do và hướng xử lý. Giữ bộ câu đã khóa và điểm benchmark lịch sử; đề xuất sửa phiên bản kế tiếp nếu cần.
6. Lưu kết quả rà thay TV2 với `performed_by=Codex`, `method=delegated_ai_local_review` và `human_direct_review=false`. Người chịu trách nhiệm TV2 theo lời người dùng, không giả lập chữ ký hay xác nhận trực tiếp của TV2.
7. Chạy validator offline, kiểm thử phù hợp, kiểm liên kết/UTF-8 và diff. Viết báo cáo kết quả, handover và cập nhật danh sách bàn giao. Phân biệt kết quả kiểm local với kiểm chứng website/public và benchmark chưa chạy lại.

## Sản phẩm

- Phiếu review từng ca có kết luận và nguồn ủy quyền rõ ràng.
- Báo cáo tổng hợp: số ca đạt/cần sửa, 26 ca sửa, lỗi phát hiện, hash đầu vào, lệnh kiểm và giới hạn.
- Handover cùng nhánh; không thay kết quả đo lịch sử hay tuyên bố đánh giá độc lập bởi con người.
