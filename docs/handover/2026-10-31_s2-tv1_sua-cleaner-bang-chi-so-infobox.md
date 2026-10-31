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
- **Chạy thật trên máy TV1** (31/10, sau khi merge `develop` vào nhánh): `python -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --output-dir data/clean_runs/s2-full-v3-tv1-test`. Mất 5 phút 4 giây, exit 0, `input_artifacts_unchanged=true`, 0 lời gọi mạng, 0 ghi DB. So với `s2-full-v2`:
  - Nội dung **keep** trùng khớp từng dòng: 73.559/73.559 dòng; số block keep 43.581 không đổi. Số record keep tăng từ 20.235 lên 20.250 chỉ vì khối chỉ số (excluded) chen giữa các trường infobox, làm một record bị tách đôi; chữ không đổi.
  - `review.csv` tăng từ 55.560 lên 58.160 dòng: thêm 1.551 dòng `infobox_stats_group` (1.503 trang), 721 `infobox_placeholder_stats`, 342 `infobox_unlabeled_value`.
  - `unclassified_structure` giảm 14 record: 258 trang có infobox chỉ gồm smart group, trước đây bị dồn nguyên khối thành một chuỗi dính chữ, nay tách đúng loại. Đã đối chiếu các trang có số liệu (vd. 5676 `Fire: -20%`, 6199 Samurai `HP: 455`): giá trị đều còn, chỉ đổi định dạng.
  - Moonveil có trong `review.csv`: `Stats | Attack Power / Physical: 73 | Guarded Damage Negation / Physical: 31 | …`.
  - Thư mục `s2-full-v3-tv1-test` chỉ để kiểm thử, **không phải bản bàn giao**; TV2 nên tự chạy lại vào thư mục chính thức. Chưa chạy chunk (máy TV1 không có `tokenizer.json`), chưa nạp DB, chưa index.
- Cùng lượt: backend 391 unit + 15 integration passed; web 24/24, bot 21/21; lint/format/typecheck đạt.

## Việc tiếp theo

1. TV2 chạy lại clean vào thư mục mới, vd. `python -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --output-dir data/clean_runs/s2-full-v3`. Kiểm `review.csv` có lý do `infobox_stats_group`, `content_clean_all.csv` không đổi phần lore. Sau đó chunk lại. Chunk lúc này chưa khác vì chỉ số vẫn `excluded`.
2. Sau CHANGE-REQ gameplay: việc #2 đổi `infobox_stats_group` (và các lý do gameplay khác) thành `keep`; việc #3 gộp infobox mỗi trang thành một chunk.
3. Đo baseline (#6) trước khi thay corpus đang phục vụ.
