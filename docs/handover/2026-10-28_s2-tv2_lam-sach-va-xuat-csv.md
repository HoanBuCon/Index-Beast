# Bàn giao TV2 Sprint 2 làm sạch dữ liệu và xuất CSV

Ngày: 28/10/2026. Chủ sở hữu: TV2 (UncleThing). Thẻ: Làm sạch & chuẩn hoá nội dung; yêu cầu FR-ING-03 và phần metadata cần cho artifact. Nhánh: feature/s2-tv2-lam-sach-va-xuat-csv, tạo --no-track từ origin/develop. Thay đổi đang ở working tree, chưa commit/push hoặc merge trong lượt này. Không thực hiện embedding, retrieval, LLM, entities, migrations hay hạ tầng của các thành viên khác.

## Kết quả đã chạy

Dùng job local crawl-adfa0d316047 ngày 25/10: 247 raw hiện có, chọn đúng 200 page ID theo report completed. Dữ liệu local đã thay đổi so với handover S1 nên không dùng số liệu/các file report cũ làm nguồn nghiệm thu. Không có s1-acceptance.json trong dữ liệu hiện tại; raw ID/revision/hash và manifest của cohort được kiểm chứng lại khi chạy.

Đã khảo sát cấu trúc trên 200 trang: 321 infobox, 579 table, 251 wikitable, 67 navbox, 140 toc, 187 gallery, 50 blockquote.quote. Các số này tính trên HTML raw trước lọc.

Thử 20 trang đa dạng trước, xem các đoạn trước/sau và giữ source literals cho mỗi trang. Sau kiểm tra đã sửa: bảng loadout/stats, thông báo quote/stub, sự lặp quote hiển thị, marker edit/chú thích trong block terminal, và chống lặp nhật ký cùng node. Đã chạy đủ 200 trang và lặp lại một lần để kiểm tính ổn định.

Kết quả cuối: 1.353 section còn nội dung sau lọc cấu trúc; 783 giữ, 564 review, 6 excluded theo scope. Loại 3.076 node với vị trí DOM/lý do, gồm 1.880 marker chú thích/edit, 37 bảng số, 28 bảng loadout và 31 quote hiển thị trùng. Không dedup mọi câu lặp xuyên section/trang.

CSV: lore_clean.csv 783 dòng; review.csv 3.841 dòng; images.csv 2.637 occurrence. Review gồm section, node và ghi chú cấu trúc nên không đồng nhất với số section review. Mọi CSV có UTF-8 BOM, quote ô đúng chuẩn; kiểm lại bằng csv.DictReader và so nội dung round-trip.

Kiểm thử thực tế: 124 passed, 1 integration test deselected; ruff check và format --check đạt. Gồm 25 regression cấu trúc/pipeline và 20 regression source literals từ dữ liệu local. Trên CI thiếu raw thì 20 case local sẽ skip; không coi đó là đã chạy trên corpus thật ở CI. Kiểm thử còn xác nhận không tạo HTTP client ở pipeline, revision sai phải dừng, output không được ghi đè, ảnh khác trang/section bị từ chối.

Hai lần chạy đủ 200 trang tạo SHA-256 giống nhau cho cả ba CSV. Raw/manifest giữ nguyên hash trong từng lượt; ảnh chỉ được đọc và kiểm hash, không ghi lại. Không gọi mạng/AI trong clean. Network Git fetch chỉ dùng khi chuẩn bị nhánh.

## File và luồng xử lý

- core/text/normalize.py: NFC và khoảng trắng, giữ nội dung nhiều dòng.
- core/text/html_clean.py: hàm thuần, heading hierarchy, phân biệt bảng, infobox fields, UI, quote duplicate có bằng chứng; trả section và removal audit.
- ingest/filter/rules.py: pure filter_document, evidence và quyết định scope.
- ingest/transform/document.py: xác định cohort, lưu filter artifact trước; đọc lại để transform metadata, nối manifest, xuất/đọc lại CSV và report.
- ingest/transform/metadata.py: source_type/lang conservative, không suy diễn bằng model.
- ingest/config/sources.toml: thêm nhóm clean với danh sách cấu hình.
- ingest/__main__.py và README: lệnh clean và hướng dẫn.
- tests/unit/test_cleaning_s2.py, tests/fixtures/cleaning_s2_expectations.json: test và kỳ vọng ngắn, không chứa raw HTML crawl.

Mã hiện dùng một lệnh clean điều phối các bước nhưng artifact filter và processed tách riêng. Không expose các lệnh index/update chưa triển khai. Không sửa core/types.py, bảng entities, DB, app online hoặc cấu hình TV3.

## Artifact và lệnh chạy

Kết quả chính: backend/data/clean_runs/s2-csv-200-v1/. Bản lặp: s2-csv-200-v1-repeat/. Mẫu 20: s2-csv-20-v1/. Các lượt thử trước có thể chưa có report vì validation đã bắt lỗi; không sử dụng CSV ở thư mục thiếu report.

Trong mỗi output có filtered/wikigg/<id>.json, decisions.jsonl rồi processed/wikigg/<id>.json, ba CSV và report.json. Report ghi rule/config hash, cohort, thống kê, checksum và giới hạn. Mẫu 20 có before-after-20.json; bản bàn giao bổ sung qa-20.json và before-after-20.md.

```powershell
# Từ backend; chọn output mới hoặc rỗng
.venv/Scripts/python.exe -m ingest clean --limit 20 --crawl-report data/reports/crawl-adfa0d316047.json --output-dir data/clean_runs/new-20
.venv/Scripts/python.exe -m ingest clean --limit 200 --crawl-report data/reports/crawl-adfa0d316047.json --output-dir data/clean_runs/new-200
.venv/Scripts/python.exe -m pytest tests/unit/test_cleaning_s2.py -q
```

Không chỉ định crawl-report thì chọn lượt 200 trang mới nhất theo mtime, có validation danh sách ID và revision. --limit 20 là cohort cố định với các title có trong fixture; bộ mẫu khác thiếu title sẽ báo lỗi để người dùng chọn lại expectation, không tự giả vờ cùng cohort. Giới hạn clean là 1..200 trong thử nghiệm này. Chưa triển khai chế độ toàn corpus hoặc ghi PG ở tác vụ này.

## Quyết định và hạn chế

Base chỉ được gán khi có evidence từ địa danh base trong lead/infobox/section; đây là heuristic, không phải chứng minh ngữ nghĩa của mọi phát biểu. Marker DLC/cut heading bị excluded; nội dung trộn được review. Danh sách tên explicit DLC trong scope_excluded của report bổ sung tín hiệu review, không dùng danh sách S1 như ground truth base. Các tên/marker chưa có vẫn có thể bị bỏ sót. Không dùng dữ liệu này để tuyên bố FR-ING-03 hoàn thành toàn bộ hoặc sẵn sàng index production.

Không đủ evidence thì giữ review; 217 section clean có source_type unknown và 123 section lang unknown. Bảng Dialogue có cấu trúc rõ được gắn in_game_text; Description/quote chưa đủ nguồn giữ unknown. Giữ bảng điều kiện vật phẩm, loại bảng stats/loadout theo nhãn; bảng khác chưa rõ được giữ ở processed/review. Bảy section có dấu hiệu speculation được gắn nhãn riêng.

Image IDs trong lore là JSON array, chỉ nối scope base theo cùng source_id/revision/section khớp duy nhất. Infobox giữ ngữ cảnh riêng; gallery hoặc section trùng tên/mơ hồ không được gắn hàng loạt. Metadata ảnh có dấu hiệu DLC được review. Không sinh caption, không thay quyền ảnh unknown. local_path/source_snapshot là absolute path trên máy này; chuyển dữ liệu sang máy khác cần relocate prefix và mang theo raw/media.

Các artifact CSV/processed/report nằm trong backend/data nên bị Git ignore; bản giao cho người dùng được sao chép ra outputs của chat, không đẩy dữ liệu crawl vào repo. Chưa thay đổi trạng thái SRS/planning hoặc đánh dấu task Done trước review. Tài liệu này và mã cần review qua PR về develop theo quy ước; chưa tự merge.


## Cập nhật trạng thái Git

Sau lượt triển khai/nghiên cứu này, mã đã được rebase và push lên nhánh riêng theo yêu cầu người dùng. Xem [bàn giao Git](2026-10-28_s2-tv2_day-ma-nguon-github.md) để biết commit, kiểm tra sau rebase và trạng thái review.
