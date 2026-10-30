# TV2 — đồng bộ các nhánh công việc lên GitHub

Theo yêu cầu người dùng đẩy mọi nhánh trong lúc crawler đang chạy.
Đồng bộ sáu nhánh feature TV2 bằng ref đích rõ ràng; không dùng push --all,
không force, không merge/rebase, không push main/develop.

- feature/s1-tv2-crawl-media: lịch sử S1 cũ, trước đây upstream nhầm origin/develop;
  đẩy lên nhánh cùng tên và đặt lại upstream. Không coi đây là bản thay thế mã S2.
- feature/s1-tv2-crawler-va-du-lieu-anh: đưa lại ref lên remote nếu đã bị xóa sau merge.
- feature/s2-tv2-lam-sach-va-xuat-csv: đưa lại ref lên remote nếu đã bị xóa sau merge.
- feature/s2-tv2-crawl-toan-bo-wikigg: nhánh crawl hiện hành và bàn giao này.
- feature/s2-tv2-clean-chuan-hoa: nhánh thẻ clean.
- feature/s2-tv2-chunking-metadata: nhánh thẻ chunk/PG và integration tests.

Không đẩy raw/media/artifact/.env, không đổi thư mục đang checkout hoặc tiến trình
crawler. Nhánh hệ thống mở rộng thứ tư theo kế hoạch vẫn chưa bắt đầu.
Local main có lịch sử riêng; không tự đưa lịch sử đó vào nhánh ổn định trên remote.

Xác minh bằng git ls-remote và so SHA HEAD của từng nhánh local/remote sau push.
Không chạy lại test mã nguồn cho tác vụ chỉ đồng bộ ref và bổ sung bàn giao.
