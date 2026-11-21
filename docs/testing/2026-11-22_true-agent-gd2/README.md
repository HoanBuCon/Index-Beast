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
