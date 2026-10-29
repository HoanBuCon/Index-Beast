# TV2 — clean toàn bộ 4164 raw base + SotE

Người dùng duyệt phạm vi Sprint 2 base game + Shadow of the Erdtree. Nhánh
feature/s2-tv2-clean-chuan-hoa; không merge develop, không làm embedding/entities/retrieval.

## Mã và contract

- core/text/html_clean.py: capture_context tùy chọn, giữ tab/literal-description/citation;
  gỡ nhãn source/version trang trí có audit locator. Mặc định legacy không đổi.
- core/text/lore_policy.py: pure block decisions, nhóm theo ngôn ngữ/variant/source_type;
  dialogue/literal item description được giữ, bảng chưa hiểu/cut/cross-game/combat hỗn hợp
  ở review; không loại DLC. Không dùng min_chars để loại quote ngắn.
- ingest/transform/full.py: đọc cohort report/checkpoint, text/media riêng, ghi filter trước
  transform, core.ids document ID, CSV BOM, checksum/round-trip, processed theo page.
- game_scope=elden_ring (base+SotE được duyệt); release_scope candidate/unknown chỉ là
  heuristic. Unknown language giữ nguyên, tab FR/DE/... không bị gán giả thành en.
- source_type suy từ cấu trúc quote/dialogue/wiki và wording speculation; vẫn là heuristic.
  Speaker không suy từ page title. License ảnh chưa rõ vẫn unknown_review_required.

## Chạy thực tế

Từ backend:

```powershell
.venv/Scripts/python.exe -m ingest.transform.full --run-dir data/crawl_runs/s2-full-20261028 --output-dir data/clean_runs/<ten-moi>
```

`--limit 20` chọn bộ 20 trang đa dạng cố định. Đã chạy 20-final, 200-first-ID và regression
đúng 200 ID từ report S1 crawl-adfa0d316047 (projection manifest dùng revision full hiện tại).
Manifest regression local: data/validation_manifests/s2-regression-200.

**Bản bàn giao clean hiện tại: data/clean_runs/s2-full-v2**. v1 là lượt thử trước khi chuyển
Boss Fight sang review; không dùng v1 làm final. v2: 4164 trang, 22419 records, 20235 eligible,
65593 image occurrences. 7 trang media failed vẫn có text. Review.csv 55560 dòng gồm
node bị bỏ và record review, không phải số section review. content_clean_all.csv gồm cả
keep/review, dùng cột decision/chunk_eligible để phân biệt. Block counts: 43581 keep,
2432 review, 23361 excluded. validation.json ghi metadata và kiểm tra độc lập.

159 unit tests passed, 11 integration deselected (bỏ file test chunk đang chuẩn bị ở
nhánh khác). Ruff check/format file clean đạt. Đọc lại CSV, hash text/ID và mọi raw/manifest
trong fingerprint không đổi. Mô tả Elden Remembrance, Scadutree Fragment, Great Épée và
dialogue Ranni được xem trực tiếp; EN/JP/FR/DE được tách đúng theo tab nguồn.

## Tài liệu và giới hạn

Đã cập nhật ngoại lệ ADR-004, AGENTS và planning/sprint_plan.json chỉ cho quyết định TV2 S2;
đã sinh lại docs/03_SPRINT_PLAN.md bằng hàm generator. File Word export chưa được sinh lại.
Đã cài dependency python-docx==1.2.0 từ planning/requirements.txt để dùng generator Markdown.
Không tự cập nhật Trello hay phần retrieval TV3. TV3 phải review game_scope/passage prefix.

Đây là clean theo luật, chưa chứng nhận mọi câu đúng ngữ nghĩa. Combat/table/cut/cross-game
chưa rõ được review; không index ảnh/không OCR. Chưa bắt đầu nhánh hệ thống mở rộng thứ tư.
