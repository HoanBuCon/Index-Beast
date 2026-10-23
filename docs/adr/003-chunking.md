# ADR 003 Chiến lược chunk lore và liên kết ảnh

Ngày: 24/10/2026. Trạng thái: **Đề xuất, chờ review TV3 và Mentor**. Chủ sở hữu: TV2. Yêu cầu: FR-ING-04; metadata tham chiếu FR-ING-05. Phần thu thập ảnh đã được TV2 duyệt, phần image embedding/retrieval thuộc TV3.

## Quyết định đề xuất

Chia theo heading, hướng tới 350–450 token cho chunk đủ nội dung, giới hạn cứng **450 token tính toàn bộ chuỗi đưa vào embedding**, overlap **50 token phần nội dung** trong cùng section. Đếm bằng tokenizer của `intfloat/multilingual-e5-small`, không dùng quy đổi ký tự/token hoặc tokenizer LLM khác. Đây là phương án khởi đầu phù hợp cấu hình hiện có, chưa được chứng minh tối ưu retrieval.

Giữ tiêu đề trang và đường dẫn heading trong từng chunk. Chuỗi dự kiến:

```text
passage: <page title>
<section cha > section con>
<nội dung>
```

Tính cả prefix và special tokens khi kiểm tra giới hạn. Đo lại chuỗi đã serialize cuối cùng, tránh cộng số token từng phần rồi coi là tuyệt đối chính xác. Model card e5-small dùng giới hạn 512 token; chọn 450 để có khoảng trống, không đặt body=450 rồi cộng title/section vào sau. Với heading quá dài phải chia/chuẩn hóa prefix theo quy tắc được review, không âm thầm truncate nội dung.

## Cơ sở dữ liệu mẫu

Mẫu 20 trang được chọn trải đều theo thứ tự discovery cân bằng category trong tập 200 trang của job `crawl-2301a25ddbc1`. Các trang qua heuristic nhận diện scope ở lead/infobox; chưa hoàn thành thẩm định mọi section. Dữ liệu gồm NPC, boss, địa điểm, nhóm sinh vật, item/painting và tutorial. Không xem mẫu này là phân bố thống kê đại diện toàn wiki.

Script `backend/ingest/debug/heading_analysis.py` chỉ đọc local, bỏ menu/script/mục lục và infobox khi đo text; giữ bảng vì bảng hội thoại có thể hữu ích. Đây chưa phải bộ cleaner S2. References, bảng stats và nội dung trùng có thể còn trong phép đo. File `heading-analysis.json` lưu revision từng trang, đường dẫn section, số token và SHA-256 tokenizer.

| Trang mẫu | Số section có nội dung |
|---|---:|
| Abandoned Merchant | 6 |
| Ancient Hero of Zamor | 7 |
| "Prophecy" Painting | 4 |
| Bloody Finger Nerijus | 5 |
| Ainsel River Well | 4 |
| Altus Plateau | 6 |
| Beasts | 9 |
| Artist's Shack (Limgrave) | 5 |
| Auriza Hero's Grave | 7 |
| About Flask of Wondrous Physick | 4 |
| Boc's Mother | 7 |
| Demi-Human Queen Maggie | 5 |
| Chair-Crypt | 2 |
| Gurranq, Beast Clergyman | 9 |
| Dragonlord Placidusax | 8 |
| Elemer of the Briar | 13 |
| About Sorceries and Incantations | 3 |
| About Stance-Breaking | 4 |
| About Summoning Pools | 4 |
| Cave of Knowledge | 5 |

## Thí nghiệm kích thước

Đo mô phỏng cửa sổ token trong từng section, overlap 50, cộng prefix và 2 special tokens. Chưa chạy retrieval, chưa tối ưu ranh giới câu. Số chunk ngắn dưới đây tính body <300 token, không đồng nghĩa nội dung rác.

| Giới hạn tổng token | Số cửa sổ | Body ngắn dưới 300 | Prefix không đủ ngân sách |
|---|---:|---:|---:|
| 350 | 141 | 112 | 0 |
| 400 | 131 | 102 | 0 |
| 450 | 127 | 101 | 0 |
| 500 | 125 | 100 | 0 |

Từ 450 lên 500 chỉ giảm ít cửa sổ trên mẫu này; 450 giữ khoảng trống tốt hơn cho tiêu đề và ngữ cảnh. Nhiều section vốn ngắn, nên không ép mọi chunk đạt 300 token hoặc bổ sung nội dung bằng AI. Việc chọn 450/50 vẫn cần TV3 xác nhận bằng baseline ở S1 và đánh giá retrieval sau này.

## Quy tắc ranh giới cho S2

1. Duy trì hierarchy heading cha/con. Không ghép nội dung khác trang, khác scope hoặc khác source_type để đủ token.
2. Ưu tiên ranh giới đoạn và câu. Hội thoại giữ trigger/người nói cùng lời thoại; bảng giữ header với hàng liên quan. Đo lại token sau khi thêm context.
3. Section dài được chia thành nhiều chunk. Overlap tối đa 50 token, lấy từ phần cuối chunk trước trong cùng section; không lặp title vào body overlap.
4. Section ngắn có thể ghép với section kề trong cùng heading cha khi cùng scope và source_type; vẫn lưu dấu vết subheading. Nếu không phù hợp, giữ chunk ngắn có nghĩa.
5. Gallery, navbox, bảng chỉ số, backlink references và nội dung DLC phải xử lý trước chunking. Không xóa toàn bộ bảng vì có thể làm mất hội thoại hoặc mô tả. Không xem tất cả references là rác; lưu bằng chứng riêng khi cần.
6. Không suy ra tất cả nội dung là base chỉ vì trang qua heuristic. Chỉ gán `game_scope=base` sau rà soát section theo ADR-004. Các ảnh của section DLC cũng bị loại khỏi tập index base.

## Quan hệ giữa chunk và ảnh

Ảnh được lưu độc lập trong `data/media/blobs/<prefix>/<sha256>.<ext>`. Mỗi occurrence trong manifest giữ page ID, revision, section, caption, alt và URL nguồn. Một blob có thể có nhiều occurrence hợp lệ ở nhiều trang; không xóa liên kết khi dedup file.

Ở S2, chunk có thể tham chiếu `image_ids`/occurrence IDs khi ảnh thuộc cùng section hoặc có liên kết caption rõ ràng. Ảnh infobox giữ ngữ cảnh `Infobox`; không tự gắn vào mọi chunk của trang. Không chép caption thành phát biểu lore mới hoặc tự đoán danh tính từ pixel. Nếu cần OCR, mô tả ảnh bằng model, embedding ảnh hay multi-vector thì TV3 quyết định và triển khai trong thẻ riêng.

Ảnh thiếu giấy phép giữ nhãn `unknown_review_required`; việc tải được ảnh không đồng nghĩa được phép tái phân phối. Các trường Artist/description có HTML cần escape/sanitize khi hiển thị. File raw và ảnh không đưa vào Git.

## Bàn giao và phần việc kế tiếp

TV2 bàn giao raw, manifest, báo cáo 20 trang và đề xuất này. S1 chưa xây production cleaner/chunker hoặc ghi DB; các phần đó thuộc S2. TV3 review tokenizer/prefix/ngân sách và dùng dữ liệu cho baseline; TV1 giữ schema/migrations; UI hiển thị nguồn thuộc TV4.

## Tài liệu tham chiếu

- `docs/01_TECHSTACK.md`, `docs/02_SRS.md`, `docs/04_ARCHITECTURE.md`
- `docs/adr/004-base-game-scope.md`
- https://huggingface.co/intfloat/multilingual-e5-small
