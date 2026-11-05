# Setup và chẩn đoán thật 20 lượt — 06/11/2026

TV3 — MinhMuc · IndexBeast / 4 Hollows.

## Kết quả thực thi

**Đã hoàn tất đúng 20 lượt**, exit 0, report `status=complete`, `attempted_turns=20`.
Không bị ngắt giữa chừng; không gửi lượt 21, không retest API sau sửa code.
8 câu độc lập từ golden set + 4 hội thoại × 3 lượt, tổng 10 VI / 10 EN.
Đây là development diagnostic, chưa có review chéo độc lập và không đại diện accuracy toàn golden set.

- [Raw report: câu hỏi, đáp án, source excerpt, trace và model output](report.json).
- [Kiểm tra PostgreSQL/Qdrant sau khi chạy](resource-verification.json).
- [Setup local DB và memory collection](../2026-11-06_memory-setup.json).
- [Manifest cố định](../../../backend/eval/agent_memory_20.json).
- [Preflight lần trước bị chặn, 0 lượt](../2026-11-06_agent-memory-20/README.md).

Raw report giữ nguyên sau run; `manual_correctness` và `manual_faithfulness` vẫn `null`.
Nhận xét bên dưới do trợ lý đọc đáp án và đoạn trích đã lưu, **chưa phải chấm của con người**.
Không đưa expected_answer vào prompt làm evidence.

## Hạ tầng và cấu hình thật

App DB `indexbeast` trước setup không có bảng; đã chạy migration 0001 → 0002 và tạo collection
`conversation_memories`: dense 384 cosine, 5 keyword indexes, 0 point. Không ghi corpus.
Settings thực tế vẫn `CHAT_PERSISTENCE=memory`; `.env` không bị sửa. Setup không tự bật persistence cho app.

Run dùng PostgreSQL **`indexbeast_agent_test_70e67916e0`** và collection
**`ib_agent_test_70e67916e0`** riêng. Đã xác minh sau run:

| Kiểm tra | Kết quả |
|---|---:|
| Revision DB test | 0002 |
| Conversations / runtime | 12 / 12 |
| Messages | 40 |
| Memory rows | 22: 21 active, 1 superseded |
| Active memory chưa index revision mới nhất | 0 |
| Point collection memory test | 21 |
| Point corpus trước / sau | 18.368 / 18.368 |

Collection corpus: `indexbeast_tv3_integration_20261029_c1871afc`. Main DB vẫn có 0 conversation/message;
documents/chunks SQL đang rỗng từ trước, không phải bị xóa bởi setup. Corpus hiện hữu nằm ở Qdrant.
Không drop DB/collection test; dữ liệu chẩn đoán được giữ lại. Không index lại corpus hoặc tải weights.

DeepSeek thực tế theo settings: `deepseek-flash`, temperature 0,2, max output 4096,
RAG thinking enabled; decision/assessment có cấu hình riêng trong code.
E5 ONNX chạy từ cache với HF offline. Tavily mode `auto`, không phải always.
Transport là in-process ASGI HTTP với provider/model/tool thật; một lượt SSE.
Tạo lại service kiểm tra restore từ PG, **không phải reboot Windows**.
ASGI có buffering: chưa chứng minh độ trễ token qua mạng, browser/Discord hoặc hiệu năng nhiều người dùng.

## Số liệu

| Chỉ số | Kết quả |
|---|---:|
| HTTP 200 | 20/20 |
| Agent retrieve / clarify / refuse | 14 / 4 / 1 |
| Decision invalid → hỏi lại dự phòng | 1 |
| Response grounded=true | 13 |
| Retrieval trả insufficient sau khi tìm web | 1 |
| Local sufficient / gọi web | 9 / 5 lượt |
| Logical model calls | 48: 20 decision, 14 assessment, 14 generation |
| Tavily requests | 10: 5 Search + 5 Extract |
| Prompt / completion token đã biết | 132.372 / 14.450 |
| Call chưa có usage | 1, SSE |
| Latency min / median / p95 / max | 1,13 / 4,27 / 19,39 / 28,10 giây |

p95 dùng nearest-rank trên 20 latency client, gồm toàn bộ xử lý turn trong ASGI; không phải riêng Qdrant.
Tổng latency các turn 141,41 giây, không bao gồm mọi chi phí startup/preflight. Token chưa đủ để tính tổng tiền
chính xác; không tự áp bảng giá hoặc coi thiếu usage là 0. Không có generation repair trong run này.
HTTP thành công và `grounded=true` chỉ là trạng thái kỹ thuật, không chứng minh entailment hay đáp án đúng.

## Nhận xét từng lượt

| ID | Nhận xét sau đọc đáp án và evidence |
|---|---|
| IB-GS-001 | Blaidd/Ranni: trả đúng trọng tâm, các ý chính có trong quote; hơi dài. |
| IB-GS-041 | Flame, Cleanse Me: phân biệt giảm buildup và chữa poison/rot, có item quote tương ứng. |
| IB-GS-091 | Tính tổng 179 đúng theo quy tắc cộng level + 79 đã cấp. |
| IB-GS-096 | Hỏi katana/stats/upgrade thay vì bịa exact AR/DPS. Cách nói “để tính chính xác” dễ hứa quá khả năng: chưa có damage calculator/latest-patch coverage. |
| IB-GS-005 | Trả Hoarah Loux; hai đoạn nguồn hỗ trợ tên và danh hiệu. |
| IB-GS-047 | Buffable và Bloodflame Blade có trong wiki note đã cấp; không chứng minh đây là buff tối ưu mọi build. |
| IB-GS-086 | **Lỗi guard:** câu hỏi Maliketh rõ ràng nhưng bị invalid_decision, hỏi lại chung chung; không retrieval. Sửa offline bên dưới. |
| IB-GS-100 | Từ chối yêu cầu đánh cắp API key, không tìm web/game nguồn giả. |
| VI-FAMILY:1 | Có cây gia phả và phân biệt SotE, nhưng “half-brother” bị cụ thể hóa thành “cùng cha khác mẹ” khi quote không xác định phía cha/mẹ. Cách gộp đoạn các con cũng dễ gây hiểu lầm cha của Messmer. |
| VI-FAMILY:2 | Chuyển sang Ranni, không chọn ký ức Marika một cách máy móc. Các quan hệ chính có nguồn. |
| VI-FAMILY:3 | Sau recreate service, recall đúng Marika thay vì nhân vật Ranni ở lượt gần nhất; giữ Melina là suy đoán khi nguồn nêu speculation. Lặp nhiều nội dung đã nói, chưa thực sự mở rộng gia phả sâu. |
| VI-BUILD:1 | Hỏi starting class phù hợp mục tiêu chia điểm level 100; lưu pending. |
| VI-BUILD:2 | Sau recreate, nhận Samurai/PvE, resolve đúng Moonveil level 100. Chỉ trả yêu cầu vũ khí/hướng Int và báo thiếu stat nền; **chưa đáp ứng bảng phân bổ tám chỉ số** dù đã search web. |
| VI-BUILD:3 | Correction nhận đúng level 120, memory level cũ bị supersede. Vẫn không ra bảng stat vì thiếu evidence. |
| EN-QUEST:1 | Lộ trình tiếp quest Ranni khớp đoạn walkthrough đã cấp; trả cả nhiều bước sau, có thể dài/spoil hơn yêu cầu “next”. |
| EN-QUEST:2 | Hỏi “it” là item nào, không tự đoán từ một loạt item trong câu trả lời trước. |
| EN-QUEST:3 | Acquisition Carian Inverted Statue đúng quote, nhưng **báo xung đột sai**: nhận từ Ranni và dùng trong quest Fia hoàn toàn có thể đồng thời đúng. Validator citation không chặn lỗi suy luận này. |
| EN-ROUTE:1 | Hỏi vị trí hiện tại và mục tiêu thay vì áp một walkthrough cố định. |
| EN-ROUTE:2 | SSE hoàn tất, đưa đường Ruin-Strewn Precipice có evidence. Tuy nhiên nhắc lift “defunct” theo lời thoại như trạng thái vận hành chung mà không giải thích điều kiện; chưa trình bày đủ lựa chọn/điều kiện Dectus. Không gọi đây là route đầy đủ. |
| EN-ROUTE:3 | Đổi chủ đề sang Great Stars sạch, không kéo route cũ. Web Search/Extract thành công nhưng đáp án vẫn insufficient: **tool chạy được chưa có nghĩa đã lấy đúng đoạn acquisition**. |

Không tính một “accuracy” từ bảng này. Kết quả cho thấy persistence/recall/correction đã chạy thật,
nhưng build, coverage acquisition, diễn giải quan hệ và đánh giá mâu thuẫn vẫn còn hạn chế.
Không thể suy ra semantic recall@k hay VI–EN retrieval parity từ bộ này: chưa có nhãn relevant-memory/chunk đầy đủ,
và không phải 10 cặp VI–EN song song.

## Lỗi guard đã sửa sau run, chỉ kiểm thử offline

IB-GS-086 có decision `rewrite=false`, `resolved_question` giữ nguyên user question,
entities gồm `Maliketh`, `Leyndell, Ashen Capital`. `search_query` không được dùng lại bỏ dấu phẩy của tên thành phố.
Guard cũ kiểm cả query không dùng, nên báo `Entity has no supplied user provenance` và chặn nhầm.

Sửa [agent.py](../../../backend/app/rag/agent.py): khi rewrite=false chỉ kiểm query thực sự dùng
(resolved question bắt buộc bằng câu gốc). Khi rewrite=true vẫn kiểm cả search và resolved query.
Entity phải có provenance trong user memory/current question ở cả hai chế độ; không bỏ kiểm nguồn/số/goal.
Regression [test_agent_durable.py](../../../backend/tests/unit/test_agent_durable.py) replay decision đã quan sát,
assert retriever nhận câu gốc, đồng thời giữ test chặn entity bịa ở cả rewrite true/false.

Full unit sau sửa: **774 passed, 2 warnings, 25,96 giây** (trước tác vụ 771 passed).
Ruff check, Ruff format check 214 file, `pip check`, OpenAPI `--check`: đạt.
Hai warning: payload index không áp dụng trong Qdrant memory fixture và Alembic path_separator deprecated.
Không bỏ assertion để che lỗi. Raw live vẫn giữ đúng lỗi ban đầu; **chưa xác minh lại fix bằng DeepSeek thật**.

## Lệnh đã chạy và bước người dùng tự chạy

Đã chạy từ `backend/`:

```powershell
.venv/Scripts/python.exe -X utf8 -m alembic upgrade head
.venv/Scripts/python.exe -X utf8 -m scripts.memory_admin setup --apply
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_agent_memory --execute --allow-llm --allow-web --allow-embedding --output ../docs/testing/2026-11-06_agent-memory-20-live
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
```

Để app đang dùng chuyển sang persistence đã setup, **chưa chạy thay người dùng**, từ gốc project:

```powershell
$env:CHAT_PERSISTENCE = "postgres"
make dev
```

Restart server cũ trước, tạo conversation mới; browser phải giữ conversation_token. Đây là process override,
không sửa `.env`. Muốn lưu cấu hình qua terminal khác thì người dùng đặt `CHAT_PERSISTENCE=postgres` trong `.env`.
Không cần reindex corpus; RAM history cũ không tự chuyển vào PostgreSQL.
Không tự commit/push/merge hoặc đánh dấu task Done.
