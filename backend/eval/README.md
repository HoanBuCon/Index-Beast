# Golden set v0 — IndexBeast

Yêu cầu: **FR-EVAL-01**, thẻ S1 “Golden set v0 (30 câu)”, phụ trách **TV3 — MinhMuc**. Bộ câu hỏi dành cho **lore Elden Ring base game**, theo [ADR-004](../../docs/adr/004-base-game-scope.md). Có tiết lộ cốt truyện.

File chuẩn là [`golden_set.jsonl`](golden_set.jsonl) trong thư mục `backend/eval/` có sẵn của repo. Đường dẫn `eval/golden_set.jsonl` trong checklist được hiểu từ thư mục `backend/`. Không duy trì một bản sao ở gốc repo.

## Thành phần

| Category | Ý nghĩa | ID | Việt | Anh |
|---|---|---|---:|---:|
| `character` | Nhân vật, danh tính, vai trò | IB-GS-001–006 | 4 | 2 |
| `event` | Sự kiện và hậu quả | IB-GS-007–012 | 4 | 2 |
| `location` | Địa điểm và bối cảnh | IB-GS-013–018 | 4 | 2 |
| `multi_hop` | Kết hợp các quan hệ hoặc chuỗi nguyên nhân, từ ít nhất hai nguồn | IB-GS-019–024 | 4 | 2 |
| `out_of_scope` | Từ chối yêu cầu ngoài phạm vi lore | IB-GS-025–030 | 4 | 2 |
| **Tổng** | **30 câu; 66,7% tiếng Việt** | | **20** | **10** |

Độ khó: **12 easy, 12 medium, 6 hard**. Đây là nhãn thiết kế ban đầu, chưa suy ra từ kết quả chạy hệ thống. Câu `multi_hop` cần đủ các ý liên kết trong đáp án; có nhiều URL không có nghĩa mọi pipeline buộc phải lấy nhiều chunk nếu một chunk đã chứa đủ bằng chứng.

## Schema và cách đóng góp

UTF-8 không BOM; mỗi dòng là một JSON object độc lập với đúng bảy trường:

| Trường | Kiểu | Quy tắc |
|---|---|---|
| `id` | string | `IB-GS-001`…; duy nhất và ổn định qua các lần đánh giá |
| `question` | string | Câu hỏi rõ, tự đủ ngữ cảnh, không nhúng đáp án |
| `lang` | string | `vi` hoặc `en` |
| `expected_answer` | string | Các ý tối thiểu cần đúng, cùng ngôn ngữ câu hỏi; không buộc khớp từng chữ |
| `source_urls` | array[string] | URL bài nguồn hỗ trợ đáp án; không dùng URL ảnh hoặc trang kết quả tìm kiếm |
| `category` | string | Một trong năm giá trị ở bảng trên |
| `difficulty` | string | `easy`: tra cứu trực tiếp; `medium`: phân biệt hoặc giải thích; `hard`: tổng hợp quan hệ/nhân quả |

Giữ nguyên tên riêng tiếng Anh. Không đưa fan theory thành sự thật; tránh câu hỏi mơ hồ hoặc cần thông tin ngoài nguồn. Khi sửa đáp án/URL phải có review diff. Nếu thay đổi hẳn ý nghĩa câu hỏi, cấp ID mới và ghi thay đổi để không so điểm các phiên bản như cùng một bộ test.

## Nguồn và mức kiểm chứng

Bản nháp được trợ lý soạn ngày **25/10/2026**, tham khảo kế hoạch và dữ liệu local, đối chiếu với nội dung wiki.gg được công cụ tìm kiếm lập chỉ mục. Các lần mở trực tiếp trang mẫu trả **403**; chưa kiểm chứng toàn văn, HTTP status của toàn bộ URL, revision cố định hoặc đối chiếu trực tiếp trong game. **Cần nhóm review trước khi đóng băng v0.**

`source_urls` trong JSONL là nguồn tham chiếu cho từng câu. Một số URL là redirect đã xuất hiện trong kết quả tìm kiếm, ví dụ [Raya Lucaria](https://eldenring.wiki.gg/wiki/Raya_Lucaria), [Erdtree Sanctuary → Leyndell](https://eldenring.wiki.gg/wiki/Erdtree_Sanctuary), [Rya](https://eldenring.wiki.gg/wiki/Rya). TV2 cần chuẩn hóa chúng về URL canonical mà crawler lưu trước khi tính retrieval bằng URL; không so chuỗi redirect với canonical rồi kết luận retrieval sai.

Ưu tiên bằng chứng từ lời thoại và mô tả vật phẩm được wiki ghi lại:

- IB-GS-003: [Remembrance of the Black Blade](https://eldenring.wiki.gg/wiki/Remembrance_of_the_Black_Blade), mô tả nhiệm vụ canh giữ Destined Death.
- IB-GS-004: [Remembrance of the Full Moon Queen](https://eldenring.wiki.gg/wiki/Remembrance_of_the_Full_Moon_Queen), vai trò lịch sử của Rennala.
- IB-GS-005, 012: [Remembrance of Hoarah Loux](https://eldenring.wiki.gg/wiki/Remembrance_of_Hoarah_Loux), Godfrey mất grace và rời Lands Between.
- IB-GS-010, 011, 022: [Cursemark of Death](https://eldenring.wiki.gg/wiki/Cursemark_of_Death), phân biệt cái chết về thể xác và linh hồn.
- IB-GS-020: [Remembrance of the Rot Goddess](https://eldenring.wiki.gg/wiki/Remembrance_of_the_Rot_Goddess), hai affliction từ khi sinh ra.
- IB-GS-021: [Remembrance of the Lichdragon](https://eldenring.wiki.gg/wiki/Remembrance_of_the_Lichdragon), Fortissax chống Death bên trong Godwyn và bị tha hóa.
- IB-GS-022: [Mending Rune of the Death-Prince](https://eldenring.wiki.gg/wiki/Mending_Rune_of_the_Death-Prince), hai nửa hallowbrand và nguyên lý sống trong Death.
- IB-GS-023: [Starscourge Conflict](https://eldenring.wiki.gg/wiki/Starscourge_Conflict) và [Nokron, Eternal City](https://eldenring.wiki.gg/wiki/Nokron%2C_Eternal_City), chuỗi sao bị giữ → Radahn chết → hố thiên thạch mở đường.

Chỉ dùng các ý thuộc base game trong bài nguồn; không tự index toàn bài chỉ vì URL có trong golden set. Nguồn wiki có thể được cập nhật và trộn nội dung ngoài phạm vi. Khi corpus có sẵn, lưu revision/hash nguồn trong manifest riêng; schema JSONL vẫn giữ đúng bảy trường.

## Phân công review đề xuất

Đây là phân công **đề xuất**, chưa phải bằng chứng các thành viên đã đóng góp. Mỗi người cần tự kiểm tra, sửa hoặc bổ sung ít nhất năm câu và xác nhận qua PR/review. Chưa đánh dấu checklist “Mỗi người đóng góp ≥ 5 câu” hoàn thành.

| Thành viên | Câu nhận review/hoàn thiện | Số câu | Trạng thái |
|---|---|---:|---|
| TV1 — Hoanbucon | IB-GS-001–008 | 8 | Chờ xác nhận |
| TV2 — UncleThing | IB-GS-009–016 | 8 | Chờ xác nhận; hỗ trợ review nguồn toàn bộ |
| TV3 — MinhMuc | IB-GS-017–023 | 7 | Chờ xác nhận |
| TV4 — QuyVuiVe | IB-GS-024–030 | 7 | Chờ xác nhận |

TV2 và TV3 review chéo đáp án/nguồn. Mentor review trước khi merge theo [quy ước Git](../../docs/quy_uoc.md).

## Cách dùng khi đánh giá

1. Lưu phiên bản golden set, Git SHA, cấu hình retrieval/LLM và phiên bản corpus cùng mỗi lượt eval. Không index `question` hoặc `expected_answer` vào corpus RAG.
2. Chỉ gửi `question` cho hệ thống; đáp án chuẩn dành cho bước chấm. Trả lời đúng ngôn ngữ, ngắn gọn, đủ ý và dẫn nguồn hỗ trợ từng khẳng định.
3. Với 24 câu trong phạm vi, chấm correctness theo ý nghĩa: **2** đúng đủ ý, **1** đúng một phần hoặc thiếu mắt xích, **0** sai/không trả lời. Chấm faithfulness riêng bằng câu trả lời và **ngữ cảnh thực sự được truy xuất**, không suy từ đáp án chuẩn.
4. `source_urls` liệt kê tập nguồn tham chiếu cho các ý cần trả lời; không mặc định mọi URL đều bắt buộc cho một câu tra cứu đơn. Báo cáo riêng Hit@k (có ít nhất một nguồn phù hợp), recall theo nguồn và độ phủ bằng chứng của câu đa bước. Phải canonicalize URL/redirect theo cùng quy tắc ở corpus và bộ eval.
5. Sáu câu `out_of_scope` có `source_urls: []` vì kiểm tra chính sách phạm vi, không có trang lore làm đáp án. Không tính chúng vào Recall/MRR hoặc coi thiếu URL là lỗi retrieval. Báo cáo riêng tỉ lệ từ chối đúng: nêu phạm vi, không thực hiện yêu cầu ngoài phạm vi, không bịa trích dẫn. Không yêu cầu lặp lại đúng câu từ chối mẫu.
6. Bộ 30 câu này dành cho toàn dự án; **không phải bộ đo phù hợp cho index chỉ có 240 dòng armor**. Trước khi chạy cần rà soát corpus có đủ bằng chứng cho 24 câu lore. Thiếu nguồn phải báo cáo coverage, không đổi đáp án cho khớp đầu ra mô hình.

Đây là bộ phát triển ban đầu; một số câu liên quan cùng nhân vật/sự kiện. Không dùng lại nguyên bộ này làm test độc lập sau khi đã tinh chỉnh prompt bằng nó. Chưa chạy retrieval, notebook hay LLM với bộ câu hỏi này; chưa có điểm chất lượng.
