# True Agent GĐ2 qua API so với baseline — 22/11/2026

TV3 MinhMuc · Nhánh `feature/s5-tv3-true-agent-gd2` (từ `origin/develop` `cb12859`, chưa commit). Quyết định: [ADR 006](../../adr/006-true-agent.md). Baseline: [2026-11-22_baseline-truoc-true-agent](../2026-11-22_baseline-truoc-true-agent/README.md) (cùng 10 câu, cùng cách đo).

## Đã chạy gì

- 14 câu ([manifest.json](manifest.json)) qua ASGI app thật, web SSE `/api/v1/chat/stream`, `.env` thật (PostgreSQL/Qdrant/Redis local, DeepSeek, Jina, Tavily), `web_search=auto`, `lang=auto`, một lượt chạy. Trước đó thử 2 câu (BL-05, MT-2).
- 10 câu baseline + 4 câu mới: MT-1 (build Dexterity level 80, rồi "À nhầm, level 100 nhé"), MT-2 (chia điểm không nêu level → trả lời câu hỏi lại "Level 90, build Faith"), WEB-1 (bản cập nhật mới nhất), WEB-2 (chỗ farm rune level 50).
- Đo giống baseline: thời gian phía client (gồm giữ câu tới khi kiểm xong và chọn ảnh), lượt gọi model từ trace, grounded. Lần này có ghi token đầu vào của Agent (`trace.agent.usage`). Số liệu tổng hợp: [summary.json](summary.json); kết quả thô ở `backend/data/research_runs/2026-11-22-gd2/` (gitignored).

## Kết quả (10 câu baseline)

| Chỉ số | Baseline (pipeline nhiều vai) | GĐ2 (vòng lặp Agent + Generator) |
|---|---|---|
| Trả lời được / grounded | 10/10 / 10/10 | 10/10 / 10/10 |
| p50 / p95 / max | 17,6 / 36,4 / 36,6 s | **16,6 / 29,1 / 35,5 s** |
| Trung bình | 20,3 s | 16,8 s |
| Lượt gọi model / câu (gồm viết và ảnh) | 7,8 (max 11) | **6,0** (max 8) |
| Calculator đạt (2 câu build) | 1/2 | **2/2** |
| Token đầu vào của Agent / câu | chưa đo | 23 nghìn (max 42 nghìn) |
| Vượt 45 s | 0 | 0 |

| ID | Baseline | GĐ2 | Lượt gọi (Agent + viết + ảnh) | Ghi chú |
|---|---:|---:|---|---|
| BL-01 Lore Ranni | 19,3 s | 18,3 s | 3 + 1 + 1 | |
| BL-02 Rivers of Blood | 7,9 s | 9,3 s | 3 + 1 + 1 | |
| BL-03 Mooonveil | 10,2 s | 6,3 s | 3 + 1 + 1 | `check_name` rồi chọn "Moonveil" |
| BL-04 Godfrey | 16,1 s | 17,4 s | 3 + 1 + 1 | |
| BL-05 Build Strength 125 | 36,6 s | 35,5 s | 6 + 1 + 1 | Calculator lỗi 2 lần, Agent tự sửa, lần 3 đạt |
| BL-06 Prisoner 30 + Moonveil | 36,1 s | **15,4 s** | 6 + 1 + 1 | Baseline calculator lỗi; GĐ2 đạt ở lần 2 |
| BL-07 So sánh | 17,8 s | 21,3 s | 5 + 1 + 1 | 4 lần tìm local |
| BL-08 Waterfowl Dance | 30,9 s | 17,0 s | 5 + 1 + 1 | Không cần web |
| BL-09 Quest Ranni | 11,1 s | 16,1 s | 3 + 1 + 1 | |
| BL-10 SotE (EN) | 17,4 s | 11,1 s | 3 + 1 + 1 | |

## Bốn câu mới

| ID | Kết quả | Thời gian | Ghi chú |
|---|---|---:|---|
| MT-1 | 2 lượt, cả hai grounded | 55,0 s tổng (hai lượt) | Lượt 1: tổng 159 (level 80). Lượt 2: Agent ghi đè điều kiện level → **tổng 179 (level 100)** đúng. Lượt 2 có một lần `set_conditions` bị từ chối (sai nguồn) rồi sửa |
| MT-2 | 2 lượt | 1,4 s + 28,6 s | Lượt 1 Agent hỏi level (`ask_user`, 1 lượt gọi). Lượt trả lời: ghi "level 90", calculator đạt ở lần 2 |
| WEB-1 | grounded | 29,1 s | Agent tự tìm web 3 lần (bản vá 1.17) |
| WEB-2 | grounded | 25,6 s | Corpus đủ (Mohgwyn Palace), không đi web |

## Sau khi bỏ chọn đoạn web theo từ khóa và đoán ngôn ngữ (mục 13, 14)

4 câu mới, chưa từng dùng ở lần đo nào ([manifest-muc-13-14.json](manifest-muc-13-14.json)), chạy bằng `scripts/run_live_manifest.py` (lần chạy thật đầu tiên của script này); kết quả thô ở `backend/data/research_runs/2026-11-22-muc-13-14/`.

| ID | Câu | Kết quả | Thời gian | Ghi chú |
|---|---|---|---:|---|
| WEB-3 | Tin tức mới nhất về Elden Ring tháng này | grounded, 3 nguồn web | 20,3 s | 2 lần `search_web`, Agent tự mở khối trang cần đọc (`open_evidence`); bản vá 1.17.2 |
| WEB-4 | Build cộng đồng đánh giá mạnh nhất ở SotE | grounded, web + corpus | 42,1 s | 3 lần web, 3 lần corpus; 5 lượt Agent |
| LANG-EN | "where do i find the black knife armor" | grounded, tiếng Anh | 5,0 s | 1 lần tìm rồi `finish` |
| LANG-VI | "Lam sao de vao duoc Haligtree?" (không dấu) | grounded, **tiếng Việt** | 17,3 s | Hàm đoán theo dấu cũ sẽ chọn tiếng Anh |

## Sau khi sửa câu hỏi về chính cuộc trò chuyện

4 câu mới ([manifest-hoi-thoai.json](manifest-hoi-thoai.json)), chế độ RAM (`CHAT_PERSISTENCE=memory`), kết quả thô ở `backend/data/research_runs/2026-11-22-hoi-thoai/`.

| ID | Hội thoại | Kết quả |
|---|---|---|
| CONV-1 | "Malenia mạnh nhất ở phase nào?" → "Câu hỏi trước của tôi là gì?" | Lượt 2: `reply` (intent `conversation`), trích đúng câu trước và tóm tắt câu đã trả lời, 1,2 s, không tìm kiếm |
| CONV-2 | "Rykard là ai?" → "Tóm tắt lại những gì bạn vừa trả lời" | Lượt 2: `reply`, tóm tắt đúng câu trả lời trước, 2,0 s |
| CONV-3 | "Bloodhound's Fang lấy ở đâu?" → "Vũ khí đó cần bao nhiêu Dexterity?" | Lượt 2: hiểu "vũ khí đó" từ lượt trước, vẫn tìm nguồn, grounded: 17 Dex, Str 18/12 |
| REG-1 | "Starscourge Radahn có điểm yếu gì?" | grounded, 22,7 s (kiểm hồi quy) |

## Chế độ lưu PostgreSQL, có restart giữa hai lượt

Lần đầu chạy thật với `CHAT_PERSISTENCE=postgres` (chế độ production/staging dùng): DB local nâng từ migration 0002 lên 0005, `scripts.memory_admin setup --apply`. Lượt 1 trong một app instance, tắt app, lượt 2 trong app instance mới cùng hội thoại (lịch sử phải đọc từ PostgreSQL). Câu mới, chưa dùng ở lần đo nào; kết quả đọc lại từ DB ở `backend/data/research_runs/2026-11-22-postgres/`.

| ID | Lượt 1 | Lượt 2 (sau restart) | Kết quả |
|---|---|---|---|
| PG-1 | "Godrick the Grafted ở đâu?" (11,7 s, grounded) | "Câu hỏi trước của tôi là gì?" | `reply` intent `conversation`, trích đúng câu trước và câu trả lời, 2,9 s; không lưu thành ký ức chủ đề |
| PG-2 | "Rennala dùng loại phép gì?" (16,2 s, grounded) | "Vậy nên mặc giáp gì để chống phép đó?" | Hiểu "phép đó" là sorcery (Magic), tìm nguồn so sánh giáp kháng Magic, grounded, 24,4 s; ký ức chủ đề lưu theo yêu cầu đã diễn đạt lại |

`tokens_in` lưu trong `messages` gồm cả token của Agent (12,7–42,8 nghìn/lượt). Ký ức ngữ nghĩa trả về 1 ứng viên ở lượt 2 của mỗi hội thoại.

## Build linh động: trả lời trước với giả định rõ ràng

4 câu build mới ([manifest-build-linh-dong.json](manifest-build-linh-dong.json)), chế độ PostgreSQL; kết quả thô ở `backend/data/research_runs/2026-11-22-build-linh-dong/`.

| ID | Câu | Hỏi lại? | Bảng 8 chỉ số | Thời gian | Ghi chú |
|---|---|---|---|---:|---|
| BUILD-1 | "Gợi ý cho mình một build dùng katana" | Không | **Có, đã kiểm** (giả định level 150, class Samurai) | 51,1 s | Ghi chú dưới bảng nêu đúng phần giả định; 2 lần `set_conditions` và 2 lần calculator bị từ chối trước khi đạt |
| BUILD-2 | "Build tank chịu đòn tốt cho PvE" | Không | Không | 30,7 s | Agent tìm 10 lần rồi hết ngân sách trước khi chia điểm; trả lời chọn khiên và lối chơi |
| BUILD-3 | "Mình mới chơi, nên build phép thế nào?" | Không | Không (calculator lỗi 1 lần, hết ngân sách) | 31,2 s | Trả lời định tính có vũ khí cụ thể (Meteorite Staff) |
| BUILD-4 | "Chia lại chính xác 8 chỉ số cho nhân vật Faith của mình giúp" → "level 75, class Confessor" | **Có** (đúng: đòi bảng chính xác) | **Có, đã kiểm** | 1,2 s + 24,8 s | Đúng sàn Confessor |

Không còn câu build nào bị hỏi lại khi người chơi không đòi số chính xác. Còn lại: Agent tiêu nhiều lượt cho tìm kiếm trước khi chia điểm (BUILD-2, 3), và `set_conditions`/calculator hay bị từ chối lần đầu (trace giờ ghi lý do từ chối ở `agent.steps[].error` để chẩn đoán).

## Agent tự tính bằng Python (bỏ calculator và mọi kiểm tra build của server)

4 câu build mới ([manifest-run-python.json](manifest-run-python.json)), chế độ PostgreSQL; kết quả thô ở `backend/data/research_runs/2026-11-22-run-python/`. Tổng và sàn class được tính lại tay để đối chiếu.

| ID | Câu | Bảng 8 chỉ số | Tổng / đúng level + 79 | Sàn class, yêu cầu vũ khí | Thời gian |
|---|---|---|---|---|---:|
| PY-1 | "Gợi ý build Faith cho PvP" | Có (giả định level 150, Prophet, Blasphemous Blade) | 229 ✓ | ✓ | 62,6 s |
| PY-2 | "Build cầm Blasphemous Blade ở level 120" | Có (giả định Vagabond) | 199 ✓ | ✓ (22/15/21) | 23,8 s |
| PY-3 | "Mình là Vagabond level 60, muốn chuyển sang build Dex, chia lại điểm giúp" | Có | 139 ✓ | ✓ | 26,6 s |
| PY-4 | "Build lai Arcane và Faith thì chia điểm sao?" | Có (giả định level 150, Prophet) | 229 ✓ | ✓ | 36,2 s |

4/4 có bảng đúng, không câu nào bị hỏi lại. `run_python` báo `AssertionError` giữa chừng ở PY-1, PY-3: Agent tự đặt kiểm tra trong code, thấy sai thì sửa rồi chạy lại. PY-1 tốn ~80 nghìn token đầu vào và 62 s (nhiều lượt tìm kiếm).

## Sau khi thay 5 rule cứng (#2, #8, #12, #18, #24)

3 câu mới ([manifest-rule-cung.json](manifest-rule-cung.json)), web `auto`, PostgreSQL; kết quả thô ở `backend/data/research_runs/2026-11-22-rule-cung/`.

| ID | Câu | Kết quả | Agent | Thời gian |
|---|---|---|---|---:|
| RC-1 | "Ai lồng tiếng cho Godrick the Grafted bản tiếng Nhật?" | Không grounded, bước viết tự nói "không xác nhận được diễn viên lồng tiếng Nhật" (không còn câu tĩnh của server) | corpus → web (2 lần web timeout) → finish chọn 2 bằng chứng | 30,1 s |
| RC-2 | "Mình hay chết vì bị nhiều kẻ địch vây cùng lúc, có mẹo gì không?" | Grounded, 4 nguồn (đòn quét, AoE đẩy lùi, crowd control) | 4 lần search_corpus, không bật `gameplay_advice` | 20,1 s |
| RC-3 | "Mimic Tear và Black Knife Tiche khác nhau thế nào khi đánh boss?" | Grounded, bảng so sánh, 5 trích dẫn | Agent tự chọn 5 bằng chứng | 17,5 s |

3/3 trả lời đúng định dạng, không lỗi kiểm chứng; trace luôn `evidence_selection.method = model`. Agent luôn tự chọn bằng chứng nên lời nhắc #18 chưa lần nào phải dùng; #2 và #8 cũng không bị kích hoạt trong 3 câu này (chỉ có unit test). RC-2 đúng nguồn nhưng chỉ nói vũ khí/skill, thiếu mẹo chung (kéo từng địch, giữ khoảng cách) vì Agent không bật lời khuyên gameplay. RC-1 chạm trần thời gian chuẩn bị vì web timeout.

## Câu xin mẹo sau khi sửa prompt `gameplay_advice`

Prompt `true_agent.md` thêm: câu xin mẹo/cách xử lý tình huống luôn bật `gameplay_advice`. Trace thêm `agent.gameplay_advice` (chỉ chẩn đoán). Manifest: [manifest-meo-gameplay.json](manifest-meo-gameplay.json), [manifest-meo-gameplay-2.json](manifest-meo-gameplay-2.json).

| ID | Câu | Kết quả | Bước / token đầu vào | Thời gian |
|---|---|---|---|---:|
| MG-1 | "Đánh Crucible Knight cứ bị đòn đuôi quật trúng, nên né thế nào?" | Grounded, mẹo né cụ thể (lăn chéo, chờ cú quét thứ hai) | 12 / 76k | 23,7 s |
| MG-2 | "Chơi build phép mà hay hết FP giữa trận thì xử lý sao?" | Grounded, 5 nguồn (flask, tear, talisman) | 10 / 57k | 20,9 s |
| MG-3 | "Bloodhound Knight Darriwil đánh dồn dập quá, nên phản công lúc nào?" | Grounded, `gameplay_advice=true`, có giới hạn rõ phần nguồn không nêu | 8 / 47k | 38,2 s |

MG-1, MG-2 chạy trước khi trace có cờ nên không biết cờ. Cả 3 câu bước viết vẫn ưu tiên mẹo có trích dẫn, không thêm `recommendation`.

## Đánh giá tổng (22/11)

| Tiêu chí | Trước GĐ2 (baseline) | GĐ2 | Hiện tại |
|---|---|---|---|
| Câu build | calculator đạt 1/2, hay bắt người chơi khai level/class | 2/2 | 4/4 bảng đúng, tự giả định khi thiếu, không hỏi lại |
| Hỏi về chính cuộc hội thoại | trả lời lạc đề | trả lời lạc đề | 6/6 đúng (memory và PostgreSQL) |
| Không có nguồn | câu tĩnh cố định | câu tĩnh cố định | bước viết nói rõ thiếu gì (RC-1) |
| Lượt gọi model / câu (10 câu baseline) | 7,8 | 6,0 | chưa đo lại |
| Thời gian (10 câu baseline) | p50 17,6 s, p95 36,4 s | p50 16,6 s, p95 29,1 s | chưa đo lại; 12 câu mới: trung vị ~23,8 s, cao nhất 62,6 s |
| Token đầu vào Agent | — | — | 15k–80k/câu, cao khi Agent tìm 8–9 lần |

Chất lượng tốt hơn rõ (build linh hoạt và đúng số, nhớ hội thoại, câu thiếu nguồn tự nhiên, ít rule cứng). Chi phí và độ trễ có xu hướng tăng vì Agent tự tìm nhiều lần; 12 câu mới khó hơn bộ baseline nên chưa so trực tiếp được. Muốn so công bằng cần chạy lại đúng 10 câu baseline.

## Nhận xét

- Thời gian đuôi giảm rõ (p95 −20%); câu build không còn bị bảng tham khảo do calculator lỗi (2/2 đạt, Agent đọc lỗi và tự sửa).
- Câu tra cứu thường giữ 5 lượt gọi (3 lượt Agent + viết + ảnh) so với 6–8 trước đây; một số câu không nhanh hơn vì Agent thường mở thêm `open_evidence` trước khi kết thúc.
- Câu build vẫn tốn nhất (6 lượt Agent, ~35 s khi calculator phải sửa 2 lần) — sát hạn 45 s của JSON/Discord.
- Lỗi JSON tham số (`invalid_tool_calls`) xuất hiện 1 lần (MT-1) và được trả lời đúng, vòng lặp chạy tiếp.

## Hạn chế

- Một lượt chạy, 14 câu: so sánh thô, độ trễ dao động theo mạng/provider. Baseline chưa ghi token nên chưa so được chi phí.
- Chưa đo kênh Discord/JSON (hạn 45 s), chưa có câu nhiều hơn 2 lượt hội thoại, chưa chấm chất lượng theo golden set (mới đọc tay vài câu).

## Chạy lại

Hướng dẫn, chưa tự chạy thêm (gọi API thật, tốn phí; cần PostgreSQL/Qdrant/Redis, `.env` với `CHAT_MODE=rag`). Từ `D:\Index-Beastackend`:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.run_live_manifest ../docs/testing/2026-11-22_true-agent-gd2/manifest.json data/research_runs/gd2-moi
```

`scripts/run_live_manifest.py` là bản gọn của runner đã dùng cho lần đo 14 câu (cùng cách gửi lượt hỏi lại và tin nhắn nối tiếp); đã chạy thật với 4 câu mục 13, 14 ở trên.
