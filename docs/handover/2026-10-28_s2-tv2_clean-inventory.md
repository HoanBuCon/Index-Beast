# TV2 — clean theo inventory

Nhánh feature/s2-tv2-clean-chuan-hoa từ origin/develop 02c4abf.
Kế thừa cleaner và regression 20 trang trong PR #31 đã merge.

Thêm `clean --all --crawl-report <report.json> --output-dir <new-dir>` để đọc số trang
bất kỳ từ report completed có ID không trùng. Mặc định giữ cơ chế mẫu 200 trang cũ.
Media manifest theo từng entry trong inventory nếu có; fallback manifest mẫu S1.
Không đổi raw/ảnh; filter và transform tiếp tục tách artifact và giữ quyết định review.

Kiểm chứng: 149 passed, 11 deselected. Ruff check/format đạt trên file thay đổi.
Đã chạy clean 20 trang: 138 section, 86 base heuristic, 52 review.
Đã chạy clean 200 trang: 1353 section, 783 base heuristic, 564 review, 6 excluded.
Output local: backend/data/clean_runs/s2-card-clean-20 và s2-card-clean-200.
Ba CSV được CLI đọc lại kiểm tra round-trip và liên kết ảnh.

Chưa có inventory full đã nghiệm thu; chưa tuyên bố hoàn tất cleaning toàn corpus.
Scope/source_type còn heuristic, review chưa được giải quyết toàn bộ. Không embedding,
LLM, entities, Qdrant hoặc thay đổi schema TV1.
