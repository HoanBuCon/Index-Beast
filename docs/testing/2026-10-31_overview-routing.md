# Câu hỏi tổng quan trong IndexBeast

31/10/2026 · TV3 — MinhMuc · nhánh `feature/s2-tv3-overview-routing`.

## Vấn đề và thay đổi

Luồng cũ dùng query entity retrieval cho cả câu hỏi rộng, top-5 không ưu tiên nguồn tổng quan.
Rewrite có thể yêu cầu làm rõ vì không có entity cụ thể, dù câu “các boss trong elden ring” đã có topic rõ.
Nhánh thiếu context cũng mặc định hỏi tên nhân vật/trang bị/boss/nhiệm vụ.

Đã thêm routing overview deterministic cho các cue tổng quan/danh sách/phân loại VI/EN và chủ đề
bosses, weapons, armor, characters/NPCs, locations, quests, builds, lore/game. Có hỗ trợ các chủ đề kết hợp.
Names guard bảo thủ giữ câu có tên riêng về luồng entity; đại từ không có referent vẫn hỏi lại.
Ngoài phạm vi/instruction injection vẫn được gate trước routing. Heuristic có thể bỏ sót cách diễn đạt hoặc
tên viết thường; không chứng nhận hiểu mọi ý định bằng regex.

### Retrieval có giới hạn

- Overview có topic rõ nên không gọi model rewrite; giữ nguyên câu hỏi/điều kiện và thêm một query có cue tiếng Anh.
- Không dịch/gán tên riêng, không thêm facts vào question/evidence. Cues chỉ hướng search, không được đưa vào context làm nguồn.
- Tối đa 2 query, kể cả khi query mode là dual; không thêm query thứ 3. Giữ await budget retrieval đang cấu hình,
  chia đều theo query và giữ max rag_prefetch ứng viên/fusion, context tối đa top-5.
- Dùng rank fusion và content/ID dedup hiện có. Ưu tiên title trang overview, rồi section intro/overview/list/type/category;
  xen kẽ các nhóm source/section để bớt chiếm context bởi cùng một section.
- Metadata preference không phải cross-encoder reranking hoặc bằng chứng relevance. Không hard-filter chỉ còn trang overview:
  khi thiếu trang tổng quan, vẫn có thể dùng bằng chứng từ các trang riêng lẻ.

### Generation

Prompt bổ sung yêu cầu trả overview có grouping/ví dụ được nguồn hỗ trợ; không đòi người dùng chọn một entity trước.
Không từ chối chỉ vì không liệt kê được toàn bộ. Khi có phần hữu ích, trả phần đó cùng citation và nói rõ giới hạn.
Khi không có phần nào đủ evidence, giữ insufficient contract hoặc thông báo thiếu context, hỏi cách thu hẹp chủ đề
thay vì bắt nêu tên nhân vật. Không tự bịa loại build, nhóm vũ khí, số lượng hoặc danh sách hoàn chỉnh.

Giữ JSON schema, citation/quote validation, format/protocol recovery, nguồn/ảnh từ metadata server,
VI/EN, release/continuity/unknown, spoilers và ba mode. Không fallback llm_only hoặc search web tự động.
Không đổi API JSON/SSE/conversation/feedback, rate limit/token guard/timeout của TV1 hoặc persistence.

## Đối chiếu dữ liệu chỉ đọc

Trong artifact EN local có các title: Bosses, Weapons, Armor, Locations, NPCs, Characters.
Ví dụ Bosses có Introduction/Overview/Mandatory bosses/Remembrance Bosses; NPCs có List of All NPCs.
Không tìm thấy title khớp chính xác Builds/Classes/Quests/Elden Ring trong lần census title này;
không suy ra toàn bộ thông tin tương ứng vắng mặt ở các trang khác.

[Mẫu sắp xếp metadata](2026-10-31_overview-ordering.json) lấy chunk thực từ artifact:
sequence thủ công ban đầu Letter for Freyja → Bosses Introduction → Bosses Overview → Elden Beast → Maliketh;
sau preference, hai chunk Bosses lên trước. IDs và toàn bộ payload giữ nguyên.
Đây là mẫu ordering đọc artifact local, không phải replay retrieval thật hoặc phép đo chất lượng model.
Không chạy encoder/model/Qdrant/DeepSeek, không sửa raw/clean/chunks hoặc tạo index trong lượt này.

## Kiểm tra thực tế

Baseline: **483 passed, 1 warning**, 21,31 giây.
Sau sửa: **523 passed, 1 warning**, 18,42 giây; thêm 40 case overview/benchmark budget.
Warning Qdrant memory không thực thi payload index là dự kiến. Không dùng thời gian pytest làm benchmark retrieval.

Test mới kiểm tra:

- Câu rộng VI/EN, có/không dấu, lore/game, nhiều category và DLC.
- Câu có tên riêng, comparison, acquisition hoặc đại từ giữ luồng entity.
- Không gọi paid rewrite cho overview, hai query giữ nguyên điều kiện, context top-5 và ngôn ngữ trả lời.
- Ưu tiên title/section, metadata và image association không bị đổi; review rejection/spoilers vẫn được lọc.
- Thiếu context không đòi entity; lỗi retrieval vẫn unavailable, không chuyển thành thiếu dữ liệu.
- Partial overview có citation qua API JSON/SSE; scope/injection, disable flag và llm_only.
- Plan-only benchmark không đánh giá thiếu số truy vấn khi input có overview.

Lệnh đã chạy từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q --tb=short
.venv/Scripts/python.exe -m ruff check app/rag/overview.py app/rag/pipeline.py core/config.py scripts/benchmark_vi_en.py tests/unit/test_overview.py
.venv/Scripts/python.exe -m ruff format --check app/rag/overview.py app/rag/pipeline.py core/config.py scripts/benchmark_vi_en.py tests/unit/test_overview.py
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_vi_en --strategies original rewrite dual
```

Lint/format, OpenAPI, dependencies đạt. Plan-only bộ VI–EN cũ vẫn 13 cặp/78 dòng, upper bound 104 retrieval query,
không client/model hoặc API call; custom overview cases được tính tối đa 2 query mỗi dòng.
Không chạy benchmark thật, không có điểm recall/correctness hoặc đánh giá ngữ nghĩa mới.

## Cách thử — người dùng tự thực hiện

Flag `RAG_OVERVIEW_ENABLED` mặc định true, .env.example/Compose đã đồng bộ; không sửa .env thật.
Nếu worker chưa reload, restart bằng `make api` từ gốc và tạo chat mới sau restart. Không cần reindex.
Các câu thử:

- “các boss trong elden ring”
- “Các loại vũ khí trong Elden Ring là gì?”
- “Những nhóm nhân vật trong Elden Ring”
- “Tổng quan cốt truyện Elden Ring”
- “Những kiểu build phổ biến là gì?”

Câu hỏi thật vẫn gọi generation và query embedding như ứng dụng bình thường. Routing không thêm LLM call,
nhưng có thể thêm một query embedding/Qdrant so với luồng một query trước đây. Tổng context không tăng.
App trace có request_kind=overview, overview_topic, context_ordering và số query; raw query chỉ opt-in ở diagnostic.

Đặt `RAG_OVERVIEW_ENABLED=false` trong cấu hình của người dùng rồi restart nếu muốn so sánh/tắt tính năng.
Muốn benchmark VI–EN riêng tác dụng rewrite thì tắt flag này cho phiên benchmark; report ghi overview_enabled.
Corpus thiếu mechanics/build/acquisition vẫn cần công việc dữ liệu riêng. Code mới chưa làm RAG thành công cụ
liệt kê hết toàn corpus hoặc bảo đảm mọi câu tổng quan đều trả lời đầy đủ.
