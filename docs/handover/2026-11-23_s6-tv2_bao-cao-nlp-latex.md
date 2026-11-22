# TV2 · Báo cáo NLP bằng LaTeX theo định dạng học phần (23/11/2026)

Sprint 6, thẻ 6.12 (báo cáo). Nhánh `docs/bao-cao-nlp-latex` (tách từ `develop`), PR vào `develop`.
Việc do trợ lý AI (Claude Code) thực hiện theo yêu cầu của TV2; nội dung cần cả nhóm đọc lại trước khi nộp.

## Phạm vi

- Xóa báo cáo LaTeX cũ trong `docs/bao-cao-nlp/` (sai định dạng), giữ `assets/ictu_logo.png`.
- Viết lại toàn bộ báo cáo theo lớp `ictureport.cls` của báo cáo mẫu môn Học sâu (XeLaTeX + Biber), sửa trang bìa
  thành "HỌC PHẦN XỬ LÝ NGÔN NGỮ TỰ NHIÊN", "Giảng viên hướng dẫn: TS. Trần Văn Khánh", 4 thành viên.
- Bám khung `khung-bao-cao-agentic-rag.md` và `khung-xuong-bao-cao-chi-tiet.md` (lấy từ nhánh
  `origin/docs/cau-truc-bao-cao-nlp`). Chỉ mô tả kiến trúc cuối cùng (một Agent, 9 tool, hybrid E5 + BM25 + RRF,
  reranker MiniLM-L12 cục bộ, kiểm trích dẫn, `run_python`); không đưa ADR hay lịch sử thay đổi.
- Xuất `BaoCao_NLP_IndexBeast.pdf` (111 trang, phần thân khoảng 93 trang) và `BaoCao_NLP_IndexBeast.docx`.

## File

| File | Nội dung |
|---|---|
| `docs/bao-cao-nlp/main.tex`, `metadata.tex`, `preamble.tex`, `ictureport.cls` | Khung tài liệu |
| `docs/bao-cao-nlp/frontmatter/`, `chapters/` | Nội dung |
| `docs/bao-cao-nlp/references.bib` | 30 tài liệu (2009–2025) |
| `docs/bao-cao-nlp/tools/export_docx.py` | Xuất DOCX (TikZ → PNG, `\ref`/`\cite` → số theo PDF, Pandoc, python-docx) |
| `docs/bao-cao-nlp/README.md` | Cách biên dịch |

## Kiểm tra đã chạy

- Biên dịch XeLaTeX + Biber thành công, 0 lỗi, 0 tham chiếu/trích dẫn chưa định nghĩa, 0 overfull hbox.
- 30/30 tài liệu tra trên arXiv API và Crossref: đều tồn tại đúng tên, năm, nơi công bố. Riêng BM25 ghi tập/trang
  theo nhà xuất bản (Crossref ghi khác, có chú thích trong `references.bib`).
- Số liệu Chương 4 lấy từ `docs/testing/2026-11-24_golden-200-ablation/` (README, `summary.json`); p50/p95 theo ngôn ngữ
  tính lại từ `rows` bằng nearest-rank. Số liệu corpus lấy từ các handover TV2 ngày 12, 13, 20/11.
- Đoạn mã `run_python` minh họa trong Chương 3 đã chạy thật qua `app.rag.python_sandbox.run_python`.
- Một vòng phản biện bằng 2 sub-agent Sonnet (trích dẫn/trung thực; kỹ thuật so với code). Đã sửa mọi lỗi được xác nhận
  (tác giả thiếu ở một mục bib, một trích dẫn Toolformer đặt sai chỗ, mô tả nguồn số liệu đánh giá, p95 theo ngôn ngữ,
  thời hạn web 90 s, cú pháp `/setup` `/clear`, mô tả container, thinking mặc định tắt, bỏ bảng phương án kiểu ADR).
  Không chạy thêm vòng.
- GitNexus đã cài và `gitnexus analyze` để lập bản đồ mã (thư mục `.gitnexus` và `AGENTS.md`/`CLAUDE.md` ở gốc do công cụ
  sinh ra không được commit).

## Hạn chế, việc còn lại

- Bản DOCX: mục lục là trường Word, cần mở bằng Word và nhấn F9; bảng và hình chuyển tự động nên nên rà lại bố cục.
- Ảnh giao diện web/Discord đã bổ sung ở Mục 3.7 (xem mục Bổ sung bên dưới).
- Lượt rà soát cuối của golden set có trợ lý AI hỗ trợ; báo cáo đã ghi rõ.
- Máy viết báo cáo cài thêm MiKTeX và Pandoc (winget, phạm vi người dùng).

## Bổ sung: sơ đồ draw.io và ảnh demo (23/11/2026)

- 11 sơ đồ vẽ bằng draw.io thay cho hình TikZ: nghiệp vụ dạng làn bơi, các workflow, sơ đồ tuần tự, kiến trúc,
  triển khai, ERD, use case, LangGraph, RAG, ReAct. Nguồn XML: `docs/bao-cao-nlp/figures/drawio/*.drawio`
  (sinh bằng `tools/drawio_diagrams.py`); PNG xuất bằng draw.io desktop CLI vào `figures/`.
  Lệnh xuất: `draw.io.exe -x -f png -s 2 -b 12 -o figures/<tên>.png figures/drawio/<tên>.drawio`.
- 10 ảnh demo trong `figures/screens/`, chụp từ hệ thống production ngày 23/11/2026 bằng Edge điều khiển qua Playwright:
  trang chủ, chat trống, câu trả lời có trích dẫn (câu không dấu, gõ sai), popover nguồn, câu build (bảng 8 chỉ số,
  tổng 139), trang trace quản trị (chỉ cắt khung trace), mobile, và 2 câu `/ask` thật của bot trên Discord
  (đã cắt chỉ giữ khung tin nhắn). Câu trả lời là thật, không dàn dựng; 2 lệnh `/ask` gửi vào kênh bot với sự đồng ý của TV2.
- Thêm vào Mục 3.7; ghi thêm hạn chế: embed Discord không hiển thị bảng Markdown.
- PDF 117 trang; DOCX có đủ 24 hình.
