# Khảo sát toàn bộ `backend/data` và đề xuất xử lý dữ liệu

| | |
|---|---|
| Ngày | 31/10/2026 (Asia/Saigon) |
| Người lập | TV1 (Hoanbucon), Tech Lead |
| Nhánh | `docs/s2-tv1-khao-sat-du-lieu` (từ `origin/develop` tại `f089538`, sau PR #51) |
| Căn cứ | Bản sao `backend/data` TV2 bàn giao (~9,2 GB); handover TV2/TV3 S2; [audit độ phủ của TV2](../testing/2026-10-31_tv2-corpus-readiness.md) |
| Cách làm | Chỉ đọc: liệt kê, đếm, hash, thống kê bằng script Python. Không crawl, không gọi LLM, không embedding/index, không ghi DB/Qdrant, không sửa file dữ liệu |

## 1. Kết luận nhanh

| Tầng | Bản cuối | Quy mô | Trạng thái |
|---|---|---|---|
| **Raw** | `raw/wikigg/snapshots/<pageid>/<revid>-<hash>.json`, chọn theo `crawl_runs/s2-full-20261028/report.json` + `checkpoint.json` | 4.164 trang (158 MB). 4.170 file vì 6 trang có thêm 1 revision cũ | Đủ: 4.157 trang thành công + 7 trang chỉ lỗi ảnh (text có đủ) |
| **Ảnh** | `media/blobs/` (theo SHA-256) + manifest `crawl_runs/s2-full-20261028/media/<pageid>.json` | 10.371 blob, 7,96 GB | Khớp số TV2 audit; giấy phép chưa rõ toàn bộ |
| **Clean** | `clean_runs/s2-full-v2/` | 4.164 trang, 22.419 record (20.235 eligible, 2.184 review), 207 MB | SHA-256 của 3 CSV khớp `delivery/s2-full/manifest.json` |
| **Chunk** | `chunk_runs/s2-full-v1/` (`chunks.jsonl` là nguồn cho index) | 23.765 chunk, 129 MB | SHA-256 của 5 file chính khớp `report.json`; đầu vào chính là `clean_runs/s2-full-v2` |
| Điểm vào | `delivery/s2-full/README.md`, `manifest.json` | — | Chỉ trỏ tới hai thư mục trên |

**Lưu ý dễ nhầm:**
- `raw/wikigg/*.json` (247 file nằm phẳng) và `media/manifests/` (200 file) là **mẫu Sprint 1**, không thuộc bộ cuối.
- `clean_runs/s2-full-v1` là lượt thử trước khi chuyển "Boss Fight" sang review. **Không dùng.**

## 2. Kiểm kê toàn bộ thư mục

| Thư mục | Dung lượng | Nội dung | Vai trò |
|---|---:|---|---|
| `media/` | 7,5 GB | `blobs/` 10.371 ảnh; `manifests/` 200 (S1); `url-index.json` | Cuối (blobs); manifests là S1 |
| `local-setup/` | 592 MB | Bộ cài Docker Desktop, script và log sửa WSL/Docker | **Rác, không phải dữ liệu** |
| `clean_runs/` | 552 MB | 23 lượt chạy (20/200 trang, regression, full v1, full v2) | Cuối: `s2-full-v2`; 22 lượt còn lại (346 MB) là thử nghiệm |
| `chunk_runs/` | 176 MB | 8 lượt chạy | Cuối: `s2-full-v1`; 7 lượt còn lại (47 MB) là thử nghiệm |
| `raw/` | 171 MB | `snapshots/` (cuối) + 247 file S1 | Xem mục 1 |
| `crawl_runs/` | 132 MB | `s2-full-20261028`: inventory 4.179, checkpoint, report, history 2 lượt, 4.164 media manifest, log | Bằng chứng + chỉ mục chọn raw cuối |
| `research_runs/` | 23 MB | Khảo sát phạm vi 29/10 (v1, v2) | Nghiên cứu |
| `studies/` | 4 MB | Nghiên cứu chunk 200 trang | Nghiên cứu |
| `reports/` | 428 KB | `categories.json`, report crawl S1 | Lịch sử |
| `validation_manifests/` | 112 KB | Danh sách 200 trang regression | Dùng cho test hồi quy |

Thư mục `research_runs/s2-readiness-20261031` (output audit TV2 ngày 31/10) **không có trong bản sao này**.

## 3. Hồ sơ dữ liệu (đo lại trên bản cuối)

**Chunk `s2-full-v1`:**

| Chỉ số | Giá trị |
|---|---|
| Ngôn ngữ | en 18.368 · ja 3.447 · unknown 1.801 · 10 ngôn ngữ khác 149 |
| Loại nguồn | wiki_prose 15.393 · in_game_text 8.329 · speculation 43 |
| Loại đơn vị | prose 16.077 · infobox 4.155 · dialogue 3.288 · quote 245 |
| `release_scope` | unknown 14.165 (60%) · base_candidate 6.185 · mixed_or_sote_candidate 2.011 · sote_candidate 1.404 |
| Token (cả bộ) | min 13 · **median 55** · mean 78 · max 450 |
| Chunk EN (đã index) | 18.368, **median 52 token, 8.720 chunk (47%) dưới 50 token** |
| Chunk infobox EN | 2.582, median 27 token (mỗi trường infobox thành một chunk riêng) |
| Thân chunk trùng y hệt | 2.068 bản lặp; ví dụ `Slots Used: 1` ×190, `Region: Liurnia of the Lakes` ×49, `Affinity: Keen` ×35 |
| Chunk mỗi trang | median 5, lớn nhất 162 |
| Metadata trống ở mọi chunk | `review_status`, `content_type`, `speaker`, `spoiler_level`, `patch_version` |

**Document:** `release_scope` unknown 2.748, base_candidate 767, mixed_or_sote_candidate 366, sote_candidate 283.

**Trên máy TV1** (máy nhận bản sao): PostgreSQL `index-beast` có **0 document, 0 chunk**. Qdrant ở cổng 16333 **không có collection `lore_chunks`**. Dữ liệu mới nằm trên đĩa, chưa được nạp.

## 4. Vấn đề rút ra (góc nhìn Data Engineer)

1. **Không có bản phát hành dữ liệu rõ ràng.** Bản cuối chỉ được nhận ra qua README/handover; 30 lượt chạy nằm lẫn với bản cuối và với 592 MB bộ cài Docker.
2. **Artifact không di chuyển được.** `manifest.json`, `input-fingerprints.json` và `report.json` ghi đường dẫn tuyệt đối `D:\Index-Beast\...` (máy TV2). Sang máy khác (`D:\Hoc_Tap\...`), mọi bước kiểm fingerprint theo đường dẫn đều phải sửa tay.
3. **Chunk quá vụn: ảnh hưởng lớn nhất tới chất lượng truy xuất.** Gần một nửa chunk EN dưới 50 token; infobox bị cắt thành từng dòng. Các mảnh "Slots Used: 1" giống hệt nhau giữa hàng trăm trang chiếm chỗ trong top-k mà không mang ngữ cảnh. Embedding câu ngắn cũng kém ổn định.
4. **Phạm vi sản phẩm lệch chính sách làm sạch.** Sản phẩm đã mở sang gameplay/build, nhưng clean vẫn bỏ Weight, FP, HP/Runes, bảng chỉ số và các mục Effects/Acquisition (số liệu trong audit TV2). Chatbot sẽ không trả lời được câu hỏi thông số.
5. **Metadata để lọc chưa dùng được.** 60% chunk có `release_scope=unknown`, nên chưa lọc được base/SotE. `spoiler_level` trống, nên tùy chọn tắt spoiler luôn trả rỗng.
6. **Lỗi nội dung đã biết:** trang mẫu Talisman Template lọt vào corpus; 17 chunk tiếng Bồ Đào Nha gắn nhãn `en`; 15 chunk tab 🇹🇼 gắn `unknown`; còn sót markup `[[...]]` (chi tiết trong audit TV2).
7. **Chỉ số trên 4.157 vs 4.164:** 7 trang lỗi ảnh vẫn có text trong clean và chunk. Đúng, nhưng phải đọc `checkpoint.json` mới thấy; report crawl ghi `partial`.

## 5. Đề xuất xử lý

Nguyên tắc: không crawl lại; mọi bước ghi vào thư mục mới; đánh giá A/B bằng golden set trước khi thay corpus đang phục vụ. Không xây hạ tầng mới (orchestrator, data lake).

### P0: làm ngay đầu S3

| # | Việc | Phụ trách | Kết quả mong đợi |
|---|---|---|---|
| 1 | **Đóng gói bản phát hành `data/releases/s2-r1/`** gồm `raw` (danh sách đường dẫn revision cuối), `clean`, `chunk`, `MANIFEST.json` (đường dẫn **tương đối**, SHA-256, số lượng, commit code đã sinh ra). Code đọc release qua một biến `DATA_RELEASE`, không trỏ thẳng tên run | TV2, TV1 review | Mọi máy biết chính xác bản nào là cuối; chạy lại được ở đường dẫn khác |
| 2 | **Dọn `backend/data`:** xóa `local-setup/`; chuyển 30 lượt thử sang `archive/` hoặc xóa (chỉ giữ regression 200 làm test). Media 8 GB phân phối riêng, không gói chung với text | TV2 | Gói text ~0,5 GB dễ chia sẻ |
| 3 | **Nạp lên máy chung:** `python -m ingest.chunk.load_full` rồi index EN vào Qdrant (~17 phút) trên máy demo | TV1 + TV3 | Demo S3 chạy trên dữ liệu thật; index cần người dùng xác nhận chạy embedding |
| 4 | **Sửa lỗi nội dung đã biết** (template, map tab 🇧🇷/🇹🇼, markup), đúng thứ tự P0 trong audit TV2 | TV2 | Release `s2-r2`, có test âm cho từng lỗi |

### P1: trong S3

| # | Việc | Ghi chú |
|---|---|---|
| 5 | **Gộp chunk vụn**: trong cùng một section, gộp các unit liên tiếp tới khoảng 250–350 token. Mỗi trang có một **"thẻ infobox"** (tiêu đề + mọi trường) thay vì một chunk cho mỗi trường. Giữ nguyên ranh giới dialogue/quote | Ước tính 18,4k chunk EN còn khoảng 8–10k; thời gian index giảm tương ứng. Chỉ thay sau khi Recall@5 và MRR trên golden set không giảm (A/B hai collection) |
| 6 | **Chốt phạm vi gameplay bằng CHANGE-REQ.** Nếu giữ gameplay, cách rẻ nhất là thêm "thẻ thông số" dạng văn bản cho mỗi vật phẩm (trường infobox + hàng bảng chỉ số có header), gắn `content_type=stats`. Chưa cần bảng dữ liệu cấu trúc riêng | Nếu bỏ gameplay: sửa README, prompt và golden set cho khớp |
| 7 | **Index theo release và đổi bằng alias Qdrant** (`lore_chunks` → `lore_chunks_s2_r2`) | Thay corpus không ảnh hưởng lúc đang phục vụ; xóa luôn point cũ (phát hiện #6 của code review) |
| 8 | Tính `release_scope` từ category và infobox có bằng chứng; ghi `unknown` khi không chắc. Tắt tùy chọn `spoilers=false` cho tới khi có `spoiler_level` | Không gán hàng loạt |

### P2: S4–S5

- Cập nhật tăng dần theo revision (FR-ING-07): crawl chỉ trang đổi revision, clean/chunk lại theo trang, upsert và xóa point theo `doc_id`.
- Rà soát giấy phép ảnh trước khi web hiển thị rộng.
- Một lệnh `make data-release` chạy chuỗi clean → chunk → validate → nạp PG → index collection mới, bằng các CLI đã có.

## 6. Việc cần team quyết định

1. Có giữ phạm vi gameplay/build không (quyết định P1 #6).
2. Ai giữ bản phát hành dữ liệu và chia sẻ bằng cách nào (ổ chung, Google Drive, GitHub Release), kèm checksum.
3. Có đồng ý xóa `local-setup/` và các lượt chạy thử không.

## 7. Cách tái lập số liệu

Script khảo sát là script tạm của TV1 (không đưa vào repo), chỉ đọc file. Kết quả kiểm chứng chính:

- SHA-256 của `content_clean_all.csv`, `review.csv`, `images.csv` khớp `delivery/s2-full/manifest.json`.
- SHA-256 của `chunks.jsonl`, `chunks.csv`, `documents.jsonl`, `review.jsonl`, `coverage.jsonl` khớp `chunk_runs/s2-full-v1/report.json`.
- 4.157 id trong `report.json` crawl đều có snapshot. 7 snapshot còn lại đúng là 7 trang lỗi ảnh.
- Không đọc nội dung ảnh, không decode pixel.
