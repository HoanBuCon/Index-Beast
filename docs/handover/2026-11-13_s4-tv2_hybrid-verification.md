# TV2 Sprint 4 · Kiểm chứng Qdrant hybrid

Cập nhật cho [bàn giao dữ liệu Sprint 4](2026-11-12_s4-tv2_wiki-quality.md) sau khi [PR #95](https://github.com/HoanBuCon/Index-Beast/pull/95) vào develop. Dùng cùng corpus và chính sách `pilot` / `en` của bản S4. Môi trường test dùng Qdrant server qua HTTP ở `127.0.0.1:16333`, collection riêng `s4_tv2_wiki_hybrid`, volume riêng `index-beast-s4-tv2-qdrant`. PostgreSQL và Redis phản hồi kiểm tra kết nối. Dùng E5 đã có và cache BM25 mới, cùng class encoder, schema, store và retriever của dự án.

## Kết quả đã chạy

- Re-index đủ 34.070 chunk EN trong 642,38 giây. Qdrant xác nhận cả 34.070 point có hai vector `dense` và `bm25`, cùng payload index `game_scope` và `spoiler_level`.
- Bộ lọc `spoilers=false` trả đúng tập 33 ID mức 0 so với artifact. Ba truy vấn kiểm thử qua retriever và bước chọn ngữ cảnh chỉ trả mức 0. Truy vấn ending của Ranni loại cả 30 ứng viên mức cao từ lần bật spoiler.
- Chạy 25 câu gốc qua hybrid retriever. 20/22 câu có URL kỳ vọng xuất hiện đúng trang ở top 5. Hai câu 091 và 092 trỏ tới trang stats trên Wikidot ngoài cohort. Ba câu hành vi không có URL kỳ vọng.
- Sáu truy vấn đối chiếu đoạn bằng chứng đều đạt top 2. Fingerslayer Blade ở hạng 1, Discarded Palace Key hạng 2. Đây là hạng ứng viên hybrid theo truy vấn đối chiếu, tách với hạng FTS5/E5 ở lần trước.
- Report local gồm `data/research_runs/s4-wiki-hybrid/hybrid-index.json`, `hybrid-retrieval-eval.json` và `api-preflight.json` trong cùng thư mục. Kết quả retrieval và kết quả API được lưu riêng.

## Chạy lại

Từ `backend/` trên Windows, đặt biến cho tiến trình PowerShell. Dùng tên collection mới nếu tái lập từ đầu. Lệnh index chuẩn xử lý toàn bộ tập EN, đọc cache local và cần Qdrant đã chạy.

```powershell
$env:QDRANT_HOST = '127.0.0.1'
$env:QDRANT_PORT = '16333'
$env:RAG_MODELS_DIR = Join-Path $env:USERPROFILE '.cache/huggingface/hub'
$env:RAG_CORPUS_POLICY = 'pilot'
$env:RAG_LANGUAGES = 'en'
$env:HF_HUB_OFFLINE = '1'
$env:RAG_COLLECTION = 's4_tv2_wiki_hybrid'
.venv/Scripts/python.exe -X utf8 -m ingest index --input data/chunk_runs/s4-wiki-release/chunks.jsonl --policy pilot --languages en --collection $env:RAG_COLLECTION
```

Lượt ngày 13/11 dùng script local `data/research_runs/s4-wiki-hybrid-index.py` để sắp chunk theo token, in tiến độ và tiếp tục từ ID đã ghi. Dùng `data/research_runs/s4-wiki-hybrid-eval.py` để kiểm vector, bộ lọc và eval retrieval. Chạy lại từ cùng thư mục bằng `Get-Content -Encoding utf8 data/research_runs/s4-wiki-hybrid-eval.py | .venv/Scripts/python.exe -X utf8 -`.

## Eval qua API

Đặt `DEEPSEEK_API_KEY` và `TAVILY_API_KEY` trong file `.env` local ở gốc repo. Git bỏ qua file này.

Đã chạy đủ 25 câu trên `POST /api/v1/chat` qua ASGI test. Cả 25 lượt trả HTTP 200, so với 24/25 ở baseline. IB-GS-086 từng trả 502, lần này có câu trả lời kèm nguồn Maliketh và Leyndell. Đọc trực tiếp IB-GS-075 và IB-GS-052 cho thấy vị trí rương Fingerslayer Blade và điều kiện lấy Discarded Palace Key có trích dẫn đúng phần nhiệm vụ. IB-GS-019 nêu đúng cha mẹ và quan hệ anh em nhưng bỏ chi tiết Radahn là anh của Ranni trong kỳ vọng. Chưa có điểm chấm độc lập cho toàn bộ câu trả lời.

Report tại `backend/data/research_runs/s4-wiki-hybrid/api-rerun/report.json`. Ghi nhận 93 lượt gọi model logic, 519.450 input token, 12.857 output token và 0 lượt gọi Tavily. Corpus giữ 34.070 điểm trước và sau. Cùng 25 câu và DeepSeek Flash với baseline, nhưng giới hạn output 2.048 thay cho 4.096 và thinking tắt thay vì bật. Không dùng thay đổi HTTP để quy kết tác động riêng của dữ liệu. Preflight ban đầu dừng ở chế độ mặc định mock trước khi gọi model. Tiếp tục đúng lượt với `CHAT_MODE=rag` ở phạm vi tiến trình test.

Runner yêu cầu DeepSeek và Tavily đã cấu hình, Qdrant có corpus, PostgreSQL và Redis. Lượt đã ghi dùng runner tại `09a21ee` với trần 6 lượt gọi model logic mỗi câu. Runner trên develop có thể dùng ngân sách khác. Kiểm tra ngân sách trước khi chạy lại với API thật.

```powershell
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '15432'
$env:REDIS_HOST = '127.0.0.1'
$env:REDIS_PORT = '16379'
$env:CHAT_MODE = 'rag'
$env:WEB_SEARCH_ENABLED = 'true'
$env:WEB_SEARCH_MODE = 'auto'
$env:LLM_MODEL = 'deepseek-flash'
$env:LLM_MAX_TOKENS = '2048'
$env:RAG_THINKING_ENABLED = 'false'
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest data/research_runs/s4-wiki-hybrid/api-golden-25-manifest.json --max-turns 25 --execute --allow-llm --allow-web --allow-embedding --output data/research_runs/s4-wiki-hybrid/api-replay
```

Manifest eval local lấy nguyên văn từ [baseline ngày 09/11](../testing/2026-11-09_golden-25-by-difficulty/report.json). Kết quả chạy qua retriever đo hạng trang nguồn và đoạn bằng chứng, còn eval API đánh giá thêm câu trả lời và nguồn thực tế.

## Kiểm thử

116 test liên quan pass. Một cảnh báo từ Qdrant nhúng trong unit test về chỉ mục payload, còn môi trường thử nghiệm dùng Qdrant server. Đã cài các dependency khóa sẵn trong venv dự án và `uv pip check` đạt.
