# TV2 Sprint 5 · Cập nhật dữ liệu tăng dần và tài liệu pipeline

**Cập nhật quyết định ngày 16/11/2026.** Hoãn lịch cập nhật hằng tuần trên VPS. Nghiệm thu CLI trên staging và thiết lập lịch nằm trong backlog FR-ING-07. Xem [handover tài liệu pipeline](2026-11-16_s5-tv2_tai-lieu-pipeline.md). Nội dung bên dưới ghi lại trạng thái ở thời điểm bàn giao triển khai ban đầu.

Ngày 16/11/2026, nhánh `feature/s5-tv2-cap-nhat-tang-dan` từ `origin/develop` (`3719e02`). Agent của TV1 thực hiện thay phần việc TV2 (Himmel) theo yêu cầu của trưởng nhóm: pipeline Crawl, Clean, Chunking, Ingest phải co giãn khi dữ liệu tăng hoặc đổi. Thẻ 5.4 và 5.6, FR-ING-07. Chưa push, chưa mở PR.

## Phạm vi

- `python -m ingest update --source wikigg [--since ISO] [--dry-run] [--full-scan] [--max-pages N] [--batch-pages N] [--bootstrap-from DIR | --bootstrap-from-db]`.
- `backend/ingest/update.py`: phát hiện, phân loại, điều phối lô, state, resume. Mọi thành phần ngoài (nguồn, builder, index, PostgreSQL, jobs) được tiêm vào.
- `update_builder.py`: dựng chunk cho một lô bằng đúng `transform.full` (S3 structured) và `chunk.full --wiki-quality` trên run nhỏ `data/update_runs/<id>/`.
- `index/writer.py` (`QdrantIndex`): upsert theo point id ổn định rồi xoá point thừa của chính tài liệu; xoá tài liệu bị xoá.
- `chunk/sync.py` (`PgDocuments`): upsert document, thay chunk, đặt `deleted`, liệt kê tài liệu để bootstrap. `chunk/load_full.py` tách hàm `chunk_fields` dùng chung (hành vi không đổi).
- `jobs.py` (`DbJobLog`): dòng `ingestion_jobs` kind `update`; `sources/wikigg.py` thêm `recent_changes`; `[update]` trong `sources.toml`; `update_cli.py` nối thành phần thật và khoá chạy chồng.
- `scripts/ingest-weekly.sh` (cron), `docs/data-pipeline.md` (thẻ 5.6), dòng FR-ING-07 trong SRS.

## Quyết định

- State là file `data/state/wikigg-update.json` (revision và số chunk theo trang, mốc quét, cache category). Chọn file vì `data/` đã được mount bền trong Compose và không cần migration; PostgreSQL vẫn là nguồn nội dung. Khi quá lớn, chuyển sang bảng (ghi trong tài liệu).
- Phát hiện bằng recentchanges, quá 30 ngày hoặc `--full-scan` thì so `lastrevid` toàn bộ. So revision với state làm mọi lượt idempotent và bỏ qua sửa-rồi-hoàn-tác.
- Upsert trước, xoá point thừa sau (lọc `document_id`), nên dừng giữa chừng không để trang mất dữ liệu; chunk id theo ordinal nên trang co lại để lại point mồ côi nếu không xoá.
- State ghi sau mỗi lô; mốc chỉ đẩy khi không lỗi, không hoãn. Trang lỗi giữ revision cũ nên tự được làm lại.
- Dùng lại nguyên stage production thay vì viết đường clean/chunk riêng, tránh lệch kết quả giữa dựng toàn bộ và cập nhật.
- **Cần TV3 review**: `backend/ingest/index/writer.py` trước là stub do TV3 phụ trách và đã bị thay hoàn toàn bằng `QdrantIndex`.
- Trailer commit dùng `Claude Sonnet 5.5` (model thực tế) thay vì dòng `Opus 5.5` trong common-rules.

## Kiểm tra

Chạy bằng venv của repo chính, từ `backend/` của worktree:

- `ruff check .`: All checks passed. `ruff format --check .`: 282 files already formatted.
- `python -m pytest tests/unit -q`: **1169 passed, 20 skipped** (trước thay đổi: 1141 passed, 20 skipped; thêm 28 test).
- Test mới: `test_ingest_update.py` (recentchanges, continuation), `test_ingest_update_run.py` (12 ca: phân loại new/changed/deleted/unchanged, idempotent, co lại, lỗi từng trang, resume sau lỗi hạ tầng, dry-run, `--max-pages`, quét toàn bộ khi mốc cũ, ngoài phạm vi, redirect, log xoá không pageid), `test_ingest_update_index.py` (5 ca với client Qdrant và encoder giả), `test_ingest_update_builder.py` (4 ca, stage giả), `test_ingest_update_cli.py` (5 ca). Không mạng, không tải model, không embedding thật.
- `bash -n scripts/ingest-weekly.sh`: OK. Chạy với `docker` và `flock` giả: mã thoát 3 chuyển tiếp đúng, 75 khi khoá bận, 0 khi thành công, log ghi vào thư mục ngoài repo, thiếu `flock` báo lỗi mã 1.

## Chưa kiểm chứng

- Chưa chạy `update` với wiki.gg, Qdrant, PostgreSQL, FastEmbed thật; `PgDocuments`, `DbJobLog` và đường nối `update_cli.run` chỉ được kiểm import/biên dịch câu lệnh, không có DB thật.
- `PipelineBuilder` được test với stage giả; chưa chạy `transform.full`/`chunk.full` thật trên run một vài trang (cần tokenizer E5 cục bộ và dữ liệu ảnh).
- `recent_changes` kiểm bằng fake; chưa xác nhận thực tế wiki.gg trả `pageid` cho dòng log xoá và thời hạn lưu recentchanges.
- `docker-compose.prod.yml` chưa có trên `develop` (thuộc PR #109): **phụ thuộc PR #109**. Script tự dùng `docker-compose.yml` kèm dòng cảnh báo trong log khi thiếu file.
- Chưa phát hiện đổi chính sách clean/chunk (cần dựng toàn bộ vào collection mới); xem mục giới hạn trong `docs/data-pipeline.md`.

## Việc kế tiếp và cần TV1 quyết định

1. Chạy thử trên staging: `--bootstrap-from <bản chunk đang phục vụ> --dry-run`, rồi một lượt thật với `--max-pages 20`.
2. Bootstrap trên VPS: `--bootstrap-from-db` (TV1 đã chốt, là mặc định trong tài liệu).
3. TV3 review `index/writer.py` (stub bị thay) và bộ lọc xoá theo `document_id` (payload index đã có).

## Sửa sau review (TV1)

- `classify`: duyệt lại cây category tối đa một lần mỗi lượt (trước đây mỗi trang mới ngoài phạm vi lại duyệt). `refresh_scope` nay duyệt không giới hạn độ sâu như `crawl.full.inventory` (trước dùng `discover` độ sâu 1, sẽ coi nhầm trang ở category sâu là rời phạm vi).
- Trang đã biết rời mọi category phạm vi được xếp `deleted` (xoá Qdrant/PG/state), chỉ khi describe có trả category.
- `recent_changes`: dòng `log` `move` cập nhật tiêu đề trong state và đưa trang vào ứng viên; chấp nhận khoá `logtype` hoặc `log_type`, tên mới ở `logparams.target_title`.
- `builder.build` chạy qua `asyncio.to_thread`, không chặn event loop.
- `ingest-weekly.sh`: thiếu `docker-compose.prod.yml` thì dùng file gốc kèm cảnh báo; docs khuyến nghị cron `--full-scan` hằng tháng; `--bootstrap-from-db` là mặc định cho VPS.
- State có `pipeline_version` (clean + chunk); khác phiên bản đã ghi thì `warnings` trong báo cáo.
- Test mới: 6 ca trong `test_ingest_update_run.py` (duyệt category một lần, rời phạm vi, không xoá khi không có category, move rồi xoá theo tên mới, build ngoài event loop, pipeline_version). Kết quả: ruff check và format sạch, 1175 passed, 20 skipped, `bash -n` OK; script chạy thử với docker/flock giả cho thấy dòng cảnh báo khi thiếu file prod.
