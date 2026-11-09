# Rà soát cách chia section và chunk trên toàn bộ 4.164 trang

| | |
|---|---|
| Ngày | 02/11/2026 |
| Người thực hiện | TV1 (Hoanbucon); mã cleaner/chunker thuộc TV2 |
| Nhánh | `docs/s3-tv1-ra-soat-section-chunk` (từ `develop` tại `d9421c7`) |
| Dữ liệu | Raw cuối (`raw/wikigg/snapshots`, chọn theo report crawl `s2-full-20261028`), clean `s2-full-v2`, chunk `s2-full-v1` |
| Cách làm | Script tạm, chỉ đọc: parse lại HTML raw bằng BeautifulSoup, đối chiếu với clean, review và chunk. Không sửa dữ liệu, không gọi mạng, không ghi DB. Chạy khoảng 1 phút |

## Câu hỏi

Cleaner chia section theo heading HTML (`h1`–`h6`) của MediaWiki. Nếu trang dùng "tiêu đề giả" (dòng chữ đậm, `;Tiêu đề`) hoặc cấu trúc lạ, chunk có thể gộp sai chủ đề hoặc mất phần nội dung. Trước đây chỉ kiểm bằng mắt trên 20 trang (ADR-003).

## Kết quả

| Kiểm tra | Kết quả | Đánh giá |
|---|---|---|
| Tiêu đề giả: `<p>` chỉ có chữ đậm ngắn, hoặc `<dt>` | 76 dòng trên **53/4.164 trang** (65 chữ đậm, 11 `<dt>`) | Hầu hết không phải tiêu đề chủ đề: `???` (skill chưa có tên), `View Gallery`, `Items related to or referencing …` (dòng dẫn danh sách liên kết) |
| Chunk bị trộn: tiêu đề giả nằm giữa thân chunk | **3 chunk trên 3 trang** (The Guilty, Carian Study Hall, Great Coffin) | Đều là danh sách kẻ địch hoặc vật phẩm theo vùng; nhãn "Enemies", "Standard", "Liurnia of the Lakes" nằm cùng chunk với mục liền trước. Ảnh hưởng nhỏ |
| Heading thật không có dấu vết trong clean hoặc review | Ban đầu đếm 9.678; sau khi trừ section bị loại có chủ đích (Acquisition, Effects, Gallery, References…) còn 253 heading trên 49 trang. Xem tận nơi (vd. trang *Fists*): đó là heading `h3` **nằm trong ô `<th>` của bảng** thu gọn, không phải heading section. Nội dung bảng vẫn được giữ dưới section cha với lý do `unclassified_structure` | **Không có heading section nào bị mất** |
| Section được giữ dài hơn 6.000 ký tự | 40 section: 9/10 dài nhất là **Dialogue**, còn lại là Notes của *Skill: Barbaric Roar* (20.633 ký tự) | Chunker xử lý đúng: Dialogue tách theo từng lượt thoại (vd. *Ranni the Witch* 94 chunk, lớn nhất 213 token); Notes của Barbaric Roar thành 21 chunk, mỗi chunk ≤ 450 token |
| Trang nội dung dài nhưng chỉ có Introduction/Infobox (không heading) | **0 trang** | Không có trang "phẳng" bị dồn chung một section |

## Kết luận

- **Cách chia theo heading đúng với cấu trúc thực tế của 4.164 trang.** Không có heading section bị mất, không có trang dài thiếu heading. Tiêu đề giả hiếm (53 trang) và gần như không phải tiêu đề chủ đề; chỉ 3 chunk bị trộn nhẹ.
- Cộng với các kiểm tra sẵn có (không mất chữ, ≤ 450 token, trang nào cũng có chunk, ID ổn định), **chưa thấy lý do phải sửa cách chia section trong `html_clean.py`**.
- Chưa phủ: ý nghĩa nội dung từng chunk (vẫn cần đánh giá truy xuất bằng golden set); các vấn đề không thuộc cấu trúc đã biết từ trước (trang mẫu Talisman Template, nhãn ngôn ngữ 🇧🇷/🇹🇼, dữ liệu gameplay chưa vào corpus).

## Gợi ý nhỏ cho TV2 (không bắt buộc)

- Các dòng `???` và `Items related to or referencing …` là nhãn trang trí hoặc dẫn danh sách. Có thể đưa vào luật loại `interface_or_navigation` khi làm việc #5 (sửa lỗi nội dung).
- Bảng thu gọn chứa heading `h3` trong `<th>` (danh sách Ash of War theo affinity) đang vào review `unclassified_structure`. Đây là danh sách điều hướng, có thể loại hẳn để `review.csv` gọn hơn.

## Tái lập

Script là bản tạm của TV1, không đưa vào repo. Muốn chạy lại thì: với mỗi trang trong report crawl, tìm `<p>` chỉ chứa `<b>`/`<strong>` (≤ 80 ký tự, không kết thúc bằng dấu chấm) và `<dt>`; đối chiếu các dòng đó với thân chunk trong `chunks.jsonl`; so heading `h2`–`h6` (ngoài navbox, toc, infobox) với tên section xuất hiện trong `content_clean_all.csv` và `review.csv`.
