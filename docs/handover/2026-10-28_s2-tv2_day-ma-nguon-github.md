# Bàn giao TV2 đẩy mã nguồn làm sạch và chunking lên GitHub

Ngày: 28/10/2026. Người phụ trách: TV2 (UncleThing). Theo yêu cầu đẩy mã nguồn lên GitHub; phạm vi gồm các thay đổi TV2 về làm sạch, xuất CSV, nghiên cứu và chunking đã bàn giao trước đó.

## Nhánh và các commit

Nhánh: feature/s2-tv2-lam-sach-va-xuat-csv, PR đích develop theo docs/quy_uoc.md. Đã fetch và rebase lên origin/develop tại 5ec72a4, gồm cập nhật API/PostgreSQL của TV1. Conflict duy nhất ở docs/handover/README.md đã giải quyết bằng giữ đầy đủ mục của cả TV1 và TV2, không sửa mã phần TV1.

Ba commit mã/tài liệu đã được push và xác minh remote tại 90651f95099ecf414b1c6038f0f2c6022112530a:

- ba0eebe feat(ingest): add offline cleaning exports and context-aware chunking
- bbc30ec feat(ingest): add local chunk readiness analysis
- 90651f9 docs(ingest): document TV2 cleaning and chunking handover

Tài liệu này và cập nhật liên kết handover là commit bổ sung trên cùng nhánh. Không merge develop/main và không force-push. Upstream được đặt đúng origin/feature/s2-tv2-lam-sach-va-xuat-csv.

## Kiểm tra đã chạy sau rebase

- pytest -q tại backend: 147 passed, 11 deselected. Các test integration cần service bị loại theo cấu hình mặc định; không coi là đã chạy integration thật.
- ruff check . đạt; ruff format --check . đạt, 128 file được kiểm tra.
- git diff --check đạt; kiểm tra JSON fixture và liên kết local trong các tài liệu liên quan đạt.
- Xác minh diff so origin/develop chỉ gồm mã/test/tài liệu TV2; không có .env hoặc backend/data. Raw, ảnh, CSV/JSONL xuất, tokenizer/model không đưa lên Git.
- Không chạy lại crawl, notebook, model, API AI, embedding hoặc index để thực hiện tác vụ Git này.

Các số liệu 200 trang/CSV/chunk đã được ghi trong handover triển khai tương ứng; tác vụ Git chỉ kiểm thử mã sau tích hợp với develop. Không thay đổi số liệu lịch sử thành kết quả chạy lại giả.

## GitHub và bước review

Mã nguồn: https://github.com/HoanBuCon/Index-Beast/tree/feature/s2-tv2-lam-sach-va-xuat-csv

Mở PR về develop: https://github.com/HoanBuCon/Index-Beast/compare/develop...feature/s2-tv2-lam-sach-va-xuat-csv?expand=1

Hiện chưa tạo hoặc merge PR trong tác vụ này. CI trên GitHub và Mentor approval chưa được xác nhận; không đánh dấu CI xanh hoặc task đã tích hợp. Cần mở PR, review theo CODEOWNERS/Mentor và chờ các kiểm tra bắt buộc trước merge. Nếu tác giả là Mentor, reviewer phải là người khác được nhóm chấp thuận.

## Hạn chế giữ nguyên

Scope base vẫn là heuristic; review/excluded còn phải thẩm định. Source_updated_at chưa có nguồn xác thực và khác updated_at sinh artifact. Speaker còn null khi nguồn thiếu trường rõ. Retrieval quality, DB integration và image embedding thuộc phần phối hợp các thành viên sau review; không tự nhận đã hoàn thành.
