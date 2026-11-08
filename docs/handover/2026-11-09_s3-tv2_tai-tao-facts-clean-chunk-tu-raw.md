# TV2 — Tái tạo facts/clean/chunk từ raw cuối

Ngày 09/11/2026; nhánh fix/s3-tv2-chat-luong-du-lieu. Quyền thực hiện đã chốt qua
4 câu hỏi: giữ raw/ảnh/manifest/crawl state, xóa dẫn xuất cũ, thực hiện P0/P1/P2,
phần chưa rõ review; chỉ offline, không crawl thêm/embedding/index/push.

[Meta prompts đã dùng](../prompts/2026-11-08_tv2-rebuild-structured-tables.md).
[Báo cáo đầy đủ, ví dụ và hạn chế](../testing/2026-11-09_tv2-structured-release.md).

## Thay đổi và phạm vi

- core/text/structured_tables.py và table_quality.py: grid ô gộp, role/header,
  decision theo cell, bảng theo schema và quality gate thuần.
- core/text/html_clean.py, lore_policy.py, chunking.py: opt-in table_fact, giữ
  legacy infobox/dialogue; locale/row context, chunk nguyên hàng.
- ingest/transform/full.py, table_artifacts.py: điều phối filter → serialization,
  provenance/metadata, facts_clean/catalog/review và CSV round-trip.
- ingest/chunk/full.py, load_full.py: metadata/version 2.0 và validate-only.
- ingest/debug/verify_structured.py, reset_derived.ps1, publish_structured_local.ps1:
  kiểm offline và thao tác artifact đã được ủy quyền; không ghi DB.
- tests/unit/test_structured_tables.py, README ingest, baseline/sample metadata
  trong docs/testing và các tài liệu bàn giao.

Không thay schema/entities/API/UI hoặc retrieval/LLM/encoder của TV1/TV3/TV4.
Giữ các thay đổi đang có, stash 04b001ca2192109ec379ee65dc8ed7b4f407122b không đổi.
Chưa commit/push/PR/merge trong lượt này.

## Đầu ra thực tế

4.164 raw, 10.371 file ảnh giữ nguyên; 8.506 bảng, 255.039 ô được hạch toán.
118.498 fact catalog: 70.561 keep, 47.937 review. Clean 29.239 dòng; chunk
39.551, trong đó 34.047 EN. Table keep gồm cả giữ từng phần, không phải chứng
nhận mọi ô hoặc nội dung wiki. Compatibility thiếu subject vẫn review.

Đã dọn root clean/chunk/research/delivery cũ sau khi giữ fingerprint raw/state;
sau thử nghiệm xóa 15 thư mục trung gian. Chỉ còn một bộ dẫn xuất structured-release.
Local-setup là cấu hình môi trường, giữ nguyên. Manifest/raw source cần thiết không xóa.

Điểm vào `D:/Index-Beast/backend/data/delivery/final/README.md`, manifest.json:

- raw → data/raw/wikigg, media → data/media, source → crawl run cuối.
- facts → data/clean_runs/structured-release/tables, dùng **facts_clean.csv/jsonl**.
- clean → data/clean_runs/structured-release, dùng **content_clean.csv**.
- chunk → data/chunk_runs/structured-release, dùng chunks.csv/jsonl.
- report → data/research_runs/structured-acceptance.

Các alias là junction, không phải bản copy. `table_facts.*` và content_clean_all.csv
là catalog có review; không index nguyên các file này. Data chỉ local, Git ignore.

## Kiểm thực tế và còn lại

93 unit test đạt/20 skip fixture cũ; 37 test nhóm clean/table/chunk/stats đạt.
Ruff check/format/diff check đạt. 8.330 fingerprint input khớp; CSV round-trip,
source cell/column, ID, token450/overlap50, sample20 stable và full source coverage
đã kiểm. 39.457/39.457 unit phủ; stats1.551 và 15/15 fact baseline không mất.
Validate-only 4.164 docs/39.551 chunks, database writes 0; encoder/API calls 0.

50 mẫu assistant review gồm 38 source-structure consistent, 10 quarantine đúng,
2 context review recipe applicability; chưa human approval. 327/486 ứng viên
equipment chưa thấy upgrade table trong raw, không tự suy là crawler lỗi.
Header/legend/compatibility chưa rõ, source_updated_at/spoiler_level và license
ảnh là hạn chế còn lại. Chưa kiểm retrieval, LLM, DB integration hoặc full backend suite.

Sửa qua kiểm tra: Move Name lặp không thành fact giả, Required có Attribute,
recipe # item/material tách vai trò, EN/JP tách cột, bullet cookbook không bị
phép kiểm nhầm là tiếng Nhật, separator/note chưa giải nghĩa review. Xem báo cáo
để phân biệt lỗi đã sửa với hạn chế nguồn còn lại; không tuyên bố sạch hoàn toàn.

Lệnh chạy lại ở README ingest, bật `--gameplay --structured-tables`, output mới.
Không tự gọi runner TV1 để index version S3; tích hợp runner/retrieval cần thành
viên phụ trách review. Script reset/publish có xóa artifact, không chạy khi chỉ test.
