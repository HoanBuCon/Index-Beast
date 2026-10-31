# Khảo sát toàn bộ `backend/data` và đề xuất xử lý dữ liệu (bản 2, sau phản biện)

| | |
|---|---|
| Ngày | 31/10/2026 (Asia/Saigon) |
| Người lập | TV1 (Hoanbucon), Tech Lead |
| Nhánh | `docs/s2-tv1-khao-sat-du-lieu` (từ `origin/develop` tại `f089538`) |
| Trạng thái | **Chưa duyệt.** Bản 1 bị trả lại vì chưa đủ sâu. Bản này kiểm chứng lại từng luận điểm bằng số liệu, bỏ các đề xuất không có bằng chứng |
| Căn cứ | Bản sao `backend/data` (~9,2 GB); handover TV2/TV3 S2; [audit độ phủ TV2](../testing/2026-10-31_tv2-corpus-readiness.md); [audit năng lực TV3](../testing/2026-10-29_elden-ring-assistant-capabilities.md); mã `backend/core/text/html_clean.py` |
| Cách làm | Chỉ đọc: liệt kê, hash, đếm, parse lại HTML raw bằng BeautifulSoup. Không crawl, không LLM, không embedding/index, không ghi DB/Qdrant, không sửa dữ liệu |

## 1. Bản cuối của từng tầng

| Tầng | Bản cuối | Quy mô | Kiểm chứng |
|---|---|---|---|
| Raw | `raw/wikigg/snapshots/<pageid>/<revid>-<hash>.json`, đúng file mà `crawl_runs/s2-full-20261028/report.json` trỏ tới | 4.164 trang, 158 MB | 4.157 id trong report có snapshot; 7 snapshot còn lại đúng là 7 trang chỉ lỗi ảnh. 6 trang có thêm một revision cũ (bỏ qua) |
| Ảnh | `media/blobs/` + manifest `crawl_runs/s2-full-20261028/media/<pageid>.json` | 10.371 blob, 7,96 GB | Khớp audit TV2 |
| Clean | `clean_runs/s2-full-v2/` | 22.419 record giữ/review + 55.560 dòng ghi lý do loại (`review.csv`) | SHA-256 ba CSV khớp `delivery/s2-full/manifest.json` |
| Chunk | `chunk_runs/s2-full-v1/chunks.jsonl` | 23.765 chunk (18.368 EN được index) | SHA-256 năm file khớp `report.json` |

Không phải bản cuối:
- 247 file `raw/wikigg/*.json` và `media/manifests/` (200 file) là mẫu Sprint 1.
- `clean_runs/s2-full-v1` là lượt thử trước.
- 29 lượt `*-20`, `*-200`, `trial`, `repeat` là thử nghiệm.
- `local-setup/` (592 MB) là bộ cài Docker, không phải dữ liệu.

## 2. Phản biện bản đề xuất 1

| Luận điểm bản 1 | Kiểm chứng lại | Kết luận |
|---|---|---|
| "Chunk vụn, mất ngữ cảnh: `Slots Used: 1` lặp 190 lần" | Thân chunk trùng, nhưng `embedding_text` luôn có `passage: <tiêu đề trang>\n<section>`. Trong 18.368 chunk EN chỉ **7** `embedding_text` trùng hoàn toàn | **Sai.** Chunk nhỏ vẫn mang tên trang, không phải mảnh vô danh |
| "Gộp chunk sẽ giảm 18k xuống 8–10k" | Mô phỏng gộp các unit liên tiếp cùng section tới 300 token (không gộp dialogue/quote): 18.368 → **17.281** (−6%). Phần lớn chunk nhỏ đứng một mình trong section | **Sai ước tính.** Lợi ích nhỏ; không làm như một dự án riêng |
| "Chunk vụn là vấn đề ảnh hưởng lớn nhất tới truy xuất" | Chưa từng đo Recall@K/MRR trên corpus đầy đủ (TV3 ghi rõ ở báo cáo độ trễ và audit năng lực). Bộ 10/10 là smoke test lore | **Không có bằng chứng.** Phải đo trước khi tối ưu |
| "Cần bản phát hành `data/releases/` + biến `DATA_RELEASE`" | Thứ thật sự hỏng: `load_full --validate-only` trên máy TV1 **lỗi `FileNotFoundError`** vì `documents.jsonl` ghi `source_snapshot` tuyệt đối `D:\Index-Beast\...`. Index Qdrant không đọc trường này nên không bị ảnh hưởng | **Phức tạp hóa.** Chỉ cần sửa đường dẫn tương đối |
| "Index theo release + alias Qdrant" | `RAG_COLLECTION` và `--collection` đã có: index sang collection mới rồi đổi `.env` | **Thừa.** Dùng cơ chế sẵn có |
| "Tính `release_scope` vì 60% unknown" | Phạm vi đã gồm cả base và SotE; chưa có yêu cầu lọc theo bản phát hành | **Chưa cần.** Hoãn |
| "Viết parser mới, dựng thẻ thông số" | `review.csv` **đã có sẵn text** của phần gameplay bị loại, kèm lý do. Ví dụ Moonveil: `Type: Katana / Skill: Transient Moonlight / Sell Price: 500` (`gameplay_infobox_field`), `Weight / 6.5`, `FP Cost / - (15 20)` (`infobox_numeric_or_production_field`), `Acquisition: Dropped by the Magma Wyrm in Gael Tunnel` (`gameplay_section`) | **Phần lớn thừa.** Đổi chính sách giữ/loại là đủ cho các mục này |
| "Dữ liệu gameplay thiếu do chính sách lore" | Đúng một phần, nhưng **bỏ sót nguyên nhân lớn hơn** (mục 3) | Cần sửa |

## 3. Phát hiện chính: bảng chỉ số trong infobox bị mất không để lại dấu vết

`html_clean.infobox()` (`backend/core/text/html_clean.py`, quanh dòng 149) chỉ duyệt các phần tử `.pi-data`. Các bảng Attack Power, Guarded Damage Negation, Attributes (Required/Scaling), Damage Negation, Resistance, Poise lại nằm trong `<table>` lồng trong `.pi-group`. Hàm không thêm chúng vào clean, cũng không gọi `audit()`, nên chúng **không có trong `content_clean_all.csv` lẫn `review.csv`**.

Đo trên 4.164 trang raw (parse lại infobox, so với mọi dòng clean/review của trang):

| Bảng trong infobox raw | Số trang có trong raw | Có trong clean | Chỉ có trong review | **Mất không dấu vết** |
|---|---:|---:|---:|---:|
| Attack Power | 572 | 234 | 51 | **287** |
| Damage Negation | 1.410 | 94 | 72 | **1.244** |
| Attribute (Required/Scaling) | 800 | 88 | 63 | **649** |
| Resistance | 770 | 2 | 0 | **768** |
| Poise | 754 | 2 | 1 | **751** |
| Trang mất toàn bộ bảng chỉ số infobox | | | | **1.477 / 1.824** |

Số "có trong clean" phần lớn đến từ chữ xuất hiện trong văn xuôi (Notes…), không phải bảng. Kiểm trực tiếp Moonveil: không dòng nào ở clean hay review chứa `Physical`, `73` hay `Intelligence`.

Ví dụ trang bị mất: Flame, Cleanse Me; Lionel's Greaves; Carian Knight's Shield; Chain Coif; Battlemage Robe…

Hệ quả:
- Đây là nguyên nhân chính khiến chatbot không trả lời được chỉ số vũ khí và giáp, lớn hơn chính sách lore.
- Audit TV2 báo "0 lỗi integrity" vì chỉ kiểm những gì đã vào ledger; phần bị bỏ qua thì không có trong ledger.
- Nguyên tắc "mọi phần bị loại đều có lý do" của pipeline đang bị vi phạm. Đây là lỗi mã, không phải dữ liệu nguồn kém.

## 4. Đề xuất (bản 2): ít việc hơn, sửa đúng chỗ

| # | Việc | Phụ trách | Vì sao / bằng chứng | Chi phí |
|---|---|---|---|---|
| 1 | **Sửa `html_clean.infobox()`:** xử lý bảng trong `.pi-group` thành dòng `Nhóm / Cột: giá trị` (vd. `Attack Power / Physical: 73`, `Attributes / Intelligence: Required 23, Scaling C`). Mọi phần không dùng phải gọi `audit()`. Thêm test: Moonveil có đủ Attack Power và Attributes; không còn node infobox nào thoát khỏi cả clean lẫn ledger | TV2 | Mục 3: 1.477 trang | Nhỏ: một hàm + test |
| 2 | **Nhận lại các mục gameplay đã có sẵn trong `review.csv`:** đổi quyết định của `gameplay_infobox_field`, `infobox_numeric_or_production_field` (bỏ trường sản xuất như Voice actor), `gameplay_section`, giữ nguyên nhãn `content_type` từ lý do để lọc khi cần. **Chỉ làm sau khi team chốt CHANGE-REQ gameplay** | TV2 | Text đã có, không cần parser mới | Nhỏ: sửa `lore_policy.py`, chạy lại clean/chunk |
| 3 | **Giữ infobox của một trang trong một chunk** (≤450 token) thay vì mỗi trường một chunk | TV2 | Sau #1 mỗi trang vũ khí/giáp có thêm khoảng 10–20 dòng chỉ số. Để mỗi dòng một chunk sẽ thêm hàng chục nghìn chunk 1 dòng, và top-5 không chứa đủ một bộ chỉ số | Nhỏ: luật nhóm unit trong chunker |
| 4 | **Ghi `source_snapshot` dạng tương đối** so với `data/` (hoặc cho `load_full` tìm theo `pageid/revid-hash`) | TV2 | `load_full` hỏng trên máy khác (đã chạy thử) | Rất nhỏ |
| 5 | **Sửa các lỗi nội dung TV2 đã liệt kê:** trang mẫu Talisman Template, tab 🇧🇷 gắn `en`, tab 🇹🇼 `unknown`, markup `[[...]]` | TV2 | Audit TV2 | Nhỏ |
| 6 | **Đo trước, đo sau.** Trước khi đổi corpus, chạy Recall@5/MRR của corpus hiện tại trên golden set, bổ sung khoảng 15 câu hỏi chỉ số (Moonveil, Uchigatana, một bộ giáp, một phép). Index bản sửa sang collection mới, so sánh rồi mới đổi `RAG_COLLECTION` | TV3 | Hiện chưa có số đo chất lượng nào trên corpus đầy đủ | Index ~17 phút mỗi lần; cần người dùng duyệt chạy embedding |
| 7 | Xóa `local-setup/` và các lượt thử sau khi team đồng ý | TV2 | ~1 GB không phải dữ liệu | Rất nhỏ |

Thứ tự: #4 và #5 bất kỳ lúc nào; #6 (đo baseline) trước #1–#3; #1 → #3 → chạy clean/chunk vào thư mục mới → #6 (đo lại).

**Không làm** (đã bỏ so với bản 1): hệ thống release dữ liệu, alias Qdrant, gộp chunk văn xuôi, suy `release_scope`, parser hay bảng dữ liệu cấu trúc riêng.

**Về bảng nâng cấp (+0…+25, affinity):** đây là phần khó (bảng gộp ô, nguồn chỉ hiện một số hàng). Không đưa vào đợt này. Chatbot trả lời giá trị +0 từ infobox và dẫn link trang cho bảng nâng cấp.

## 5. Việc cần team quyết định

1. Chốt phạm vi gameplay/build bằng CHANGE-REQ. #1, #3, #4, #5 cần làm dù quyết định thế nào; #2 phụ thuộc quyết định này.
2. Đồng ý chạy embedding để đo baseline và index bản sửa (#6).
3. Đồng ý xóa `local-setup/` và các lượt thử (#7).

## 6. Giới hạn của khảo sát này

- Việc nhận diện bảng chỉ số dựa trên chữ khóa trong infobox (Attack Power, Damage Negation, Attribute, Resistance, Poise). Có thể sót loại bảng khác, ví dụ chỉ số của phép hoặc boss.
- "Có trong clean" được tính khi chữ khóa xuất hiện ở bất kỳ dòng nào của trang, nên số trang thực sự còn bảng có thể còn thấp hơn.
- Chưa đo chất lượng truy xuất. Mọi nhận định về ảnh hưởng tới câu trả lời vẫn là suy luận cho tới khi có số đo ở #6.
- Script khảo sát là script tạm của TV1, không đưa vào repo. Muốn tái lập, parse `.portable-infobox` của các snapshot trong mục 1 và so với `content_clean_all.csv` và `review.csv` theo `source_id`.
