# Bàn giao TV2 — audit độ phủ raw/clean/chunk

Ngày 31/10/2026, TV2 (UncleThing). Nhánh `docs/s2-tv2-audit-do-phu-du-lieu`,
từ origin/develop bcefa26. Phạm vi: kiểm dữ liệu hiện có và chỉ ra thiếu sót trước
khi bổ sung thông số; không sửa production cleaner/chunker, DB, index hoặc phần TV khác.

## Git và PR

- Commit audit ban đầu: `230c335`; đã fetch origin và rebase origin/develop, không
  có thay đổi nền mới hoặc conflict trong lượt đồng bộ.
- Đã push nhánh riêng, upstream là origin/docs/s2-tv2-audit-do-phu-du-lieu.
- [PR #51](https://github.com/HoanBuCon/Index-Beast/pull/51), base develop, trạng thái
  open khi kiểm tra. GitHub xác nhận requested reviewer HoanBuCon; chưa tuyên bố
  được approve, CI đạt hoặc merge. Commit bổ sung này ghi trạng thái bàn giao vào cùng PR.

## File và kết quả

- `backend/ingest/debug/corpus_readiness.py`: audit chỉ đọc corpus bàn giao, kiểm local
  fingerprints/CSV/raw/processed/chunk/media, tokenizer local, thống kê field và bảng,
  metadata thiếu và ứng viên ngôn ngữ/template. Ghi artifact vào thư mục mới.
- [Báo cáo chi tiết](../testing/2026-10-31_tv2-corpus-readiness.md): phương pháp,
  số liệu, ví dụ, giới hạn, lệnh chạy lại và ưu tiên khắc phục.
- Output thực tế: backend/data/research_runs/s2-readiness-20261031 gồm report.json,
  pages.jsonl, metadata-check.json. Không đưa data hoặc tokenizer vào Git.
- Đã đọc đủ 4164 raw/processed và 23765 chunk; kiểm 23659 units; hash 10371 blob ảnh.
  Zero lỗi integrity/token/source slice đã phát hiện, không đồng nghĩa sạch ngữ nghĩa.
- Thiếu gameplay do policy lore; 5 chunk template lọt, 17 chunk Portuguese gắn EN;
  metadata patch/level/affinity/spoiler thiếu, 7 media lỗi. Xem report để không nhầm
  số record/node với số trang hoặc số vật phẩm.

## Kiểm chứng và giới hạn

Full audit hoàn tất, exit 0. Metadata diagnostics chạy bổ sung bằng cùng hàm được CLI
gọi khi chạy lại. Ruff check/format và git diff --check đạt. Không mở kết nối DB/server,
không API/model/embedding/OCR, không thay raw/ảnh/CSV/chunks hiện có. So saved fingerprints
và kiểm size/mtime cuối lượt không phát hiện input thay đổi; file nguyên gốc vẫn ở run cũ.

Không xác minh độ phủ live wiki hoặc mọi phát biểu/game value. Nhận diện stat bảng
và so substring infobox chỉ là chẩn đoán, không dùng làm auto-approve. Placeholder/template
và Portuguese đã xem trực tiếp; các trường hợp khác giữ nhãn candidate/review.

Chưa clean/chunk lại hoặc sửa lỗi. Không tự merge, thay collection, cập nhật Trello
hay tuyên bố retrieval đạt. Các hành động đề xuất cần triển khai trong task tiếp theo.
