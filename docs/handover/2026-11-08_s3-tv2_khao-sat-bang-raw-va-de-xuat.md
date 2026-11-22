# TV2 — Khảo sát bảng raw và đề xuất chờ duyệt, 08/11/2026

Người dùng yêu cầu khảo sát toàn bộ dữ liệu thô, tìm bảng như Crystal Sword và
đưa kế hoạch lọc để duyệt, chưa chạy chuyển đổi. Phạm vi lượt này chỉ đọc local,
ghi script khảo sát/báo cáo/đề xuất. Không sửa cleaner/chunker hiện có, không
crawl, AI API, embedding, index, DB hoặc xóa dữ liệu. Nhánh vẫn là
fix/s3-tv2-chat-luong-du-lieu; giữ các thay đổi trước, không commit/push/merge.

## File mới và kết quả

- `backend/ingest/debug/table_survey.py`: census HTML read-only với lxml đã có
  trong môi trường, không thay parser production BeautifulSoup.
- [Đề xuất chi tiết chờ duyệt](../proposals/2026-11-08_tv2-structured-tables-plan.md).
- Artifact local: `backend/data/research_runs/s3-table-survey-20261108-v2/`, gồm
  tables.jsonl/report/input-fingerprints, equipment-coverage và policy-comparison.

4.164/4.164 snapshot đã đọc, content_hash/fingerprint hợp lệ, lỗi 0. Tổng 8.506
bảng; 6.760 bảng article ngoài UI trên 2.843 trang; 4.044 có rowspan/colspan.
375 bảng nâng cấp trên 159 trang; 2.391 bảng infobox, 185 dialogue, 180 catalog,
259 crafting, 127 shop, 197 drop-rate, 45 compatibility; phần khác xem report.
1.527 bảng chưa đủ căn cứ phân loại. Nhóm dựa heuristic, chưa được chứng nhận
ngữ nghĩa. Flag giao nhau, số trang giữa nhóm giao nhau, không cộng các số trang.

375 bảng nâng cấp đối chiếu cùng 159 source_id trong review hiện tại: 305 review
unclassified_structure và 70 excluded numeric_stats_table. Crystal Sword có ô
gộp khiến 68/166 bị hiểu sai cột nếu flatten. Longsword có 13 bảng nâng cấp.
486 trang ứng viên theo type infobox, 159 có bảng upgrade nhận diện được và 327
chưa có trong snapshot. Không khẳng định mọi trường hợp thiếu bảng là crawler lỗi.

Lượt khảo sát sơ bộ v1 giữ ở thư mục không có hậu tố v2; v2 sửa việc đếm dấu
backlink ↑ thành /Lv, loại nhiễu heading infobox và phân loại sâu hơn. Số growth
rate đúng theo rule /Lv/per level là 260 bảng/44 trang; không dùng 712 của v1.
Chỉ dùng v2 làm báo cáo cuối.

## Đề xuất và trạng thái phê duyệt

Đề xuất P0 khoảng 2–3 ngày: fixture/schema khoảng 20 bảng, grid parser ô gộp,
parser upgrade/infobox, nghiệm thu trên nhóm 375 bảng trong bản thử riêng. Giữ
grade/coefficient, damage/guard, level/affinity, nguồn và metadata. Dữ liệu không
rõ đưa review, không xóa cả bảng hoặc đoán loại damage từ màu. P1 các bảng
gameplay/dialogue khác, P2 unclassified và thiếu raw cần duyệt riêng.

Chưa thực hiện parser chuyển đổi hay bất kỳ P0/P1/P2 nào. Đánh giá vector/LLM
và chỉnh runtime TV3 không nằm trong lượt khảo sát này. Không tự thay nguồn đang
dùng hoặc đưa các bảng review trở lại chunk.

## Cách kiểm và tái chạy khảo sát

Từ backend, chọn output mới:

```powershell
.venv/Scripts/python.exe -m ingest.debug.table_survey --raw data/raw/wikigg/snapshots --output data/research_runs/<new-survey> --delivery data/delivery/final/manifest.json
```

Script đọc toàn bộ snapshot, lưu XPath/table_index, section, sample cell với span,
header, flags và fingerprint. Coverage theo type/policy comparison là phân tích
đọc local bổ sung; rule/type pattern và danh sách trang lưu trong JSON.
Ruff check/format đạt; kiểm 17 checksum artifact bản cuối vẫn khớp, raw fingerprint
trước/sau không đổi, delivery manifest không đổi. Không chạy test pipeline hoặc
clean/chunk vì không sửa các bước đó trong lượt này.
