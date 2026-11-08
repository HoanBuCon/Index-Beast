# Kiểm tra dữ liệu và khả năng truy xuất RAG — TV2, 08/11/2026

Sau audit, người dùng yêu cầu xóa corpus cũ: đã bàn giao raw/clean/chunk tại
`backend/data/delivery/final`. Các số đo baseline phía dưới là lịch sử đã lưu;
corpus S2 và trial trung gian không còn trên đĩa. Xem [bàn giao dọn dữ liệu](../handover/2026-11-08_s3-tv2_ban-cuoi-va-don-du-lieu-cu.md).

## Kết luận

Corpus giao Sprint 2 chưa đủ cho câu hỏi thông số trang bị: trong 15 ca kiểm tra
đối chiếu raw, chỉ 1 ca còn bằng chứng trong corpus, dù cả 15 ca đều tìm thấy đúng
trang trong top 5. Đây là mất dữ liệu trước embedding, không thể chữa bằng việc
chỉ tăng điểm tương đồng vector.

Bản thử mới đã clean 4.164 trang, tạo 31.055 chunk và có cấu trúc phù hợp để
thử vector hóa. Chạy E5 local thật trong pool cố định 201 trang tìm được bằng
chứng đúng nguồn trong top 5 cho 15/15 ca thông số. Chưa đủ căn cứ công bố chất
lượng production hoặc chất lượng câu trả lời LLM. Người dùng chọn hoãn LLM;
lượt này không gọi API trả phí, không thay corpus/index đang dùng.

## Phạm vi và phương pháp

- Nhánh: `fix/s3-tv2-chat-luong-du-lieu`; chỉ sửa clean/chunk/validation TV2.
- Căn cứ: SRS, kiến trúc filter → transform, ADR-003/004, planning và handover.
  Phạm vi full data đã duyệt gồm base + Shadow of the Erdtree; không tự gán mọi
  trang là base. Nightreign/cross-game và nội dung thiếu căn cứ giữ review/excluded.
- Baseline lấy từ `backend/data/delivery/s2-full/manifest.json`, không chọn trial
  theo mtime. Cohort 4.164 snapshot lấy từ crawl run, có 7 trang lỗi media nhưng
  text hợp lệ. Không crawl lại, không sửa raw hoặc file ảnh.
- Kiểm toàn bộ cấu trúc, token bằng tokenizer E5, CSV round-trip, ID/hash,
  exact source slices, overlap, coverage, provenance và liên kết ảnh.
- Đọc trực tiếp 50 chunk EN mỗi bản, seed 20261108. Hai mẫu độc lập, không phải
  cặp trước/sau cùng nội dung; người kiểm là assistant, chưa có human approval.
- Chẩn đoán truy xuất riêng: 201 trang nguồn cố định gồm 51 trang nguồn dương
  và 150 trang nền chọn ngẫu nhiên. Chỉ embedding chunk nguồn, không đưa câu hỏi,
  đáp án kỳ vọng hoặc rubric vào corpus. Golden100 còn pending review.

## Các sửa đổi đã thực hiện

1. Bật `--gameplay` mới cho full clean: giữ mô tả, acquisition/effect/notes và
   thông số infobox có nhãn; phân biệt Attack Power với Guarded Damage Negation,
   Required với Scaling. Giữ số 0 và dấu gạch đúng nguồn. Giá trị `?` đưa review.
2. Gom infobox vừa giới hạn thành một unit, giữ passive effect cùng chỉ số.
   Infobox dài vẫn chia theo kiểu block và lặp table header trong embedding context.
3. Giữ dialogue, trigger và người nói khi nguồn khai báo. Không suy đoán speaker
   khi nguồn không có cột người nói. Giữ nguyên câu lặp có ngữ cảnh khác nhau.
4. Tab BR/TW ánh xạ pt/zh. Tab JP có ưu tiên hơn header “English Dialogue” bị
   sao chép sai trong raw Sellen. CJK chưa rõ trong bảng EN chuyển unknown.
5. Chặn template biên tập, đưa Behind the scenes/cut content vào review; giữ
   nhãn speculation cho câu suy đoán. Không biến wiki commentary thành lời game.
6. Hạn chế cắt/overlap giữa từ; vẫn lưu exact char offsets, không viết lại nguồn.

Mặc định full clean vẫn dùng policy S2. Policy S3 phải bật rõ `--gameplay` và
ghi ra thư mục mới. Runner của TV1 hiện nhận version prefix S2; không chỉnh runner
để tự chọn bản thử S3. Validator TV2 nhận cả hai phiên bản.

## Kết quả cấu trúc toàn corpus

| Chỉ tiêu | Corpus S2 | Bản thử cuối |
|---|---:|---:|
| Trang input | 4.164 | 4.164 |
| Chunk | 23.765 | 31.055 |
| EN | 18.368 | 25.607 |
| Unit được phủ | 23.659 | 30.947/30.947 |
| Chunk typed equipment_stats | 0 | 1.551 |
| Template lọt thành chunk | 5 | 0 |
| Behind the scenes thành chunk | 2 | 0 |
| Token tối đa, gồm prefix/context | 450 | 450 |
| Overlap tối đa | 50 | 50 |
| Body không quá 20 ký tự | 1.381 | 857 |
| Body lặp, occurrence vượt lần đầu | 2.068 | 2.138 |

Bản cuối có 23.110 chunk dưới 100 token, 7.020 từ 100–299, 925 từ 300–450.
300–500 là định hướng cho prose dài; không ép dialogue/description ngắn vào nhau
chỉ để đủ độ dài. Body lặp có thể thuộc trang, ngôn ngữ hoặc điều kiện khác nhau,
không tự xóa theo hash body toàn corpus.

Full clean: 74.681 block giữ, 2.181 review, 1.371 excluded, 37.151 node nhiễu
bị loại. CSV gồm 29.405 dòng content, 40.387 dòng review và 65.593 occurrence ảnh.
Review CSV chứa cả quyết định loại node; số dòng không phải số section review.
Chunk có 1.920 section/unit review, một trang template không có chunk là chủ ý.
Không có lỗi trong kiểm tra cấu trúc cuối; không phát hiện EN có CJK chiếm đa số.

Index **dry-run** policy pilot/EN: nhận 25.607, loại theo ngôn ngữ 5.448, invalid 0.
Load **validate-only**: 4.164 documents / 31.055 chunks; không ghi PostgreSQL/Qdrant.

## Truy xuất bằng vector thật

Model `intfloat/multilingual-e5-small`, revision
`614241f622f53c4eeff9890bdc4f31cfecc418b3`, ONNX CPU, mean pooling, normalize,
384 chiều, `query:` / `passage:`. Weights đã tải về cache local trong lượt được
ủy quyền kiểm embedding; đánh giá dùng `local_files_only=True`. Không có embedding
API, không dùng vector giả. Token dài quá 512 bị từ chối thay vì âm thầm truncate.
Cache lưu signature model/tokenizer, không dùng lẫn model khác.

| Giai đoạn | Chunk EN trong pool | Có đủ bằng chứng /15 | Đúng trang top5 /15 | Bằng chứng đúng nguồn top5 /15 |
|---|---:|---:|---:|---:|
| S2 trước sửa | 1.131 | 1 | 15 | 1 |
| Khôi phục gameplay | 1.608 | 15 | 15 | 14 |
| Gom infobox | 1.444 | 15 | 15 | 15 |
| Cuối, sửa ngôn ngữ | 1.455 | 15 | 15 | 15 |

Ca Uchigatana blood loss từng đứng thứ 6 khi effect là mẩu riêng. Gom infobox vừa
cap khắc phục ca này. Các ca đã được dùng để phát triển/sửa lỗi; đây là diagnostic
regression, không phải held-out test độc lập hoặc tỷ lệ thành công toàn corpus.

100 câu golden được encode; 80 câu có URL nguồn, 75 URL nguồn khớp pool, 71 câu
có ít nhất một URL đúng trong top5 cả trước và sau. Nhãn chưa duyệt; không gọi
71/80 là Recall/MRR chính thức hoặc đúng ngữ nghĩa. Một số URL khác canonical/alias;
hai câu cần quy tắc tính stat ngoài snapshot. Không thêm sidecar TV3 vào benchmark.

Ba câu thiếu căn cứ vẫn nhận cosine top1 cao khoảng 0,838–0,881 (thông số không
có trong snapshot, patch mới nhất hôm nay, build thắng PvP 100%). Điểm cao không
chứng minh câu trả lời. Chưa thử LLM hoặc hành vi từ chối trả lời.

## Ví dụ trước/sau và review trực tiếp

- Moonveil: trước tìm đúng trang nhưng mất Physical 73 và Guarded Physical 31;
  sau giữ riêng nhãn hai nhóm, cùng Weight 6.5 và INT Required 23 / Scaling C.
- Uchigatana: passive “Causes blood loss buildup (45)” được giữ cùng infobox;
  không lẫn 45 ở nhóm chỉ số khác thành bằng chứng blood loss.
- Sellen, source 8870: bảng JP ghi nhầm “English Dialogue”; sau lang=ja dựa trên
  tab JP, giữ nguyên trigger và text. Không dịch hay bổ sung lời thoại.
- Template source 5474: không còn “English line 1/2/3” trong chunk.
- Rya/Nepheli: giữ nguyên điều kiện “If talked to again”, title và Dialogue;
  speaker null khi nguồn không chỉ rõ speaker, không tự gán bằng tên trang.
- Mẫu baseline: 48 clean / 1 dirty / 1 review. Mẫu cuối: 48 clean / 0 dirty /
  2 review. Đây chỉ là nhận xét cấu trúc/ngữ cảnh của mẫu, không phải human gold.
- Hai review cuối: Whips > Ashes of War có câu “following Ashes of War:” nhưng
  bảng sau chưa được giữ; Skill: War Cry có chunk tiếp nối bắt đầu “250%…” cần
  đoạn trước để rõ loại đòn. Đã lưu ID và lý do trong sample50-final-review.jsonl.

## Hạn chế và đề xuất theo vai trò

TV2 cần ưu tiên vòng sau: parser bảng upgrade/affinity/compatibility có schema
riêng; nối context khi chia danh sách dài; rà soát source units không rõ; bổ sung
source_updated_at chỉ khi raw có căn cứ. Cả 31.055 chunk chưa có source_updated_at
và spoiler_level. Fetched_at không thay thế thời điểm cập nhật/phiên bản patch.
Morgott có nhãn resistance/giá trị raw gây mơ hồ; không tự đổi thành % khi chưa xác minh.

Ảnh giữ manifest, context và license status hiện có; không sinh caption, không
khẳng định đã đánh giá multimodal RAG. 7 lỗi media và quyền ảnh chưa rõ vẫn cần review.
1.694 chunk unknown language chưa được chứng nhận EN. Release scope là heuristic,
chưa chứng minh base/SotE cho từng câu. Clean full không có nghĩa mọi nội dung đều
được phép index; bảng/cut/cross-game không rõ vẫn ở review/excluded.

Đề xuất TV3: thử corpus mới trong collection riêng, giữ hybrid/alias/source filters;
đánh giá citation/evidence/abstention và LLM bằng golden đã duyệt. Chỉ điều chỉnh
retrieval sau khi phân biệt nguồn thiếu fact với rank miss. Không sửa runtime TV3
trong nhánh này. TV1 cần quyết định tích hợp version S3 vào runner sau review.

## Artifact, tái chạy và kiểm thử

Điểm vào local: `backend/data/delivery/final/manifest.json` và README.
Các đường dẫn trong manifest tính từ `D:/Index-Beast/backend`:

- `data/clean_runs/s3-quality-language-20261108/`: content_clean_all.csv,
  review.csv, images.csv, processed/filtered, report và input-fingerprints.
- `data/chunk_runs/s3-quality-final-20261108/`: chunks.jsonl, chunks.csv,
  coverage.jsonl, documents.jsonl, review.jsonl và report.
- `data/research_runs/s3-rag-readiness-20261108/`: baseline, protocol nguồn,
  before/final structure và retrieval, samples/reviews, dry-run, budget/cache manifest.

CLI tái chạy xem phần S3 trong `backend/ingest/README.md`; chọn output mới.
Code là artifact Git; dữ liệu lớn trong data bị ignore và chỉ có trên máy này.
Không thay manifest giao S2 hoặc tự publish trial vào database/index.

98 unit tests dữ liệu passed; Ruff check/format passed; git diff --check passed.
CLI opt-in 20 trang mới: 711 chunk, 687 unit được phủ; full run và CSV validation
đã hoàn thành. Full backend suite chưa chạy vì môi trường thiếu langchain_core;
integration DB/LLM chưa chạy. Kiểm fingerprint lại 8.330 input full clean không đổi;
checksum corpus S2 khớp baseline; stash giữ nguyên.
So sánh lượt CLI20 mới với chính 20 trang trong full run: 711 chunk có ID và
toàn bộ metadata/text giống nhau sau khi bỏ duy nhất updated_at; lưu rerun-stability.json.

API thực dùng: **0 cuộc gọi, 0 USD**. Phần LLM hoãn theo yêu cầu; trần đề xuất
0,50 USD chưa sử dụng. Không lấy việc script thành công làm bằng chứng dữ liệu
“sạch hoàn toàn”.
