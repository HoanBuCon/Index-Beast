# TV3 — Evidence, ảnh và build có nguồn

- Ngày: 07/11/2026, Asia/Saigon.
- Chủ sở hữu: TV3 MinhMuc, IndexBeast / 4 Hollows.
- Nhánh: `feature/s3-tv3-evidence-media-build`, tách từ `develop` sạch.
- Không commit/push/merge hoặc sửa Trello/đánh dấu Done. Handover được người dùng cho phép trực tiếp.

## Phạm vi và nguyên nhân

Trước sửa, tool planner đã chọn tool bằng model nhưng context cuối vẫn đi qua `coverage_order` quest/stat keyword.
Ảnh chỉ resolve exact-section local, không có model chọn chủ thể hoặc pipeline cache ảnh web. Calculator/protocol
chủ yếu xác minh Samurai/Moonveil theo4 snapshot; không truyền một generic checked artifact đến generator.

Đã triển khai evidence IDs do model chọn; ảnh metadata-based local/web; nguồn numerical có kiểu và calculator
nhiều class/weapon; bounded decision repair sau chẩn đoán thật. Giữ auth/filter/schema/citation/calculation/budget
ở backend. Legacy còn caller/config nên giữ nguyên đường compatibility, không xóa hàng loạt.

## File và contract

- `backend/app/rag/tool_agent.py`, `pipeline.py`, `prompts/tools.md`: candidate preview/metadata, finish evidence_ids,
  context không keyword trên đường tool-agent; fallback rank có trace; giữ original IDs qua merge/dedup.
- `backend/app/rag/build_data.py`: Number/Rule/BuildData/CheckedBuild; label-value và aligned-table binding,
  provenance, floor/cap/requirements/tổng, hash version; cache factual input RAM32 entry/1h, không lưu profile.
- `backend/app/rag/generator.py`, `prompts/answer.md`: artifact nguyên vẹn đến generator, revalidate/hash/citation
  đúng quote số học, server render8 stat; không cho model thay bảng hoặc tự tuyên bố không gửi được ảnh.
- `backend/app/adapters/tavily.py`: flags ảnh Search và `results[i].images`, bỏ global images chưa liên kết.
- `backend/app/services/answer_media.py`: model chỉ chọn ID; exact_section/entity_page/web_result; HTTPS allowlist,
  DNS public/IP pinning/TLS, không redirect, giới hạn byte/pixel/time, decode/hash/atomic cache.
- `backend/app/services/images.py`, `chat.py`: phục vụ blob web qua endpoint hash cũ, resolver optional có deadline
  trong thời gian request còn lại; hỏng ảnh không làm hỏng text. `.gitignore` bỏ `backend/.cache/`.
- `backend/app/api/schemas/chat.py`, `docs/api/openapi.json`: chỉ thêm `association` tùy chọn cho ChatImage.
- `backend/app/rag/agent.py`, `prompts/agent.md`: sửa decision tối đa1 lần khi object nhận diện được vi phạm schema/
  provenance; deadline và global6 calls không tăng. Object sai hoàn toàn vẫn lỗi, không bịa fallback thành công.
- `backend/scripts/benchmark_agent.py`, `diagnose_agent_memory.py`: mode từng case, probe ảnh, checked_build report,
  giữ opt-in execute, isolated resources và checkpoint/resume không replay.
- Tests: `test_build_data.py`, `test_answer_media.py`, `test_agent_media_regressions.py`, cập nhật `test_tool_agent.py`,
  `test_web_search.py`; fixture3 decision thật ở `backend/tests/fixtures/agent_media_decisions.json`.
- Manifest mới: `backend/eval/evidence_media_build_10.json` (không sửa golden set).

Contract chi tiết và kiểm kê model/rule: [evidence-media-build](../api/evidence-media-build.md).
Runtime vẫn LangGraph điều phối + LangChain model/retriever. RRF/filter/top5/E5/schema collection không đổi.
Source URLs lấy từ server metadata; validation quote/citation không chứng minh semantic entailment.
Unknown game/release/patch/license giữ unknown; runtime extraction không tự được human approval.
Generic calculator hỗ trợ một tay/không bonus, không AR/DPS/soft caps/optimum. Không có danh sách class/weapon đóng.

## Kiểm tra đã chạy

Từ `backend`, đúng cấu hình:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
```

- Baseline: **817 passed**, 2 warning cũ, 28,81s.
- Trước run thật: **889 passed**, 2 warning cũ, 29,78s.
- Sau sửa run: **915 passed**, 2 warning cũ, 28,52s.
- Ruff lint/format, pip check và OpenAPI check đạt.
- Từ `web`: `npm test` **41 passed**; `npm run typecheck` và `npm run build` đạt.
- Unit dùng synthetic source/vector/fake model/HTTP; không dùng kết quả đó để tuyên bố recall hoặc factual accuracy.

Đã chạy plan rồi đúng1 execute:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/evidence_media_build_10.json --max-turns 10 --probe-images
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/evidence_media_build_10.json --max-turns 10 --probe-images --execute --allow-llm --allow-web --allow-embedding --output ../docs/testing/2026-11-07_evidence-media-build-10
```

**Hoàn tất10/10**, 7 HTTP200 + 3 HTTP502, 39 model calls, 2 Tavily Search + 2 Extract, retry0.
Corpus trước/sau18.368 point. Dùng DB/memory collection test riêng, giữ tài nguyên/report, không đổi `.env` thật,
không tải model/crawl/reindex. Encoder dùng cache và cờ offline-download.
Tất cả12 image entries GET200/MIME/decode/hash đúng; đã mở10 blob độc nhất. Không browser visual QA.

[Report chi tiết](../testing/2026-11-07_evidence-media-build-10/README.md),
[raw report](../testing/2026-11-07_evidence-media-build-10/report.json),
[nhận xét](../testing/2026-11-07_evidence-media-build-10/review.json).

## Kết luận và giới hạn phải giữ khi demo

**Chưa được nói build tổng quát hoặc ảnh web đã đạt live.** Run có0 generic checked_build và0 ảnh web được xác minh.
Ảnh local đúng chủ thể trong tập đã mở, nhưng nhiều kích thước trùng; text generator phủ nhận gửi ảnh dù images[] có.
Ba502 nằm ở quyết định model: constraint bị dịch,3 missing fields, query mất entity/phủ định.
Các sửa sau run được kiểm offline bằng replay + scripted corrected decision, chưa retest API để giữ trần10 lượt.
Model có thể vẫn không tìm đủ factual data trong budget; thiếu dữ liệu phải trả phần có bằng chứng, không bịa bảng.

Cache factual build chỉ RAM1h, restart mất cache; đây không phải memory conversation. Ảnh web cache trên đĩa,
7 ngày/128MiB dọn khi download thành công; DNS chịu resolver OS, optional timeout bảo vệ text nhưng không cưỡng chế
kết thúc thread OS đang resolve. Header/quote checks không tự chứng minh dữ liệu trích đúng nghĩa/đủ requirements.
Metadata-only không chứng minh pixel, patch mới nhất hay license. Không gọi VLM; có thể thử sau bằng tập ảnh khó,
không dùng sự tự tin của VLM thay nguồn, phép tính hay giấy phép.

## Chạy tiếp cho người nhận

Restart backend để nạp prompt mới (`make api`, hoặc `make dev` nếu chạy cảweb; dừng process cũ trước).
Điều kiện agent: CHAT_MODE=rag, CHAT_AGENT_ENABLED=true, CHAT_TOOL_AGENT_ENABLED=true; không tự sửa `.env` trong tác vụ.
TV4 dùng images[] JSON/SSE hiện có; association là trường optional mới, không cần thay asset/giao diện để gọi API.
Lệnh execute MỚI, resume và cách đọc ảnh/report nằm trong [hướng dẫn](../api/evidence-media-build.md#tự-kiểm-thử).
Các lệnh mới đó **chỉ hướng dẫn**, chưa chạy thêm. Không tự gửi lượt11 trong run đã kết thúc.


## Bổ sung kế hoạch khi phiên sắp chạm giới hạn — 07/11/2026

Đã lưu [kế hoạch tiếp tục](../ke-hoach-on-dinh-indexbeast.md): P0 decision/clarification,
P1 factual build inputs, P2 ảnh từ Tavily Extract theo trang nguồn, P3 tối ưu token/demo.
Có gate và đề xuất8 lượt thật cho đợt SAU; chưa được cấp/chạy trong tác vụ lập kế hoạch.
Chỉ thêm tài liệu, kiểm link/UTF-8/Git; không chạy lại model/unit suite, không sửa runtime/.env,
không commit/push/merge. Prompt tiếp tục nằm cuối kế hoạch để dùng sang phiên mới.
