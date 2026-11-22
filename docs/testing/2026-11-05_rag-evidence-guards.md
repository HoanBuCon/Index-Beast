# Kiểm thử offline guard và evidence — 05/11/2026

TV3 MinhMuc · nhánh `fix/s3-tv3-rag-evidence-guards` · chưa commit/push/PR.

## Căn cứ và phạm vi

Sửa theo [baseline thật 25 câu ngày 04/11](2026-11-04_golden-25-auto/analysis.md),
[report](2026-11-04_golden-25-auto/report.json) và observations trong cùng thư mục.
Không sửa report, golden/expected_answer, review status, corpus hay `.env`.
Lượt này không gọi DeepSeek/Tavily, embedding, server/DB, index, notebook hoặc tải model.

Report gốc SHA-256: `1ceecc01d50ee01d02be6a25c900bc9180640a49b8e43df3abb34a811d9cf104`.
Đã đối chiếu 24 assessor output, 8 rewrite output và nhóm 2 generation output build
trong [fixture](../../backend/tests/fixtures/golden_guard_replays.json) với report: **33 phép đối chiếu đạt**.
Fixture giữ output thật; các bản đồ index/quote ID assessor tái dựng từ candidate cũ dùng placeholder text,
chỉ phục vụ schema/reference replay. Không dùng chúng để chấm mức đủ bằng chứng ngữ nghĩa.
Context 044/050 giữ text/metadata candidate từ artifact, không nhét expected_answer vào model.

## Kết quả thực tế

| Kiểm tra | Trước sửa / vấn đề quan sát | Sau sửa offline |
|---|---|---|
| Unit suite trước sửa | 614 passed, 1 warning, 20,28 giây | 684 passed, 1 warning, 20,58 giây ở lượt cuối |
| Assessor output thật | 23/24 bị lỗi list/string trong lượt live cũ | 24/24 parse và reference replay đạt; giữ nguyên mọi ID |
| Rewrite từng bị chặn | 8 fallback trong baseline | 8/8 output đúng ý cũ qua guard; negative tests vẫn chặn |
| Case 044 | Context bỏ đá thường dù candidate có | Selection giữ đoạn +25 thường và +10 Somber trong top-5/budget |
| Case 050 | 3 alias trùng chiếm chỗ; thiếu điều kiện quest | 3 alias → 1 hit với 3 provenance; selection có đoạn phủ định tính bắt buộc |
| Build 027 | Hai output thật đều sai contract | Vẫn reject cả hai; scripted recovery hợp lệ hỏi lại, đúng 2 lượt |
| Nhiều quote/source | Chỉ có quote ID đơn | 1–3 ID/source, resolve chính xác; JSON/SSE cùng giữ Source contract |
| Ruff / format | Kiểm sau sửa | Đạt, 198 file đã đúng format |
| OpenAPI / pip check | Kiểm sau sửa | Không lệch spec; không có dependency hỏng |

70 regression mới trong [test_evidence_guards.py](../../backend/tests/unit/test_evidence_guards.py).
Một warning từ Qdrant memory: payload indexes không có hiệu lực trong memory mode, cần server để kiểm tính năng đó.
Suite cũ vẫn kiểm ba mode, web modes, follow-up Marika/Moonveil, ảnh local, history, cancellation,
recovery trước emission và không done thành công khi stream lỗi. Không bỏ assertion cũ để đạt test.

## Thay đổi hành vi và contract

- Assessor: `evidence={"1":["q1","q2"]}`, max 5 source và 3 ID/source. String cũ → singleton list,
  không tự lấy phần tử đầu hoặc bỏ evidence. Reject index/ID lạ, rỗng, trùng và sai kiểu.
  Sufficient cần covered không rỗng, evidence hợp lệ và missing rỗng; không dùng confidence.
- Trace: `local_sufficient`, `local_partial`, `local_insufficient`, `ambiguous`, `assessment_error`.
  Auto sufficient bỏ web; partial/insufficient/error tìm web theo budget; ambiguous hỏi lại.
  Lỗi đánh giá giữ status unknown thay vì coi là bằng chứng local không có đáp án.
- Rewrite: nhận diện khung ngữ pháp đầu câu thay vì tách mảnh chữ tiếng Việt thành tên riêng.
  Chỉ canonicalize hai full-name biến thể Fragment/Fragments và Ash/Ashes đã khai báo;
  không stemming/fuzzy mọi tên. Vẫn giữ số, tên, phủ định, mục tiêu và ý định.
  Chưa phải NER hoặc bộ chứng minh tương đương ý nghĩa.
- Context: sau policy/spoiler/URL checks, ưu tiên section questline/progression hoặc description/notes/infobox
  phù hợp ý hỏi; dành một candidate cho mỗi entity đã xác định nếu có. Không tạo evidence cho target vắng,
  không tăng K/budget, không truncate chunk. Ưu tiên này dùng metadata, chưa là semantic reranker.
  Tác dụng coverage thực thể cần rewrite hợp lệ cung cấp entities; không tự bật rewrite trong `.env`.
- Dedup: WebHit cùng text, title chuẩn hóa và toàn bộ metadata còn lại khớp mới gom;
  khác release/patch/speaker/variant/điều kiện hoặc missing/null thì giữ riêng.
  Alias giữ URL/point ID/thời gian, idempotent và qua Hit ↔ Document không mất payload.
  Source public giữ URL đại diện, không thêm trường API.
- Evidence generator: `quote_ids` 1–3 ID/source; tương thích `quote_id` hoặc quote legacy nguyên văn.
  Một evidence object/source, đúng một dạng reference. Source.text nối đúng đoạn bằng `\n[…]\n`.
  Không fuzzy quote hoặc tự mở cả trang để hợp thức hóa claim.
- Prompt: reward/use không suy thành quest requirement; phân biệt required/optional/suggested.
  Trả lời phần có căn cứ rồi nêu gap cụ thể; build có thể đưa hướng định tính có chứng cứ hoặc hỏi 1–2 điều kiện.
  Không bịa stat spread/AR/DPS, không kể quá trình tìm nguồn, không lặp disclaimer.

Không thêm semantic judge. Test chọn đúng text và resolve đúng reference không chứng minh mô hình sẽ chọn
đúng quote hoặc suy luận đúng trong lần live kế tiếp. Cả hai output lỗi thật của build vẫn bị reject;
scripted recovery không chứng minh DeepSeek thật đã hết 502. Lỗi provider/JSON/citation sau budget vẫn báo lỗi.

## Budget giữ nguyên

Mỗi request tối đa 1 rewrite, 1 assessment, 2 generation (một lần đầu + tối đa một recovery chung).
Không retry generation sau khi text SSE đã phát. Tối đa 2 query retrieval nếu cấu hình dual;
top-5 và context 12000 ký tự mặc định. Không thêm retrieval hoặc agent loop từ selection/dedup.
Tavily tối đa 1 Search + 1 Extract batch, 0 retry; deadline dùng chung 8 giây mặc định.
Deadline tổng ChatService 45 giây mặc định không được gia hạn. SDK transport retry của ứng dụng
vẫn theo cấu hình, nên logical call không đồng nghĩa số HTTP attempt.

## Lệnh đã chạy

Từ `backend/`, toàn bộ offline:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
.venv/Scripts/python.exe -m pip check
```

Có chạy riêng regression trong quá trình sửa. Không collect integration/route `test_llm` bên ngoài unit.
UTF-8 và 102 liên kết local trong 5 tài liệu đã kiểm đạt; `git diff --check` đạt.
Hash report gốc và 3 đầu vào golden/review/selection khớp snapshot, không đổi.

## Chạy lại 25 câu — chỉ hướng dẫn, chưa thực hiện

Restart API bằng `make dev` để dùng bản sửa với web/bot. Không cần reindex.
Benchmark dưới đây dùng trực tiếp pipeline, không cần API đang chạy; cần Qdrant/cached encoder và key thật.
Đối chiếu `snapshot.settings` và `input_hashes` của report gốc trước khi chạy: cùng collection/policy/language,
18.368 point tại baseline, prefetch 30, top-5, context 12000, rewrite enabled/query mode rewrite,
DeepSeek flash/temperature 0.2/max tokens 4096, overview enabled, retries 1, timeout 45,
web auto/max 3 results, cùng allowlist. Prompt hash đổi là chủ đích của bản sửa.
Lưu ý report snapshot ghi `rag_thinking_enabled=true` trong khi analysis cũ mô tả false;
lượt này không có wire trace để kết luận request provider thực tế. Khi so sánh cấu hình,
lấy snapshot đã lưu làm mốc và ghi rõ khác biệt này; không trộn lượt đổi thinking với hiệu quả sửa guard.
Không dump secret hoặc copy toàn bộ `.env` vào report.

Từ backend:

```powershell
# Chỉ đọc kế hoạch, không gọi model/server
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_golden --mode auto

# Tốn API + query embedding, CHƯA CHẠY trong tác vụ này
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_golden --execute --allow-llm --allow-web --mode auto --output-dir ../docs/testing/2026-11-05_golden-25-auto-after-guards
```

Thư mục đích phải mới. Runner giữ cùng 25 ID, 18 VI/7 EN, tối đa 100 logical model calls/50 Tavily requests,
transport retry SDK=0 trong runner. Không index/upsert hoặc sửa golden.
So sánh error, lý do assessment, tần suất search, rewrite fallback, context coverage rồi đọc claim/quote từng câu.
Chấm correctness/faithfulness riêng; grounded là protocol, không phải Accuracy/entailment.
Giữ review chéo TV2 và tập test mới ngoài tập 25 development. Xem [hướng dẫn đánh giá](../evaluation/golden-diagnostic-guide.md).

## Chưa được kiểm chứng

Chất lượng generation/quest/build/quote thực tế sau sửa, recall trên embedding thật, độ trễ/chi phí live,
đủ stat/class/progression và hiệu quả trên câu chưa gặp. Không thêm ảnh web, calculator hoặc migrate LangGraph.
Không khẳng định dữ liệu hiện tại đủ mọi câu gameplay; bản sửa xử lý lỗi contract/guard/selection đã quan sát.
