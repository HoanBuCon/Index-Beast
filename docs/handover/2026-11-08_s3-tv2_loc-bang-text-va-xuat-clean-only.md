# TV2 — Lọc bảng text nhập nhằng, 08/11/2026

Người dùng đưa ví dụ `Icon | Name | Effect | Location ... Spelldrake Talisman`
và yêu cầu kiểm tra/lọc những dữ liệu tương tự. Nhánh làm việc vẫn là
`fix/s3-tv2-chat-luong-du-lieu`; không sửa retrieval/LLM/DB hoặc tự commit/merge.

## Phát hiện và cách xử lý

Ví dụ thuộc source_id 52, Spelldrake Talismans > Overview, DOM table. Bản cũ
đã đánh review/unclassified_structure, chunk_eligible=False, nhưng vẫn xuất
vào content_clean_all.csv cùng các dòng keep. Vì vậy file này dễ bị hiểu nhầm
là tập sạch dùng embedding. Ví dụ không có trong chunks.jsonl cũ.

Ngoài ra tìm thấy bảng quest item (Roderika/Gowry/Rogier/Varré) bị nhận nhầm
là dialogue do ô dữ liệu có từ “dialogue”. Một số bảng hội thoại nhiều cột
EN/JP/location hoặc location/dialogue bị nối bằng dấu | mà chưa tách vai trò.

- Sửa html_clean ở chế độ gameplay: nhận dialogue theo section/header thật,
  không theo chữ dialogue bất kỳ trong ô dữ liệu. Bảng nhiều cột chưa tách vai
  trò mang note unresolved_multicolumn_dialogue, policy chuyển review.
- Không xóa theo dấu | nói chung. Thông số infobox có nhãn, prose và hội thoại
  một cột được giữ. Bảng chưa xử lý đủ giữ nguyên text, source/DOM/reason trong
  review để có thể viết parser và khôi phục, không mất dữ liệu gốc.
- Thêm content_clean.csv chỉ gồm decision=keep và chunk_eligible=True.
  content_clean_all.csv vẫn là catalog đối soát, không phải corpus để embedding.
- Version mới: s3-full-clean-1.2, s3-full-chunk-1.3. Validator nhận version mới.

## Artifact và kiểm chứng

Điểm vào vẫn `D:/Index-Beast/backend/data/delivery/final/README.md`.
Primary CSV là `clean/content_clean.csv`; chunk là `chunk/chunks.csv` hoặc jsonl.
Đích vật lý mới là clean_runs/s3-table-filter-final-20261108 và
chunk_runs/s3-table-filter-final-20261108. Các junction raw/media/source không đổi.

Report chi tiết: research_runs/s3-rag-readiness-20261108/table-filter/report.json;
removed-chunks.jsonl ghi lại chunk đã chuyển review, nội dung và lý do. Báo cáo
structure riêng lưu tại table-filter/table-filter-structure.json. Không lấy điểm
vector trước đây làm điểm của artifact mới; lượt này chỉ kiểm fact presence,
cấu trúc, CSV, nguồn và token, không chạy encoder/LLM hoặc index.

Đã chạy 80 unit test đạt, 20 skip vì bộ mẫu 200 trang cũ đã xóa theo yêu cầu.
24 test chọn cho clean/chunk/table/stats đều đạt. Ruff check/format đạt.
Test mới bao gồm bảng quest nhắc dialogue, bảng dialogue nhiều cột, giữ lời thoại
một cột, giữ bảng stats và dấu | trong văn bản. Full run 4.164 trang và kiểm
CSV bằng DictReader là kiểm trực tiếp dữ liệu hiện có, không phụ thuộc mẫu đã xóa.

CLI từ backend, dùng output mới:

```powershell
.venv/Scripts/python.exe -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --gameplay --output-dir data/clean_runs/<new>
.venv/Scripts/python.exe -m ingest.chunk.full --input-dir data/clean_runs/<new> --tokenizer <local-tokenizer.json> --output-dir data/chunk_runs/<new>
.venv/Scripts/python.exe -m ingest.chunk.load_full data/chunk_runs/<new> --validate-only
```

`ingest.debug.table_filter_audit` kiểm primary CSV không có review/header Icon,
đối chiếu chunk bị chuyển review theo source/DOM, và kiểm 15 fact trang bị từ
protocol raw. Cần --previous-chunks trước khi xóa artifact trước; sau khi đối
chiếu, removed-chunks.jsonl giữ phần bằng chứng nhỏ để khỏi giữ cả corpus cũ.

Raw và ảnh không bị sửa. Điểm vào final đã cập nhật bằng New-Item Junction -Force.
Xóa hai thư mục clean/chunk được thay thế bị automatic review chặn với thông báo
"blocked by policy", không có lý do cụ thể hơn; không tìm cách vượt chặn. Hai thư
mục s3-quality-language-20261108 và s3-quality-final-20261108 vẫn tồn tại nhưng
không được final sử dụng. Trạng thái lưu trong audit/table-filter/replacement-cleanup.json.
Các report baseline trong audit là lịch sử, không
phải chỉ số của bản mới. Bảng hội thoại nhiều cột cần parser chuyên biệt ở lượt
sau; chuyển review có thể giảm độ phủ truy xuất một số NPC trong thời gian này.

Kết quả cuối: 27.478 dòng clean-only; 31.034 chunk; 30.940/30.940 unit được phủ.
7 bảng chuyển review tương ứng 21 chunk cũ (4 inventory, 17 dialogue nhiều cột).
1.551 chunk thông số có nhãn vẫn giữ, 15/15 fact trang bị còn trong nguồn chunk.
Source 52 với header Icon được giữ trong review, không có trong clean-only/chunk.
Structural errors 0, max token 450/overlap 50. Load validate-only đạt 4.164 docs /
31.034 chunks, index dry-run nhận 25.607 EN và invalid 0. Kiểm lại 17 checksum
artifact sau khi đổi junction đều khớp. Không gọi encoder/LLM, không ghi database.
