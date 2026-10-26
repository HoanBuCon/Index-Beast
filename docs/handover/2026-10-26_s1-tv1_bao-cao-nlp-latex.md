# Báo cáo môn NLP (LaTeX) — TV1

| | |
|---|---|
| Ngày | 26/10/2026 |
| Người lập | TV1 (Hoanbucon) |
| Nhánh | `docs/s1-tv1-bao-cao-nlp` |

## 1. Đã làm

Viết báo cáo môn Xử lý ngôn ngữ tự nhiên về Index Beast theo mẫu LaTeX ICTU: bìa, mục lục, mở đầu, 3 chương, 18 tài liệu tham khảo, 37 trang. Mã nguồn và `main.pdf` nằm ở [`docs/bao-cao-nlp/`](../bao-cao-nlp/README.md).

## 2. Nguyên tắc nội dung

- Chỉ dùng số liệu đã có trong repo và notebook đã lưu; không chạy notebook, không tải mô hình, không gọi API LLM.
- Phần thiết kế chưa triển khai (xếp hạng lại, tìm web dự phòng, `/chat`, chunking ADR-003 đang đề xuất) được ghi rõ là thiết kế.
- Thí nghiệm cơ sở: 240 bản ghi `armors.csv`, 10 câu, Hit@5 = 10/10, MRR = 0,800; chấm tay có hỗ trợ AI, không độc lập. Báo cáo nêu rõ không suy ra chất lượng hệ thống hoàn chỉnh.

## 3. Kiểm tra

- `xelatex` ba lượt, không còn Overfull, danh mục bảng đánh số liên tục 1–16.
- Đã xem lại các trang bìa, sơ đồ và bảng trong PDF.
- Chưa kiểm tra bằng người đọc thứ hai.

## 4. Việc còn lại

- Điền họ tên thành viên 3, 4 và giáo viên hướng dẫn trong `bia.tex`; xác nhận tên học phần.
- Nhờ TV2/TV3 đối chiếu phần dữ liệu và thí nghiệm của mình.
