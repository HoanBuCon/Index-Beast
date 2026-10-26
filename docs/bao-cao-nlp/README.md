# Báo cáo môn Xử lý ngôn ngữ tự nhiên: Index Beast

Báo cáo dự án theo mẫu LaTeX của khoa CNTT, trường ĐH CNTT và Truyền thông (ICTU). Nội dung chỉ dùng số liệu đã có trong repo (Sprint 1); không chạy lại notebook hay gọi LLM để viết báo cáo.

## Biên dịch

Cần XeLaTeX (MiKTeX hoặc TeX Live) và phông Times New Roman.

```bash
xelatex main.tex && xelatex main.tex && xelatex main.tex
```

Chạy ba lần để mục lục, danh mục hình và bảng được cập nhật. Kết quả: `main.pdf`.

## Cấu trúc

| Tệp | Nội dung |
|---|---|
| `main.tex` | Khai báo gói, macro bảng, kiểu sơ đồ TikZ |
| `bia.tex` | Trang bìa |
| `mo_dau.tex` | Mở đầu |
| `chuong1.tex` | Chương 1: Cơ sở lý thuyết |
| `chuong2.tex` | Chương 2: Bài toán, phương pháp và mô hình |
| `chuong3.tex` | Chương 3: Thử nghiệm và đánh giá |
| `tai_lieu.tex` | Tài liệu tham khảo |
| `assets/` | Logo trường |

## Cần điền trước khi nộp

- Họ tên thành viên 3 và 4, giáo viên hướng dẫn trong `bia.tex`.
- Xác nhận tên học phần ở trang bìa.
- Thử nghiệm Chương 3 là trên tập con 240 bản ghi `armors.csv`, chấm tay có hỗ trợ AI; đã nêu giới hạn trong báo cáo.
