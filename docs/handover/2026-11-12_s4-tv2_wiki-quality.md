# TV2 Sprint 4 · Chất lượng dữ liệu wiki

Nhánh `feature/s4-tv2-wiki-quality` từ `origin/develop` tại `c323445`. Phạm vi gồm hai thẻ TV2 trong [Sprint 4](../../planning/sprint_plan.json) và cohort wiki.gg của lượt crawl đã nghiệm thu. [Meta prompts đã dùng](../prompts/2026-11-12_tv2-s4-wiki-quality.md).

## Bản dữ liệu

Mở `backend/data/delivery/s4-wiki/manifest.json` để tra các artifact local. Raw, ảnh, clean và facts tái sử dụng bản S3 đã nghiệm thu. Bản chunk mới nằm trong `backend/data/chunk_runs/s4-wiki-release/`. Báo cáo và collection Qdrant local nằm trong `backend/data/research_runs/s4-wiki-release/`. Dữ liệu sinh ra thuộc thư mục data đã gitignore.

- 4.164 tài liệu, 4.163 trang có chunk và 1 trang template vẫn vào review. Có 39.574 chunk, trong đó 34.070 EN, cùng 1.543 mục review. Toàn bộ 39.480 đơn vị chunk có coverage và giới hạn 450 token.
- Đối chiếu S3 và S4 giữ đủ 74.840 bộ định vị nguồn và 45.204 fact ID tham chiếu từ chunk. Số chunk tăng 23 do đổi ranh giới. Có 40 chunk được gắn nhãn chặng lấy từ HTML, trên 18 trang.
- `game_scope=elden_ring` áp dụng cho cohort base + Shadow of the Erdtree theo [ADR-004](../adr/004-base-game-scope.md). Giữ `release_scope` là tín hiệu riêng. Trong 4.164 trang có 767 `base_candidate`, 283 `sote_candidate`, 366 `mixed_or_sote_candidate` và 2.748 `unknown`. Không có tựa trang độc lập của Nightreign/Tarnished Edition trong cohort này.
- Đọc lead, danh mục, revision và ngữ cảnh của mẫu 50 trang cố định theo seed 4164. Mẫu có 10 base candidate, 10 SotE candidate, 10 mixed/SotE candidate và 20 unknown. Không thấy trang thuộc game khác trong mẫu. Ví dụ Knight of the Solitary Gaol có lead SotE dù release heuristic cũ trả `unknown`. Nhãn `unknown` vẫn lưu nguyên để tránh diễn giải heuristic thành phân loại release đã xác nhận.
- `spoiler_level` gồm 33 chunk mức 0, 38.505 mức 1 và 1.036 mức 2. Mức 0 giới hạn ở định nghĩa địa danh đầu game, phần giới thiệu/trang bị khởi đầu hoặc tutorial cơ bản đã xem trực tiếp. Mức 1 chứa tiến trình, DLC/hỗn hợp hoặc chưa xác lập an toàn. Mức 2 đánh dấu ending/khu vực cuối game theo tiêu đề, danh mục, heading hoặc nội dung. Chấm theo toàn đơn vị nguồn trước khi cắt token, lấy mức cao nhất cho document. Nhãn là heuristic, vì vậy độ phủ ở chế độ tắt spoiler còn hẹp.
- CSV và JSONL ghi cả `spoiler_reason`, `spoiler_rule_version`, `game_scope_reason` và `quest_stage`. Loader PG chuyển tiếp `spoiler_level` từ artifact S4.

## Triage eval

Đối chiếu [golden 25 ngày 09/11](../testing/2026-11-09_golden-25-by-difficulty/README.md), [gameplay 05/11](../testing/2026-11-05_gameplay-evaluation.md) và [evidence/media/build 07/11](../testing/2026-11-07_evidence-media-build-10/README.md).

| Ca | Phân loại theo bằng chứng | Xử lý |
| --- | --- | --- |
| IB-GS-086 | Decision/query trước retrieval. Report ghi truy vấn mất dấu phẩy của Leyndell, Ashen Capital và bị validator từ chối. Raw/chunk có diễn biến sau Maliketh. | Giữ tên nguồn. Bàn giao replay/validator cho TV3. |
| IB-GS-075 | Có bằng chứng gốc tại Ranni cùng revision. Chunk S3 ghép vị trí rương với những chặng khác và đoạn mở ending, tạo ứng viên rộng. | Tách theo nhãn chặng lấy từ HTML. Bảo toàn điều kiện Radahn, rương và hướng đông bắc của Grace trong chunk Nokron. |
| IB-GS-052 | Đã có bằng chứng ở Ainsel River. | Chunk ngắn hơn, vẫn giữ Baleful Shadow, chìa khóa, Rennala và rương. Thứ hạng E5 local giảm, xem bảng dưới. |
| IB-GS-061, GP-01:3 | Báo cáo cũ ghi assessor đòi mức chi tiết ngoài câu hỏi, hoặc selection bỏ rule đã có. | Bàn giao retrieval/assessment. Giữ các note gameplay và bảng thuộc tính đã qua pipeline. |
| IB-GS-091/092 | Nguồn vàng cho công thức là trang /stats ở nguồn ngoài cohort wiki.gg. Báo cáo 05/11 ghi 092 từng bị hỏi lại thừa. | Giữ provenance nguồn ngoài trong eval. Chưa gán công thức cho wiki.gg. |
| EMB06, EMB08 | Dữ liệu lớp khởi đầu Vagabond/Bandit thiếu snapshot trang chủ thể. Zweihander/Reduvia có trong cohort. EMB06 còn có lỗi schema. | Ghi thiếu dữ liệu đầu vào. Không suy từ trang giáp cùng tên. |
| EMB07, EMB09, EMB10 | Lỗi decision/validation được ghi trong eval. Trang chủ thể lớp Hero cũng thiếu snapshot, nhưng lượt EMB07 đã dừng trước tool. | Bàn giao TV3 theo bằng chứng từng tầng. |
| EMB01/03, EMB02, EMB04/05 | Văn bản phủ nhận ảnh đã trả (01/03), ảnh cùng hash bị lặp ở kết quả (02), hoặc web thiếu candidate đủ liên kết (04/05). | Bàn giao kiểm lại generation/selection ảnh. Giữ ảnh nguồn, provenance và occurrence. |

### Đo lại local

So cùng tập EN, FTS5 BM25 top 16 trên toàn corpus, sau đó xếp hạng lại 16 ứng viên bằng cosine E5 có sẵn trên máy. Chạy 25 câu nguyên văn và 6 truy vấn từ khóa đối chiếu bằng chứng. Báo cáo lưu chunk, revision, vị trí DOM và hạng. Kết quả source top 5 của 25 câu qua E5 là 19 ở cả hai bản. Con số này tính sự xuất hiện trang URL kỳ vọng trong top 5, gồm cả ca hành vi và ca cần nguồn ngoài trong mẫu số.

| Ca | Token bằng chứng S3 → S4 | Hạng BM25 S3 → S4 | Hạng E5 S3 → S4 |
| --- | --- | --- | --- |
| IB-GS-075 | 383 → 152 | 15 → 2 | 7 → 1 |
| IB-GS-052 | 442 → 218 | 10 → 8 | 7 → 10 |
| IB-GS-065 | 83 → 83 | 1 → 1 | 1 → 1 |
| IB-GS-031 | 47 → 47 | 1 → 1 | 1 → 1 |
| IB-GS-041 | 88 → 88 | 1 → 1 | 3 → 3 |
| IB-GS-086 | 414 → 414 | 4 → 4 | 3 → 3 |

## Re-index và kiểm thử

Ghi payload EN vào collection cục bộ `s4_wiki_payload_en` bằng `CorpusPolicy("pilot", ("en",))`. Kiểm đếm 34.070 point và xác minh chính xác 33 ID qua bộ lọc `spoilers=false`. Qdrant local này lưu payload và chạy phép lọc, không có vector và không thay collection đang phục vụ. Hai bước FTS5/E5 đo retrieval riêng. Chưa có phép chạy lại hybrid/LLM end-to-end. Docker Engine chưa kết nối được và cache FastEmbed thiếu `Qdrant/bm25`. Không phát sinh lượt LLM, gọi wiki hay ghi PostgreSQL. 53 test mục tiêu pass. Hai suite RAG bổ sung dừng ở collection test do venv thiếu `langchain_core`. Ruff và git diff --check pass.

## Chạy lại

Từ `backend/`, dùng đường dẫn local đã có đến snapshot model E5 và đặt tên thư mục mới.

```powershell
$env:HF_HUB_OFFLINE = '1'
$model = '<local multilingual-e5-small snapshot>'
.venv/Scripts/python.exe -X utf8 -m ingest.chunk.full --wiki-quality --input-dir data/clean_runs/structured-release --tokenizer "$model/tokenizer.json" --output-dir data/chunk_runs/s4-wiki-replay
.venv/Scripts/python.exe -X utf8 -m ingest.debug.s4_wiki_eval --before data/chunk_runs/structured-release --after data/chunk_runs/s4-wiki-replay --golden-report ../docs/testing/2026-11-09_golden-25-by-difficulty/report.json --model-snapshot "$model" --output data/research_runs/s4-wiki-replay
```

Lệnh index thật sau khi TV3/TV1 có môi trường test đầy đủ dùng `python -m ingest index --input data/chunk_runs/s4-wiki-release/chunks.jsonl --policy pilot --languages en --collection <collection-test-moi>`. PostgreSQL có thể kiểm trước bằng `python -m ingest.chunk.load_full data/chunk_runs/s4-wiki-release --validate-only`. Chạy eval API trên collection test đó và đối chiếu trước khi đổi cấu hình hệ thống đang phục vụ.
