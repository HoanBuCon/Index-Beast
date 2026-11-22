# Khung xương chi tiết — Báo cáo Index Beast (Agentic RAG)

> **Cách dùng file này.** Đây là dàn ý để viết báo cáo. Mỗi mục gồm: nội dung cần viết, hình/bảng dự kiến (đánh số
> theo chương), PI của biểu mẫu H12 mà mục đó đáp ứng, và file trong repo để lấy số liệu/minh chứng.
> Trình bày theo báo cáo mẫu môn Học sâu (`Ban3_ToanBo_Freeze`): phần đầu đánh số La Mã, mỗi chương mở bằng một đoạn
> giới thiệu nêu các mục của chương, bảng số liệu sinh bằng script từ file kết quả, Kết luận chia 4 phần cố định,
> Phụ lục có tổ chức mã nguồn và hướng dẫn tái lập.
>
> Bố cục chương theo H12 (4 chương). Bảng ánh xạ CLO/PI: [khung-bao-cao-agentic-rag.md](khung-bao-cao-agentic-rag.md).
>
> Ký hiệu: 📊 bảng · 🖼️ hình · 📐 công thức · 📁 nguồn số liệu · 🎯 PI đáp ứng.

---

## Phần đầu (đánh số trang La Mã)

### Trang bìa
- Tên trường, khoa, học phần, logo.
- Tên đề tài (ngắt dòng như mẫu): **XÂY DỰNG TRỢ LÝ HỎI ĐÁP ELDEN RING\\THEO KIẾN TRÚC AGENTIC RAG**
  (gợi ý; tên ngắn dùng trong báo cáo: *Index Beast*).
- Nhóm **4 Hollows**, danh sách thành viên (đánh dấu trưởng nhóm), giảng viên hướng dẫn, năm 2026.

### Lời cảm ơn
- 1 đoạn ngắn, cảm ơn giảng viên; thừa nhận thiếu sót.

### Mục lục

### Phân công nhiệm vụ
Hai bảng như mẫu:

📊 **Phân công theo tiến độ** (Stt · Tên nhiệm vụ · Người thực hiện), gợi ý các dòng:

| Stt | Nhiệm vụ | Người thực hiện |
|---|---|---|
| 1 | Tìm hiểu đề tài, chốt phạm vi Elden Ring + DLC, viết SRS | Cả nhóm |
| 2 | Nghiên cứu lý thuyết LLM, RAG, Agentic RAG, hybrid search | TV3, TV1 |
| 3 | Khảo sát nguồn, crawl, làm sạch, chunk, xây corpus | TV2 |
| 4 | Index Qdrant (E5 + BM25), retriever, reranker, tìm web | TV3, TV2 |
| 5 | Thiết kế và cài đặt vòng lặp Agent, tool, prompt, kiểm trích dẫn | TV3 |
| 6 | API FastAPI, bộ nhớ hội thoại, auth, rate limit, Docker, CI, triển khai VPS | TV1 |
| 7 | Web React, Discord bot, trang admin xem trace | TV4 |
| 8 | Xây golden set 200 câu, rubric, đánh giá, load test | TV2, TV3 |
| 9 | Viết báo cáo, slide, demo | Cả nhóm |

📊 **Phân công theo thành viên** (Stt · Thành viên · Nhiệm vụ · Chữ ký). Lấy từ `backend/README-TV1-TV3.md`, `backend/README-TV2-TV4.md`.

### Danh mục bảng · Danh mục hình

### Danh mục từ viết tắt
📊 Bảng 2 cột (Từ viết tắt · Diễn giải), xếp A–Z. Tối thiểu:
API, BM25, CI, DLC, E5, FAQ, HTTP, JSON, LLM, MRR, NLP, ONNX, OAuth, RAG, ReAct, RRF, SRS, SSE, VPS, p50/p95.

### Mở đầu (chương không đánh số)
Theo cấu trúc mẫu, 5 đoạn:
1. **Bối cảnh**: Elden Ring có thế giới, lore và hệ thống build rất lớn; thông tin rải trên nhiều wiki tiếng Anh;
   người chơi Việt khó tra cứu, phải tự đối chiếu nhiều trang.
2. **Vấn đề công nghệ**: LLM trả lời trôi chảy nhưng bịa (hallucination) và không biết dữ liệu game; RAG truyền thống
   giảm bịa nhưng truy xuất một lần, gặp khó với câu gõ sai, câu tiếng Việt trên corpus tiếng Anh, câu nhiều bước,
   câu cần tính toán.
3. **Đề tài**: nhóm chọn đề tài …, xây dựng *Index Beast* theo kiến trúc Agentic RAG: một Agent tự gọi tool để tìm,
   kiểm tên, tính toán, hỏi lại; mọi câu trả lời có trích dẫn nguồn; chạy trên Web và Discord.
4. **Bố cục**: Báo cáo gồm bốn chương: Chương 1 (…), Chương 2 (…), Chương 3 (…), Chương 4 (…).
5. Lời mong góp ý, cảm ơn.

---

## CHƯƠNG 1. CƠ SỞ LÝ THUYẾT VÀ CÔNG NGHỆ AGENTIC RAG

**Đoạn mở chương**: liệt kê các mục 1.1–1.7, nêu tài liệu nền (bài gốc RAG của Lewis và cộng sự 2020; ReAct; các
bài tổng quan về Agentic RAG).

### 1.1. Tổng quan về xử lý ngôn ngữ tự nhiên và mô hình ngôn ngữ lớn
- 1.1.1. Từ NLP truyền thống đến LLM (mốc: word2vec → Transformer → GPT → LLM có tool calling).
  📊 Bảng 1.1 — Một số mốc phát triển của mô hình ngôn ngữ.
- 1.1.2. Kiến trúc Transformer và cơ chế attention.
  📐 Công thức scaled dot-product attention.
- 1.1.3. Hạn chế của LLM: kiến thức tĩnh, hallucination, không trích dẫn được nguồn, giới hạn context.
- 1.1.4. Kỹ thuật prompt: system prompt, few-shot, đầu ra có cấu trúc (JSON), chain-of-thought / thinking mode.

### 1.2. Biểu diễn văn bản và truy xuất thông tin
- 1.2.1. Truy xuất thưa (sparse): TF-IDF, **BM25**.
  📐 Công thức BM25.
- 1.2.2. Truy xuất dày (dense): sentence embedding, mô hình **multilingual-E5**, độ tương đồng cosine.
  📐 Công thức cosine similarity.
- 1.2.3. **Hybrid search** và hợp nhất thứ hạng **Reciprocal Rank Fusion**.
  📐 Công thức RRF: `score(d) = Σ 1 / (k + rank_i(d))`.
- 1.2.4. Rerank bằng cross-encoder.
- 1.2.5. Cơ sở dữ liệu vector (Qdrant): collection, dense/sparse vector, payload, prefetch.
- 1.2.6. Chỉ số đánh giá truy xuất: Recall@k, MRR@k.
  📐 Công thức Recall@k, MRR@k.

### 1.3. Retrieval-Augmented Generation
- 1.3.1. Định nghĩa và pipeline chuẩn: index → retrieve → augment → generate.
  🖼️ Hình 1.1 — Pipeline RAG truyền thống.
- 1.3.2. Chunking: theo độ dài, theo section, overlap; ảnh hưởng tới truy xuất.
- 1.3.3. Grounding và trích dẫn nguồn.
- 1.3.4. Hạn chế của RAG truyền thống (dẫn sang 1.4): truy vấn một lần, không biết thiếu bằng chứng, không hỏi lại,
  không suy luận nhiều bước.

### 1.4. Tác tử AI và Agentic RAG
- 1.4.1. Khái niệm AI Agent: perception, reasoning, action, memory.
- 1.4.2. Tool calling / function calling: JSON Schema của tool, vòng lặp gọi tool.
- 1.4.3. Mô hình suy luận **ReAct** (Reason + Act): suy nghĩ → hành động → quan sát.
  🖼️ Hình 1.2 — Vòng lặp ReAct.
- 1.4.4. **Agentic RAG**: Agent điều khiển truy xuất (tự viết lại truy vấn, tìm nhiều lần, chọn nguồn, tự kiểm).
  📊 Bảng 1.2 — So sánh chatbot rule-based, RAG truyền thống và Agentic RAG (cách truy xuất, xử lý câu mơ hồ, nhiều
  bước, tính toán, trích dẫn, chi phí, độ trễ).
- 1.4.5. Single-agent và multi-agent: ưu nhược điểm.
- 1.4.6. Memory cho Agent: bộ nhớ ngắn hạn (lượt hội thoại), dài hạn / ngữ nghĩa (ký ức có embedding).

### 1.5. Đánh giá hệ thống hỏi đáp dùng LLM
- Golden set, rubric chấm theo ý; Answer Accuracy, faithfulness/groundedness, đúng hành vi (hỏi lại, từ chối).
- LLM-as-a-judge và hạn chế.
- Chỉ số vận hành: độ trễ p50/p95, số lượt gọi model, token, chi phí.

### 1.6. Các công nghệ sử dụng
📊 Bảng 1.3 — Công nghệ và phiên bản (lấy từ 📁 `docs/01_TECHSTACK.md`, nhóm theo tầng):
LLM DeepSeek · LangChain · LangGraph · multilingual-E5 (ONNX, fastembed) · BM25 · Qdrant · PostgreSQL · Redis ·
Tavily · FastAPI · React/Vite/Tailwind · discord.js · Docker Compose · Caddy · GitHub Actions.
Mỗi công nghệ 2–3 câu: là gì, dùng vào đâu trong Index Beast.

### 1.7. Các nghiên cứu và sản phẩm liên quan
- Wiki game (wiki.gg, Fextralife): tra theo từ khóa, không tổng hợp.
- Chatbot tổng quát (ChatGPT…): trả lời trôi chảy nhưng sai chi tiết game, không nguồn.
- Các hệ RAG/Agentic RAG tiêu biểu.
- 📊 Bảng 1.4 — Tóm tắt giải pháp liên quan và khoảng trống mà Index Beast nhắm tới.

---

## CHƯƠNG 2. PHÂN TÍCH BÀI TOÁN VÀ THIẾT KẾ HỆ THỐNG AGENTIC RAG
🎯 CLO 1 (PI 1.1–1.3), CLO 2 (PI 2.1–2.3)

**Đoạn mở chương**: chương trình bày bài toán, yêu cầu, workflow, vai trò Agent, kiến trúc, thiết kế tool/API,
knowledge base và memory; phần cài đặt ở Chương 3.

### 2.1. Phân tích và mô tả bài toán  🎯 PI 1.1
- 2.1.1. **Phát biểu bài toán**: đầu vào (câu hỏi tiếng Việt/Anh, có thể gõ sai, kèm lịch sử hội thoại) → đầu ra
  (câu trả lời đúng ngôn ngữ người hỏi, có trích dẫn nguồn, kèm ảnh; hoặc câu hỏi lại; hoặc từ chối khi ngoài phạm vi).
  Liệt kê khó khăn kiểu mẫu (K1…K6):
  - (K1) Corpus tiếng Anh, người hỏi tiếng Việt.
  - (K2) Câu gõ sai tên riêng, không dấu, Telex, viết tắt.
  - (K3) Câu nhiều bước, cần tổng hợp nhiều trang (quest, tuyến đường).
  - (K4) Câu build cần tính chỉ số theo level/class.
  - (K5) Câu mơ hồ, thiếu dữ kiện (level, class, vũ khí).
  - (K6) LLM bịa chi tiết game; cần trích dẫn kiểm chứng được.
- 2.1.2. **Phân loại câu hỏi thường gặp**.
  📊 Bảng 2.1 — Loại câu hỏi · ví dụ · yêu cầu xử lý (lore, nhân vật, vị trí, quest, trang bị/chỉ số, build,
  tổng quan, ngoài phạm vi, chào hỏi). 📁 nhãn trong `backend/eval/golden_set.jsonl`.
- 2.1.3. **Hạn chế của giải pháp hiện có**: wiki/FAQ, chatbot rule-based, RAG truyền thống (ví dụ cụ thể một câu
  gõ sai hoặc câu build mà RAG một lần trả sai).
- 2.1.4. **Vì sao cần Agentic RAG**: ánh xạ K1…K6 → năng lực Agent.
  📊 Bảng 2.2 — Khó khăn · năng lực Agent · tool tương ứng.

### 2.2. Mục tiêu, phạm vi và yêu cầu
- 2.2.1. **Mục tiêu** (M1…M4):
  - (M1) Corpus Elden Ring sạch, rõ nguồn, index hybrid.
  - (M2) Agent tự điều khiển truy xuất và tool, mọi câu trả lời có trích dẫn kiểm được.
  - (M3) Phục vụ Web và Discord, có bộ nhớ hội thoại, đáp ứng trong hạn thời gian.
  - (M4) Đánh giá định lượng trên golden set, có số đo truy xuất, chất lượng và độ trễ.
- 2.2.2. **Câu hỏi nghiên cứu** (tùy chọn, theo mẫu): RQ1 Agentic RAG có tốt hơn RAG một lần? RQ2 Hybrid có tốt hơn
  dense-only? RQ3 Reranker có đáng thêm độ trễ?
- 2.2.3. **Phạm vi**: Elden Ring base game + Shadow of the Erdtree; chỉ index tiếng Anh; không có bộ tối ưu AR/DPS.
  📊 Bảng 2.3 — Phạm vi thực hiện so với đề cương (làm / không làm / lý do). 📁 `docs/adr/004-base-game-scope.md`
- 2.2.4. **Yêu cầu chức năng và phi chức năng**.
  📊 Bảng 2.4 — Yêu cầu chức năng (FR). 📊 Bảng 2.5 — Yêu cầu phi chức năng (độ trễ 45 s/90 s, ~50 người đồng thời,
  bảo mật, quyền riêng tư). 📁 `docs/02_SRS.md`
- 2.2.5. **Đóng góp của đề tài** (gạch đầu dòng).

### 2.3. Phân tích workflow nghiệp vụ  🎯 PI 1.2
- 2.3.1. Workflow hỏi đáp online.
  🖼️ Hình 2.1 — Sơ đồ workflow: người chơi hỏi ⇒ kiểm phạm vi ⇒ nạp ký ức ⇒ Agent phân tích ý định ⇒ gọi tool ⇒
  chọn bằng chứng / hỏi lại ⇒ sinh câu trả lời ⇒ kiểm trích dẫn ⇒ trả lời. 📁 `docs/indexbeast-system-pipeline.md`
- 2.3.2. Workflow hỏi lại (clarification) nhiều lượt.
  🖼️ Hình 2.2 — Sơ đồ tuần tự một lượt hỏi lại.
- 2.3.3. Workflow dữ liệu offline: crawl ⇒ lọc ⇒ biến đổi ⇒ chunk ⇒ index ⇒ cập nhật.
  🖼️ Hình 2.3. 📁 `docs/data-pipeline.md`
- 2.3.4. Use case: người chơi Web, người chơi Discord, quản trị viên (xem trace, thống kê).
  🖼️ Hình 2.4 — Biểu đồ use case.

### 2.4. Vai trò và nhiệm vụ của Agent  🎯 PI 1.3
- 2.4.1. Một Agent duy nhất (True Agent): quá trình chuyển từ pipeline nhiều vai sang một vòng lặp.
  📊 Bảng 2.6 — Phương án đã cân nhắc (pipeline nhiều vai, multi-agent, Agent tự viết câu trả lời) và lý do loại.
  📁 `docs/adr/006-true-agent.md`
- 2.4.2. Nhiệm vụ của Agent: hiểu yêu cầu và ngôn ngữ; viết truy vấn tiếng Anh; tìm corpus/web; xác định tên thực
  thể; ghi điều kiện người chơi; tính build; chọn bằng chứng; hỏi lại; từ chối ngoài phạm vi.
- 2.4.3. Phân chia trách nhiệm Agent – server: Agent quyết định ngữ nghĩa; server giữ guard tất định.
  📊 Bảng 2.7 — Các guard phía server và lý do. 📁 `backend/app/rag/README.md` (mục Hiện trạng)

### 2.5. Thiết kế kiến trúc hệ thống  🎯 PI 2.1
- 2.5.1. Nguyên tắc thiết kế: Agent quyết định, server kiểm; một luồng không cờ; mọi nguồn truy được; tối giản hạ tầng.
- 2.5.2. Kiến trúc tổng thể.
  🖼️ Hình 2.5 — Sơ đồ kiến trúc: User ⇒ Web React / Discord bot ⇒ Caddy ⇒ FastAPI ⇒ ChatService ⇒ LangGraph
  ChatPipeline ⇒ DeepSeek ⇒ Tools ⇒ Qdrant / PostgreSQL / Redis / Tavily. 📁 `docs/04_ARCHITECTURE.md`, `docs/rag-diagram.md`
- 2.5.3. Mô tả các thành phần (mỗi thành phần: vai trò, đầu vào/ra, công nghệ):
  giao diện (Web, Bot) · API gateway (Caddy, FastAPI, rate limit, auth) · Agent controller (LangGraph) · LLM ·
  tầng retrieval · tầng tool · knowledge base · memory · trace/quan trị.
  📊 Bảng 2.8 — Thành phần · trách nhiệm · công nghệ · thư mục mã.
- 2.5.4. Kiến trúc triển khai (container, mạng, cổng).
  🖼️ Hình 2.6 — Sơ đồ triển khai Docker Compose.

### 2.6. Thiết kế tool và API  🎯 PI 2.2
- 2.6.1. Danh sách tool.
  📊 Bảng 2.9 — Tool · mục đích · tham số chính · kết quả trả về · guard:
  `search_corpus`, `search_web`, `check_name`, `open_evidence`, `set_conditions`, `run_python`, `ask_user`, `reply`,
  `finish`. 📁 `backend/app/rag/true_agent.py`
- 2.6.2. Hợp đồng tool: JSON Schema sinh từ Pydantic; lỗi tool trả lại cho Agent tự sửa.
  Ví dụ schema một tool (trích ngắn).
- 2.6.3. Thiết kế API.
  📊 Bảng 2.10 — Endpoint · phương thức · mô tả · xác thực (`/api/v1/chat` JSON + SSE, conversations, feedback,
  auth, admin trace/stats, health). 📁 `docs/api/openapi.json`
- 2.6.4. Định dạng câu trả lời: JSON `answer` + `evidence`, `quote_id` do server cấp; sự kiện SSE.

### 2.7. Thiết kế knowledge base  🎯 PI 2.3
- 2.7.1. Nguồn dữ liệu.
  📊 Bảng 2.11 — Nguồn · mục đích · cách truy cập · giấy phép/robots (wiki.gg, fanapis, Wikipedia; Fandom bị loại).
  📁 `docs/data-sources.md`
- 2.7.2. Làm sạch và chuẩn hóa: bỏ điều hướng, giữ bảng, lọc chất lượng, khử trùng.
- 2.7.3. Chiến lược chunking theo section. 📁 `docs/adr/003-chunking.md`
- 2.7.4. Lược đồ index: dense E5 384 chiều + sparse BM25, payload (URL, tiêu đề, section, ngôn ngữ, ảnh).
  📊 Bảng 2.12 — Trường payload. 📁 `backend/core/vector/schema.py`
- 2.7.5. Lược đồ cơ sở dữ liệu quan hệ.
  🖼️ Hình 2.7 — ERD (conversations, messages, memories, users, auth_sessions, discord_guild…). 📁 `backend/core/db/models.py`

### 2.8. Thiết kế memory  🎯 PI 2.3
- 2.8.1. Bộ nhớ hội thoại và trạng thái làm việc (PostgreSQL, khóa lạc quan theo `revision`).
- 2.8.2. Ký ức ngữ nghĩa: mục nhớ chủ đề/sự kiện, index E5 trong collection riêng, lọc theo chủ sở hữu.
- 2.8.3. Quyền riêng tư: không dùng ký ức `fact` ở thread Discord chung; retention. 📁 `docs/privacy.md`,
  `docs/api/agent-semantic-memory.md`

### 2.9. Tóm tắt chương

---

## CHƯƠNG 3. XÂY DỰNG HỆ THỐNG INDEX BEAST
🎯 CLO 3 (PI 3.1–3.4)

**Đoạn mở chương**: chương trình bày cài đặt pipeline dữ liệu, Agent, LLM/prompt, retrieval, tool, reasoning
workflow và giao diện.

### 3.1. Xây dựng pipeline dữ liệu
- 3.1.1. Thu thập (crawl) qua MediaWiki API, giới hạn tốc độ, lưu raw. 📁 `backend/ingest/crawl/`
- 3.1.2. Lọc và biến đổi: quy tắc lọc, xử lý bảng, metadata. 📁 `backend/ingest/filter/`, `transform/`
- 3.1.3. Chunk và index vào Qdrant. 📁 `backend/ingest/chunk/`, `index/`
- 3.1.4. Thống kê corpus.
  📊 Bảng 3.1 — Số trang raw → sau lọc → số chunk → số điểm Qdrant (vd. 34.070 điểm ở collection S4).
  📁 `docs/testing/2026-11-09_tv2-structured-release.md`, `docs/tv2-full-raw-clean-chunk-plan.md`
- 3.1.5. Cập nhật dữ liệu tăng dần. 📁 `backend/ingest/update.py`

### 3.2. Xây dựng Agent bằng LangChain và LangGraph  🎯 PI 3.1
- 3.2.1. Lý do chọn LangChain + LangGraph.
- 3.2.2. State và các node của `ChatPipeline`: scope → memory → agent → context → prompt → generate.
  🖼️ Hình 3.1 — Đồ thị LangGraph. 📁 `backend/app/rag/pipeline.py`
- 3.2.3. Vòng lặp Agent: `bind_tools`, `tool_choice`, ngân sách lượt gọi và thời gian, lượt cuối buộc `finish`.
  Trích mã rút gọn (đưa bản đầy đủ vào Phụ lục). 📁 `backend/app/rag/true_agent.py`

### 3.3. Tích hợp LLM và thiết kế prompt  🎯 PI 3.2
- 3.3.1. Adapter LLM DeepSeek: model, temperature, thinking chỉ ở bước viết khi `needs_reasoning`, retry định dạng.
  📁 `backend/app/adapters/llm.py`
- 3.3.2. Hệ thống prompt.
  📊 Bảng 3.2 — Prompt · vai trò · khi nào dùng (true_agent, persona, answer, language, gameplay_advice, overview,
  format_retry, guard, image_selection). 📁 `backend/app/rag/prompts/`
- 3.3.3. System prompt của Agent (trích các quy tắc chính) và prompt template của bước trả lời (trích).

### 3.4. Tích hợp retrieval  🎯 PI 3.3
- 3.4.1. Encoder E5 ONNX, tiền tố `query:`/`passage:`, giới hạn 512 token. 📁 `backend/core/encoders/onnx.py`
- 3.4.2. Hybrid retriever: prefetch dense 30 + BM25 30 → RRF → top 5, ngân sách 12.000 ký tự, timeout.
  📁 `backend/app/rag/retriever.py`
- 3.4.3. Reranker tùy chọn (Jina), fallback giữ thứ tự RRF. 📁 `backend/app/rag/reranker.py`
- 3.4.4. Tìm web Tavily: chế độ off/auto/always, allowlist domain, làm sạch trích đoạn. 📁 `backend/app/adapters/tavily.py`

### 3.5. Tích hợp tool  🎯 PI 3.3
- 3.5.1. Tool tra cứu: `search_corpus`, `check_name`, `open_evidence`, `search_web`.
- 3.5.2. Tool trạng thái hội thoại: `set_conditions` (kiểm điều kiện có trong lời người chơi), `ask_user`, `reply`.
- 3.5.3. **Code tool**: `run_python` — Agent tự viết Python tính phân bổ 8 chỉ số build; sandbox (tập con Python,
  không import/file/mạng, tiến trình con có timeout). Ví dụ mã Agent sinh ra cho một câu build.
  📁 `backend/app/rag/python_sandbox.py`, `backend/app/rag/gameplay_knowledge.py`
- 3.5.4. Xử lý lỗi tool và tham số hỏng.

### 3.6. Reasoning workflow và kiểm soát chất lượng câu trả lời  🎯 PI 3.4
- 3.6.1. Vòng suy luận: input ⇒ reasoning ⇒ tool selection ⇒ tool execution ⇒ observation ⇒ lặp ⇒ `finish` ⇒
  response generation.
  🖼️ Hình 3.2 — Sơ đồ tuần tự một lượt chat đầy đủ.
- 3.6.2. Dựng context từ bằng chứng Agent chọn (tối đa 5).
- 3.6.3. Sinh câu trả lời JSON, kiểm trích dẫn nguyên văn, sinh lại tối đa 1 lần, Answer Guard.
  📁 `backend/app/rag/generator.py`, `output.py`, `evidence.py`
- 3.6.4. Chọn ảnh minh họa song song. 📁 `backend/app/services/answer_media.py`
- 3.6.5. **Ví dụ trace thực tế** (3 ca): một câu lore, một câu build dùng `run_python`, một câu phải hỏi lại.
  📊 Bảng 3.3 — Các bước tool của từng ca (tool, tham số, kết quả rút gọn, thời gian).
  📁 `GET /api/v1/admin/trace/{id}`, `docs/testing/2026-11-22_true-agent-gd2/`

### 3.7. Xây dựng API, giao diện Web và Discord bot
- 3.7.1. API FastAPI: chat JSON/SSE, rate limit theo IP, timeout, xác thực admin, đăng nhập Discord OAuth.
- 3.7.2. Web React: khung chat, hiển thị nguồn và ảnh, chế độ web OFF/ON/ALWAYS, trang admin.
  🖼️ Hình 3.3 — Giao diện chat Web. 🖼️ Hình 3.4 — Trang admin xem trace.
- 3.7.3. Discord bot: `/ask`, mention, `/setup`, `/clear`, thread.
  🖼️ Hình 3.5 — Bot trả lời trên Discord.

### 3.8. Tóm tắt chương

---

## CHƯƠNG 4. ĐÁNH GIÁ VÀ TRIỂN KHAI HỆ THỐNG
🎯 CLO 4 (PI 4.1–4.2)

**Đoạn mở chương**: thiết lập đánh giá, kết quả truy xuất, kết quả đầu cuối, so sánh/ablation, hiệu năng, triển khai,
thảo luận. Nêu nguyên tắc như mẫu: bảng số liệu lấy từ file kết quả, không chép tay.

### 4.1. Thiết lập đánh giá  🎯 PI 4.1
- 4.1.1. Bộ dữ liệu đánh giá: golden set 200 câu (VI/EN, 3 mức khó, nhãn gõ sai, hỏi lại, ngoài phạm vi), quy trình
  duyệt. 📊 Bảng 4.1 — Phân bố độ khó × ngôn ngữ. 📊 Bảng 4.2 — Nhãn kiểu đầu vào. 📁 `backend/eval/README.md`
- 4.1.2. Các tập đo: baseline 25 câu, tập 100 ca chọn trước, tập trước/sau True Agent.
- 4.1.3. Rubric và chỉ số: Answer Accuracy, đúng hành vi, bám nguồn, Recall@5, MRR@5, p50/p95, lượt gọi model, token.
  📁 `docs/evaluation/s4-rubric.md`
- 4.1.4. Cấu hình máy, model, collection, phiên bản mã (commit) dùng khi đo.

### 4.2. Đánh giá truy xuất
- 📊 Bảng 4.3 — Recall@5, MRR@5 theo nhóm: hybrid và dense-only. 📁 `docs/testing/2026-11-14_s4-retrieval-matrix.md`
- So sánh có/không reranker. 📁 `docs/testing/2026-11-16_reranker-review-live.md`
- Nhận xét theo ngôn ngữ và câu gõ sai.

### 4.3. Đánh giá chất lượng câu trả lời đầu cuối
- 📊 Bảng 4.4 — Kết quả chính (ca có phản hồi, Accuracy, hành vi, bám nguồn, p50/p95).
  Số liệu S4 (100 ca, 14/11): Accuracy 71/83 (85,54%), hành vi 15/17 (88,24%), bám nguồn 78/89 (87,64%),
  p50/p95 9,68 s / 20,73 s. 📁 `docs/testing/2026-11-14_s4-evaluation-100.md`
  → **Cập nhật bằng lần đo mới nhất** (`docs/testing/2026-11-24_golden-200-ablation/`) nếu có.
- 📊 Bảng 4.5 — Kết quả theo nhóm (VI/EN, độ khó, câu gõ sai).
- Phân tích lỗi: 📊 Bảng 4.6 — Loại lỗi · số ca · ví dụ · nguyên nhân.

### 4.4. So sánh và ablation
- 4.4.1. Pipeline nhiều vai (trước 22/11) vs True Agent.
  📊 Bảng 4.7 — grounded, p50, p95, lượt gọi model/câu, token (baseline 7,8 lượt, p95 36,4 s → 6,0 lượt, p95 29,1 s).
  📁 `docs/testing/2026-11-22_baseline-truoc-true-agent/`, `docs/testing/2026-11-22_true-agent-gd2/`
- 4.4.2. Ablation thành phần (web search, reranker, thinking, memory…).
  🖼️ Hình 4.1 — Biểu đồ ablation. 📁 `docs/testing/2026-11-24_golden-200-ablation/`, `backend/eval/summarize_ablation.py`
- 4.4.3. Sau khi thay calculator bằng `run_python`. 📁 `docs/testing/2026-11-23_do-lai-sau-run-python/`

### 4.5. Hiệu năng và chi phí
- 📊 Bảng 4.8 — Độ trễ theo bước (retrieval, agent, generate), token vào/ra, chi phí ước tính/câu.
  📁 `backend/scripts/trace_latency.py`, `backend/scripts/llm_cost.py`
- Load test. 📁 `backend/loadtest/`, `docs/testing/s5-load-test-plan.md`, `docs/handover/2026-11-16_s5-tv3_load-test-chi-phi.md`
  🖼️ Hình 4.2 — Độ trễ theo số người dùng đồng thời.

### 4.6. Triển khai hệ thống  🎯 PI 4.2
- 4.6.1. Môi trường: VPS 4 vCPU/8 GB, Docker Compose staging và production. 📁 `docs/production.md`, `docs/staging.md`
- 4.6.2. Bảo mật vận hành: Caddy HTTPS, rate limit mọi `/api`, token dịch vụ cho bot, admin token, CORS.
  📁 `docs/handover/2026-11-22_s5-tv1_chong-dos.md`
- 4.6.3. CI/CD: GitHub Actions (lint, test, kiểm OpenAPI). 📁 `.github/workflows/ci.yml`
- 4.6.4. Demo: kịch bản demo 5 câu (lore, gõ sai tiếng Việt, quest nhiều bước, build có tính toán, hỏi lại).
  🖼️ Hình 4.3 — Ảnh chụp demo.
- 4.6.5. Hướng dẫn cài đặt (tóm tắt, bản đầy đủ ở Phụ lục) và hướng dẫn sử dụng cho người chơi.

### 4.7. Thảo luận
- Điểm mạnh; hạn chế (corpus thiếu bảng chỉ số, token đầu vào của Agent lớn, LLM-as-judge, server không kiểm lại số
  build); các mối đe dọa tới tính hợp lệ của đánh giá (tập đo nhỏ, người chấm, chạy song song ảnh hưởng độ trễ).

---

## KẾT LUẬN (chương không đánh số)
Theo đúng 4 phần của báo cáo mẫu:

1. **Kết quả đạt được** — đối chiếu lần lượt M1…M4 ở mục 2.2.1, mỗi mục 1–2 câu kèm số liệu chính; một đoạn tóm
   kết quả nổi bật và kết quả chưa như kỳ vọng.
2. **Bài học kinh nghiệm** — gợi ý: chia vai nhiều LLM làm mất ngữ cảnh → một Agent; server chỉ nên giữ guard tất
   định; kiểm trích dẫn nguyên văn chống bịa; chất lượng corpus quyết định trần chất lượng; cố định tập đo trước khi sửa.
3. **Tác động dự kiến** — về học thuật, ứng dụng (cộng đồng người chơi Việt), giáo dục (mẫu tham khảo Agentic RAG có
   đo đạc).
4. **Hướng phát triển** — bổ sung bảng chỉ số/vũ khí có cấu trúc; rerank cục bộ; giảm token Agent; đánh giá bởi
   người chơi thật; mở rộng sang game khác; streaming câu trả lời sớm hơn.

---

## TÀI LIỆU THAM KHẢO
Định dạng thống nhất (IEEE hoặc APA). Danh sách gợi ý:
- Vaswani et al., 2017 — *Attention Is All You Need*.
- Lewis et al., 2020 — *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*.
- Yao et al., 2023 — *ReAct: Synergizing Reasoning and Acting in Language Models*.
- Robertson & Zaragoza, 2009 — *The Probabilistic Relevance Framework: BM25 and Beyond*.
- Cormack et al., 2009 — *Reciprocal Rank Fusion*.
- Wang et al., 2024 — *Multilingual E5 Text Embeddings*.
- Một bài tổng quan về Agentic RAG (2025).
- Tài liệu LangChain, LangGraph, Qdrant, DeepSeek API, Tavily.

## PHỤ LỤC
- **A. Tổ chức mã nguồn** — 📊 bảng thư mục · vai trò · người phụ trách (lấy từ `README.md`).
- **B. Cài đặt lõi** — trích mã rút gọn: vòng lặp Agent (`true_agent.py`), hybrid retriever (`retriever.py`),
  kiểm trích dẫn (`output.py`), sandbox (`python_sandbox.py`).
- **C. Prompt đầy đủ** — `true_agent.md`, `answer.md`.
- **D. Hướng dẫn cài đặt và tái lập** — chạy local (`make dev`), nạp corpus, chạy đánh giá
  (`scripts.benchmark_agent`, `eval.measure_retrieval`), triển khai production.
- **E. Hồ sơ phiên bản dữ liệu và đánh giá** — commit, SHA-256 golden set/manifest, tên collection.
- **F. Kết quả chi tiết theo từng ca** — trích từ `*-scores.jsonl`.

---

## Checklist trước khi nộp
- [ ] Mỗi PI trong bảng H12 có ít nhất một mục báo cáo đáp ứng (đối chiếu cột 🎯).
- [ ] Mọi hình/bảng có số thứ tự, chú thích và được nhắc trong đoạn văn.
- [ ] Số liệu Chương 4 lấy từ một lần đo thống nhất, ghi commit và ngày đo.
- [ ] Từ viết tắt dùng trong bài đều có trong danh mục.
- [ ] Mỗi chương có đoạn mở và tóm tắt.
