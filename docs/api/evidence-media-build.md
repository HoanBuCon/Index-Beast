# Evidence, ảnh và build có nguồn — TV3

Áp dụng khi `CHAT_MODE=rag`, `CHAT_AGENT_ENABLED=true`, `CHAT_TOOL_AGENT_ENABLED=true`.
Không cần đổi `.env` nếu đã bật ba cấu hình này. Đợt triển khai này không sửa `.env` thật.

## Ai quyết định phần nào?

| Phần | Luồng agent | Backend giữ |
|---|---|---|
| Intent, rewrite, clarification, ký ức liên quan | Decision model hiện có | Schema, quyền conversation, correction, ngân sách |
| Local/web/snapshot/calculator | Tool planner dựa trên observation | Allowlist tool, off/auto/always, timeout, chống lặp |
| Context cuối | `finish/stop.evidence_ids`, tối đa 5 ID đã thấy | Admission, metadata, provenance, budget, dedup |
| Ảnh | Một decision bổ sung, tối đa 3 ID candidate | Association, hash, URL/network/file validation |
| Phương án chỉ số | Model trích dữ liệu có nguồn và đề xuất allocation | Số học, floor/cap/requirements, kiểm lại artifact |
| Câu trả lời | Generator diễn đạt theo ngôn ngữ yêu cầu | JSON, citation, quote, server-render allocation, SSE lifecycle |

Đường tool-agent không gọi `coverage_order` để xếp ưu tiên quest/stat/section theo keyword.
`evidence_ids` thiếu, lặp hoặc ngoài tập đã cung cấp → `rank_fallback` có trace (thứ tự ứng viên hiện có),
không quay về keyword và không tuyên bố fallback đã chứng minh đủ bằng chứng.
Nếu hết step budget trước finish, cũng dùng fallback. Selector không sửa text/metadata.
Preview tối đa 30 candidate, 1.000 ký tự/candidate và metadata điều kiện; top-5 hiện tại có text/quote units đầy đủ.

Các rule cũ còn tồn tại cho compatibility: `coverage_order` ở workflow không tool-agent;
`gameplay.py` khi tắt agent; calculator Samurai/Moonveil khi dùng protocol snapshot cũ.
Không xóa chúng khi còn caller/config/test. Bộ kiểm kỹ thuật không phải legacy cần bỏ.

## Ảnh

Agent nhận request đã resolve và metadata candidate từ những source **thực sự được cite**.
Không gửi URL do model tạo sang downloader. Model chỉ trả `{ "ids": [] }`, tối đa 3 ID phân biệt;
backend từ chối ID không tồn tại. Metadata là tín hiệu lựa chọn, không phải xác minh pixel bằng VLM.

- `exact_section`: occurrence đúng source/revision/section.
- `entity_page`: source ID/revision/game/release trùng canonical page nhưng section khác.
- `web_result`: ảnh thuộc chính result URL của Tavily đã Search và Extract thành evidence.

Ảnh trang cùng loại vũ khí hoặc cùng domain không tự động được coi là đúng chủ thể.
Metadata của menu/stat/inventory được loại sớm, model vẫn phải đánh giá ảnh nhóm, ảnh trang trí và sai thực thể.
Off không gọi web; auto vẫn để tool planner chọn; always giữ yêu cầu web cho câu game hợp lệ.
Lời chào/hủy không đi tìm ảnh. Khi tắt spoilers, pipeline này bỏ ảnh vì corpus chưa có nhãn spoiler đầy đủ.

Tavily Search dùng `include_images=true`, `include_image_descriptions=true` theo
[tài liệu Search](https://docs.tavily.com/documentation/api-reference/endpoint/search).
Chỉ dùng `results[i].images`; bỏ ảnh global không xác định result nguồn. Provider không trả ảnh gắn trang
thì không tự gán ảnh global hoặc scrape trang để bù. Description do provider tạo vẫn có thể sai.

Downloader chỉ HTTPS trên allowlist host ảnh trong `answer_media.py`, kiểm mọi IP DNS là public và pin IP
khi kết nối, giữ TLS hostname/certificate. Không redirect, không proxy URL tùy ý, timeout ngắn,
byte ≤ 5.000.000, pixel ≤ 16 triệu, MIME phải khớp raster decode được. Mỗi file SHA-256 có tên nội dung,
atomic replace với temporary riêng; endpoint cũ `/api/v1/images/{sha256}` đọc/kiểm lại hash và decode.
Web blobs nằm `backend/.cache/web-images/`, được gitignore; mỗi lần tải thành công dọn blob quá 7 ngày
hoặc vượt 128 MiB. Đây là cache dùng lại để phục vụ ảnh, không phải kho lưu trữ vĩnh viễn.
Local corpus/catalog không bị sửa. License/attribution giữ khi biết; unknown không chuyển approved.
Image resolver có deadline ≤6 giây, nằm trong thời gian còn lại của request và budget 6 model calls;
không đủ thời gian/call thì bỏ ảnh. Hỏng một download không xóa text. Thread tải ảnh có socket/read deadline;
hủy request không chờ nó hoàn tất, DNS vẫn chịu giới hạn resolver hệ điều hành.

JSON và SSE dùng `images[]` hiện có, chỉ thêm `association` tùy chọn. UI TV4 không bị thiết kế lại.
Có thể trả text trước ảnh; generator không tự chứng minh ảnh đúng thực thể.

## Dữ liệu build tổng quát

`build_data.BuildData` gồm class, weapon, usage, starting_level, 8 base attributes, requirements,
points_per_level, attribute_cap và class_floor_rule. Đợt này hỗ trợ **một tay, không bonus**;
hai tay/buff/AR/DPS/soft-cap/optimum chưa được calculator này chứng nhận.
Không có danh sách class/weapon đóng trên nhánh dữ liệu mới.

Mỗi số phải có `{value, source_id, quote_id, label}` từ original hit. Backend kiểm:

1. Kiểu số nguyên; đúng 8 khóa chỉ số; nhãn chỉ số đúng loại cần tính.
2. Label-value nằm liền nhau, hoặc header/cell Markdown cùng cột; bảng class phải có đúng row class.
3. Quote ID tồn tại, source URL/metadata giữ nguyên, không trộn release/patch/upgrade/affinity/NG/variant metadata đã biết khác nhau.
4. Có quote rule floor/respec, level rule, cap và requirements; không dùng số trơ hoặc instruction từ memory.
5. Tổng = tổng chỉ số nền + target level − starting level (progression được hỗ trợ: 1 điểm/level).
6. Mỗi giá trị không dưới class floor, không vượt sourced cap, đáp ứng requirements một tay.

Đây là **validation cấu trúc/lexical và số học**, không phải chứng minh semantic entailment toàn bộ bảng.
Model vẫn có thể hiểu sai completeness/điều kiện trong nguồn. `runtime_extraction_not_human_reviewed`
luôn khác approval; unknown metadata vẫn unknown. Chỉ có nguồn chưa đủ để gọi build phù hợp hoặc tối ưu.
Nguồn thiếu/cấu trúc không hỗ trợ phải tìm thêm hoặc trả hướng dẫn có nguồn; không bịa bảng đủ 8 số.

Kết quả calculator là `CheckedBuild`: allocation, dữ liệu chuẩn hóa, profile, source IDs,
units, provenance URL/timestamp/release/patch, tổng điểm, hash phiên bản và trạng thái chưa human review.
Artifact đi qua tool observation và payload generator. Context bắt buộc giữ các source kế toán (tối đa5)
trước candidate khác, nhưng vẫn tuân thủ admission/budget; nếu mất nguồn thì final validation fail.
Generator không được thay allocation; backend tính lại/hash lại, kiểm citation **đúng quote kế toán**,
rồi render tám giá trị đã kiểm. Không dùng văn bản tự sinh để chữa phép tính.

Cache factual input theo class/weapon/usage nằm riêng trong pipeline RAM, tối đa32 entry, TTL1 giờ;
không chứa player profile/history/allocation và không phải semantic memory người dùng. Có thể dùng lại
qua tool source_snapshot mà không search web lại; source metadata vẫn được admission/kiểm lại.
Restart làm mất cache này, không làm mất cache ảnh trên đĩa hay conversation PostgreSQL.

## Tự kiểm thử

Từ `D:\Index-Beast\backend`:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
# Plan, không gọi model/client:
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/evidence_media_build_10.json --max-turns 10 --probe-images
# Tự chạy một run MỚI, output phải chưa tồn tại, có dùng tiền API:
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/evidence_media_build_10.json --max-turns 10 --probe-images --execute --allow-llm --allow-web --allow-embedding --output ../docs/testing/my-evidence-media-build-run
# Resume đúng run đã bị ngắt; không replay lượt đang running/uncertain:
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/evidence_media_build_10.json --max-turns 10 --probe-images --execute --allow-llm --allow-web --allow-embedding --resume --output ../docs/testing/my-evidence-media-build-run
```

Runner dùng PostgreSQL DB và Qdrant memory collection test riêng, corpus chỉ đọc, encoder cache/offline-download,
SDK retry=0, checkpoint từng lượt (clarification reply cũng là một lượt). Không tự xóa tài nguyên run.
`--probe-images` GET endpoint cùng ASGI app, kiểm MIME/decode/hash, lưu bản ảnh trong output/images để mở xem.
Chỉ mode plan là không tạo client/model; execute thật cần hạ tầng và model cache sẵn.
Report có `response`, `trace`, `checked_build`, `image_checks`, số calls và latency; không đưa expected vào evidence.
Lệnh trên không kiểm browser visual hoặc Discord gateway. Hãy đọc đáp án/nguồn/ảnh trước khi chấm correctness.


Sau run thật 10 lượt, decision có tối đa1 repair với validation feedback cho object đầy đủ/nhận diện được,
trong cùng deadline và budget6 calls (vẫn dành1 call cho generation). Không nới invariant provenance hoặc
bịa clarification thay model. Object sai hoàn toàn và repair thất bại vẫn báo lỗi upstream.
Prompt cũng cấm generator tự phủ nhận gửi ảnh; việc chọn ảnh diễn ra sau text.
Các sửa này mới kiểm offline; [run thật và giới hạn](../testing/2026-11-07_evidence-media-build-10/README.md).
