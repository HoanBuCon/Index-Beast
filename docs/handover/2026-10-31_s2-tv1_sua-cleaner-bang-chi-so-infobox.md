# Sửa cleaner: không còn mất bảng chỉ số trong infobox

| | |
|---|---|
| Ngày | 31/10/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `fix/s2-tv1-infobox-bang-chi-so` (từ `origin/develop` tại `f089538`; chưa có PR khi viết) |
| Căn cứ | Việc #1 trong [đề xuất dữ liệu đã duyệt](2026-10-31_s2-tv1_khao-sat-du-lieu-va-de-xuat.md) |

## Lỗi

`html_clean.infobox()` chỉ duyệt `.pi-data`. Các khối `.pi-smart-group` của portable-infobox không có class `pi-data`, nên bị bỏ qua: không vào clean, cũng không vào ledger `removed`. Có 3.269 khối như vậy trong 4.164 trang: 2.387 bảng (Attack Power, Guarded Damage Negation, Attributes, Damage Negation/Resistance của giáp…), 540 lưới nhãn/giá trị (yêu cầu thuộc tính của phép, resistance của boss) và 342 giá trị không nhãn (tên tiếng Nhật).

## Đã sửa

- `core/text/html_clean.py`:
  - Duyệt `.pi-data` và `.pi-smart-group` theo thứ tự DOM.
  - Bảng được render thành dòng giữ nguyên giá trị nguồn: tiêu đề nhóm (`th colspan`) ghép với cặp nhãn/giá trị, vd. `Attack Power / Physical: 73`, `Guarded Damage Negation / Physical: 31`. Bảng có header từng cột thì giữ dạng hàng: `Attribute | Required | Scaling`, `Intelligence: | 23 | C`.
  - Lưới được render thành `Int: 0, Fth: 12`.
  - Khối được đặt dưới tiêu đề nhóm `pi-header` (Stats, Attributes Required…). Trang có nhiều infobox thì thêm tên infobox (vd. `Malenia, Goddess of Rot`).
  - Khối không có số liệu (chỉ `%`) ghi ledger `infobox_placeholder_stats`; giá trị không nhãn ghi `infobox_unlabeled_value`.
- `core/text/lore_policy.py`: kind mới `infobox_stats` → `excluded` với lý do `infobox_stats_group`. **Chưa đưa vào corpus**: dữ liệu nằm trong `review.csv` để việc #2 (nhận lại gameplay, chờ CHANGE-REQ) chỉ cần đổi một dòng policy.
- Tăng phiên bản: `html_clean` `s2-clean-2.1`, transform full `s2-full-clean-1.1`. Chunker chấp nhận cả phiên bản cũ và mới.

## Kiểm tra

- `tests/unit/test_infobox_stats.py` (6 test, HTML rút gọn theo cấu trúc thật): bảng vũ khí, bảng thuộc tính, lưới của phép, khối trống, hai infobox của boss, và bất biến "mọi giá trị trong `.pi-smart-group` phải có trong block hoặc ledger".
- Toàn bộ backend: **391 passed**; ruff, format, `export_openapi --check` đạt.
- Chạy cleaner mới trên **toàn bộ 4.164 raw cuối, chỉ trong bộ nhớ** (172 giây, 0 lỗi):
  - 2.209 khối chỉ số trên 1.503 trang; 722 khối trống và 342 giá trị không nhãn được ghi ledger.
  - Trong 1.450 trang có Attack Power/Damage Negation/Attribute/Resistance/Poise trong smart group, chỉ 1 trang (Unarmed) không có đủ chữ khóa. Đã xem trực tiếp: phần thiếu là bảng để trống, được ghi `infobox_placeholder_stats`. Không còn trang nào mất chỉ số không dấu vết.
- **Chưa** ghi artifact mới, chạy lại clean/chunk vào thư mục dữ liệu, nạp DB hay index.

## Việc tiếp theo

1. TV2 chạy lại clean vào thư mục mới, vd. `python -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --output-dir data/clean_runs/s2-full-v3`. Kiểm `review.csv` có lý do `infobox_stats_group`, `content_clean_all.csv` không đổi phần lore. Sau đó chunk lại. Chunk lúc này chưa khác vì chỉ số vẫn `excluded`.
2. Sau CHANGE-REQ gameplay: việc #2 đổi `infobox_stats_group` (và các lý do gameplay khác) thành `keep`; việc #3 gộp infobox mỗi trang thành một chunk.
3. Đo baseline (#6) trước khi thay corpus đang phục vụ.
