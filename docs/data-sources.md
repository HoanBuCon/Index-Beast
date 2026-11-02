# Nguồn dữ liệu Sprint 1 của TV2

Ngày khảo sát: 23–24/10/2026. Phạm vi theo ADR-004 là lore Elden Ring base game. Đây là khảo sát/prototype, chưa phải corpus đã làm sạch hoặc index. API dữ liệu công khai và thu thập ảnh đã được TV2 duyệt; không dùng API AI.

## Nguồn và kết quả kiểm chứng

| Nguồn | Mục đích | Endpoint | Kết quả |
|---|---|---|---|
| wiki.gg | Nguồn raw chính | https://eldenring.wiki.gg/api.php | categorymembers, parse và imageinfo hoạt động |
| fanapis | Khảo sát dữ liệu có cấu trúc cho TV3 | https://eldenring.fanapis.com/api/ | 7 resource, thử page=0/1 với limit=2 thành công |
| Fandom | Đối chiếu 10 trang | https://eldenring.fandom.com/wiki/ | robots.txt trả HTTP 403; không tải bài khi chưa xác minh policy |

Bằng chứng local: `backend/data/reports/source-probe.json`, `source-survey.json`, `categories.json`. Thời điểm trong JSON dùng UTC. Không coi số liệu crawl là trạng thái vĩnh viễn của nguồn.

## Category và cách đếm

Đếm thành viên namespace 0; số trực tiếp không bao gồm trang trong subcategory. Cột hợp nhóm lấy tối đa một cấp subcategory theo cấu hình và khử trùng page ID. Các nhóm có giao nhau, không cộng cột để suy ra số bài duy nhất. Đây là số ứng viên trước rà soát scope; category có thể lẫn nội dung DLC.

| Category | Trang trực tiếp | Subcategory trực tiếp | Trang duy nhất trong nhóm, sâu 1 |
|---|---:|---:|---:|
| NPC | 117 | 3 | 129 |
| Bosses | 115 | 3 | 141 |
| Locations | 347 | 17 | 357 |
| Lore | 65 | 9 | 313 |
| Items | 489 | 19 | 1757 |
| Characters | 180 | 10 | 396 |

Tổng hợp sau khử trùng: **2602 ứng viên**. Danh sách category và page ID đầy đủ ở `categories.json`.

## Giao thức wiki.gg

- Discovery: `action=query&list=categorymembers&cmtitle=Category:NPC&cmprop=ids|title|type&cmlimit=500`.
- Phân trang: truyền lại toàn bộ object `continue`, không chỉ cmcontinue; chống vòng lặp token.
- Đọc revision trước crawl: `action=query&prop=info|categories&pageids=...`; xử lý cả continuation của categories.
- Nội dung: `action=parse&page=<title>&prop=text|sections|categories|images|revid`; HTML và revid cùng response. Thử `oldid` trong môi trường này gặp HTTP 403; không dùng kết quả đó để khẳng định API lịch sử luôn bị tắt. Prototype dùng parse theo title và lưu revision thực tế được trả về.
- Ảnh: `action=query&prop=imageinfo&titles=File:...&iiprop=url|size|mime|sha1|timestamp|extmetadata`.
- Luôn `format=json&formatversion=2&maxlag=5`. Không chạy LLM để tạo hoặc bổ sung dữ liệu nguồn.

## Khảo sát fanapis

Mỗi resource thử `limit=2&page=0` và `limit=2&page=1`. Total là số provider trả về, chưa kiểm kê hết. Chỉ giữ response khảo sát; crawler ghi bảng entities thuộc TV3 Sprint 2.

| Resource | Total trả về | Có description trong mẫu | Hai trang trả ID khác nhau |
|---|---:|---|---|
| bosses | 106 | Có | Có |
| npcs | 55 | Không thấy | Có |
| locations | 177 | Có | Có |
| items | 462 | Có | Có |
| weapons | 307 | Có | Có |
| talismans | 87 | Có | Có |
| spirits | 64 | Có | Có |

## So sánh Fandom và wiki.gg

Đã thử đủ 10 cặp URL dưới đây. Cả 10 phía wiki.gg đọc được; phía Fandom bị dừng ở bước kiểm tra robots (HTTP 403). Vì vậy **chưa có so sánh nội dung hợp lệ**, không kết luận hai nguồn giống/khác hay tính phần trăm tương đồng. Thẻ này còn mục cần review hoặc thực hiện lại khi nguồn cho phép truy cập.

- Ranni the Witch: wiki.gg đọc được; Fandom chưa truy cập được.
- Melina: wiki.gg đọc được; Fandom chưa truy cập được.
- Millicent: wiki.gg đọc được; Fandom chưa truy cập được.
- Fia: wiki.gg đọc được; Fandom chưa truy cập được.
- Sorcerer Rogier: wiki.gg đọc được; Fandom chưa truy cập được.
- Nepheli Loux: wiki.gg đọc được; Fandom chưa truy cập được.
- Miriel, Pastor of Vows: wiki.gg đọc được; Fandom chưa truy cập được.
- Starscourge Radahn: wiki.gg đọc được; Fandom chưa truy cập được.
- Golden Order: wiki.gg đọc được; Fandom chưa truy cập được.
- Fingerslayer Blade: wiki.gg đọc được; Fandom chưa truy cập được.

## Dump

Special:Statistics không có liên kết dump trong lần kiểm tra. Special:Version liệt kê extension DumpsOnDemand. Đã đọc Special:RequestDump: cả bản current revisions và full history đều báo “This dump has not yet been created”. Không có URL tải dump ở thời điểm kiểm tra; không gửi yêu cầu tạo dump mới.

## Giấy phép và attribution

Footer wiki.gg trong mẫu HTML ghi CC BY-SA 4.0; lưu URL trang và revision để giữ provenance. Giấy phép phần mềm MediaWiki/extension không phải giấy phép nội dung wiki. Ảnh có quyền riêng: ghi extmetadata tác giả, license và trang File nếu API trả; nếu thiếu đặt `unknown_review_required`, tuyệt đối không tự gán CC BY-SA 4.0 cho ảnh. Trường Artist có thể chứa HTML, consumer phải escape/sanitize trước hiển thị.

fanapis cung cấp dữ liệu không cần key theo tài liệu chính thức; chưa xác minh giấy phép tái phân phối toàn bộ nội dung/ảnh, không suy từ giấy phép code. Nguồn Fandom chưa đọc được nên không xác nhận giấy phép từ snapshot lần này. Phần attribution trên UI thuộc TV4; TV2 bàn giao metadata.

## Chính sách client

Một CLI tuần tự, tối thiểu 1 giây giữa mọi request, gồm API/robots/ảnh, không chỉ request bài viết. Retry tối đa 2 lần cho lỗi mạng/429/5xx; backoff 2/4 giây, tôn trọng Retry-After số giây hoặc HTTP-date. Nếu phải chờ quá 60 giây thì dừng request và ghi lỗi. robots crawl-delay lớn hơn được ưu tiên. Không vượt challenge hoặc robots. Chỉ cho HTTPS, host allowlist và kiểm tra lại redirect. Email đọc từ `.env`, không ghi vào report.

Response bài/API tối đa 8 MB; ảnh tối đa 20 MB và 40 triệu pixel. PNG/JPEG/WebP/GIF được kiểm tra bằng Pillow. Nếu header MIME khác định dạng ảnh đã decode hợp lệ, ghi declared_mime/mime_mismatch và lưu đuôi theo bytes thực tế; định dạng không được phép hoặc bytes lỗi bị từ chối. Không chạy đồng thời nhiều CLI dùng chung data directory.

## Tài liệu nguồn

- https://www.mediawiki.org/wiki/API:Categorymembers
- https://www.mediawiki.org/wiki/API:Parsing_wikitext
- https://www.mediawiki.org/wiki/API:Imageinfo
- https://www.mediawiki.org/wiki/Extension:DumpsOnDemand
- https://docs.eldenring.fanapis.com/docs/
- https://github.com/deliton/eldenring-api
