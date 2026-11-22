# Báo cáo NLP — Hệ thống Agentic RAG hỏi đáp lore Elden Ring

Báo cáo môn Xử lý ngôn ngữ tự nhiên của nhóm 4 Hollows, viết bằng LaTeX theo định dạng báo cáo học phần
(lớp `ictureport.cls`, XeLaTeX + Biber). Bản xuất: [PDF](BaoCao_NLP_IndexBeast.pdf) · [DOCX](BaoCao_NLP_IndexBeast.docx).

| Tệp / thư mục | Nội dung |
|---|---|
| `main.tex`, `metadata.tex`, `preamble.tex`, `ictureport.cls` | Khung tài liệu, trang bìa, cấu hình |
| `frontmatter/` | Lời cảm ơn, phân công nhiệm vụ, từ viết tắt |
| `chapters/` | Mở đầu, Chương 1–4, Kết luận, Phụ lục |
| `references.bib` | 30 tài liệu tham khảo (đã kiểm chứng qua arXiv API và Crossref ngày 23/11/2026) |
| `tools/export_docx.py` | Xuất DOCX từ mã LaTeX (cần main.pdf, main.aux, main.bbl đã biên dịch) |
| `khung-*.md` | Khung báo cáo dùng để viết |

## Biên dịch

```powershell
xelatex main; biber main; xelatex main; xelatex main
```

Xuất DOCX (cần Pandoc, `pip install pymupdf python-docx`):

```powershell
python tools/export_docx.py --pandoc <pandoc.exe> --xelatex <xelatex.exe>
```

Bản DOCX có mục lục dạng trường: mở bằng Word rồi nhấn F9 để cập nhật số trang.
