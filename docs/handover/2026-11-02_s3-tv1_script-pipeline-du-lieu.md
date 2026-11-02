# Script chạy pipeline dữ liệu: crawl, clean, chunk, load, index

| | |
|---|---|
| Ngày | 02/11/2026 |
| Người thực hiện | TV1 (Hoanbucon); logic từng bước vẫn thuộc TV2 (crawl/clean/chunk) và TV3 (index) |
| Nhánh | `feature/s3-tv1-script-pipeline-du-lieu` (từ `develop` tại `4fc69e4`) |

## Vấn đề

Mỗi bước dữ liệu là một CLI riêng với tham số bắt buộc dài (`--run-dir`, `--output-dir`, `--tokenizer`…). Người chạy phải nhớ đường dẫn của bản cuối và tự tìm tokenizer E5. `python -m ingest clean` lại là luồng cũ cho mẫu 200 trang, dễ chạy nhầm.

## Đã làm

- `backend/scripts/data_pipeline.py`: một lệnh cho mỗi bước, **chỉ gọi lại** các CLI có sẵn, không đổi logic pipeline.

  | Lệnh (từ `backend/`) | Gọi tới | Mặc định |
  |---|---|---|
  | `python -m scripts.data_pipeline status` | (đọc `report.json`) | In bản crawl, clean, chunk mới nhất |
  | `… crawl` | `ingest.crawl.full --run-id s2-full-20261028` | Resume lượt crawl hiện có; không nằm trong `all` |
  | `… clean` | `ingest.transform.full` | Đầu vào là lượt crawl trên; đầu ra `data/clean_runs/clean-<thời-gian>` |
  | `… chunk` | `ingest.chunk.full` | Đầu vào là bản clean full mới nhất; tokenizer tự tìm trong `models/fastembed` (cùng SHA-256 với tokenizer TV2 dùng); đầu ra `data/chunk_runs/chunk-<thời-gian>` |
  | `… load` | `ingest.chunk.load_full` | Luôn `--validate-only` trước, rồi mới ghi PostgreSQL |
  | `… index` | `ingest index` | `--policy pilot --languages en`; index thật **bắt buộc `--collection`** |
  | `… all` | clean → chunk → load → index `--dry-run` | Không index thật, không crawl |

- **"Mới nhất"** chỉ tính các lượt có đúng phiên bản pipeline full và **đủ số trang của lượt crawl** (4.164), nên không chọn nhầm lượt thử 20 hay 200 trang. Mọi bước nhận `--input` và `--output` để chọn thủ công.
- `Makefile`: `make data STEP=<bước> ARGS="…"` (mặc định `status`).
- `backend/ingest/README.md`: thêm bảng "Chạy nhanh".
- `backend/tests/unit/test_data_pipeline.py`: 4 test (bỏ lượt thử, chọn đúng phiên bản, chặn index thiếu collection, đầu ra mới có thời gian).

## Kiểm tra trên máy TV1

| Lệnh | Kết quả |
|---|---|
| `status` | crawl 4.164 trang; clean mới nhất `s2-full-v3-tv1-test`; chunk mới nhất `s2-full-v1` (bỏ qua lượt thử `s2-full-20-repeat`) |
| `index` không có `--collection` | Dừng với thông báo, không gọi CLI |
| `index --dry-run` | 18.368 nhận, 0 invalid (giống gọi trực tiếp) |
| `load --validate-only` | 4.164 document, 23.765 chunk hợp lệ, 0 ghi DB |
| `chunk --input data/clean_runs/s2-full-v3-tv1-test --output data/chunk_runs/s3-chunk-tv1-test` | 33 giây, exit 0; 23.780 chunk (bản kiểm thử, không bàn giao) |
| Backend unit test | 536 passed; ruff đạt |

## Đính chính về chunk sau khi sửa cleaner (PR #53)

Chạy chunk thật trên bản clean mới cho thấy nội dung **không đổi** (73.864/73.864 dòng thân chunk trùng khớp). Tuy nhiên **số chunk tăng 15** (23.765 → 23.780; tiếng Anh 18.368 → 18.383) ở 14 trang boss: khối chỉ số `excluded` chen giữa các trường infobox nên một cụm trường bị tách làm hai. Đã sửa câu "chunk chưa khác" trong [handover sửa cleaner](2026-10-31_s2-tv1_sua-cleaner-bang-chi-so-infobox.md) và [handover setup máy TV1](2026-11-01_s3-tv1_techstack-rag-va-setup-may-tv1.md).

Hệ quả: khi dùng chunk mới, phải nạp lại PostgreSQL và **index vào collection mới**, vì chunk ID của 14 trang này đã dịch.

## Chưa làm

- Không chạy `crawl` (gọi mạng, mất hàng giờ), không chạy `load` thật hay `index` thật bằng script.
- Lệnh cũ `python -m ingest clean` vẫn giữ nguyên cho luồng mẫu.
