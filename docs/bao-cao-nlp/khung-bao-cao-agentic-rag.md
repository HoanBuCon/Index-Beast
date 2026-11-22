# Khung báo cáo H12 — Index Beast (Agentic RAG)

Chuyển biểu mẫu **H12. Phát triển tác tử AI** sang đề tài **Index Beast**: trợ lý hỏi đáp Elden Ring (gồm DLC Shadow of the Erdtree)
trên Website và Discord, dạng **Agentic RAG**. Giữ nguyên 4 CLO, 12 PI và trọng số; cột cuối thay bằng yêu cầu cụ thể của Index Beast,
kèm nơi lấy minh chứng trong repo.

## 1. Bảng CLO – PI

| Mã CLO | Nội dung CLO | % | Mã PI | Nội dung PI | % | Triển khai cụ thể cho Index Beast (Agentic RAG) | Minh chứng trong repo |
|---|---|---:|---|---|---:|---|---|
| 1 | Phân tích bài toán và xác định yêu cầu cho hệ thống **Agentic RAG** | 20 | 1.1 | Xác định bài toán phù hợp với Agentic RAG | 5 | Bài toán: người chơi hỏi lore, gameplay, quest, trang bị, build Elden Ring bằng tiếng Việt/Anh, thường gõ sai tên, viết tắt, không dấu. Phân loại câu hỏi: lore/nhân vật, vị trí/tuyến đường, quest nhiều bước, trang bị/chỉ số, tư vấn build, ngoài phạm vi. Hạn chế của wiki/FAQ/chatbot rule-based: tra theo từ khóa, không hiểu tiếng Việt, không tổng hợp nhiều trang. Hạn chế của **RAG truyền thống** (truy xuất một lần rồi sinh): không tự tìm lại khi thiếu bằng chứng, không hỏi lại khi câu mơ hồ, không tính được build, dễ bịa. Lý do cần Agentic RAG: Agent tự lập truy vấn tiếng Anh, tìm nhiều lần, kiểm tên, chọn bằng chứng, tính toán và bắt buộc trích dẫn nguồn. | `docs/02_SRS.md`, `docs/adr/004-base-game-scope.md`, `backend/eval/README.md` (nhãn `typo`, `telex`, `out_of_scope`) |
| | | | 1.2 | Phân tích workflow nghiệp vụ | 5 | Người chơi hỏi (Web/Discord) ⇒ kiểm phạm vi ⇒ nạp ký ức hội thoại ⇒ Agent hiểu ý định ⇒ Agent gọi tool tìm corpus / web / kiểm tên ⇒ Agent chọn tối đa 5 bằng chứng (hoặc hỏi lại) ⇒ Generator viết câu trả lời JSON có trích dẫn ⇒ server kiểm trích dẫn, Answer Guard ⇒ trả lời kèm nguồn và ảnh. Song song là workflow dữ liệu offline: crawl ⇒ lọc ⇒ biến đổi ⇒ chunk ⇒ index. | `docs/indexbeast-system-pipeline.md`, `docs/data-pipeline.md`, `docs/rag-diagram.md` |
| | | | 1.3 | Xác định vai trò Agent và nhiệm vụ | 10 | Một Agent duy nhất (True Agent, ADR 006) đảm nhiệm: hiểu yêu cầu và ngôn ngữ trả lời; viết truy vấn; tìm corpus/web; xác định đúng tên thực thể; ghi điều kiện người chơi (level, class, vũ khí); tự tính phân bổ chỉ số build; chọn bằng chứng; hỏi lại khi thiếu dữ kiện; từ chối câu ngoài phạm vi. Server chỉ giữ guard tất định (schema tool, chính sách corpus, ngân sách, trích dẫn). Nêu lý do không chọn multi-agent. | `docs/adr/006-true-agent.md`, `backend/app/rag/prompts/true_agent.md` |
| 2 | Thiết kế kiến trúc và các thành phần của hệ thống Agentic RAG | 30 | 2.1 | Thiết kế kiến trúc Agentic RAG | 15 | Kiến trúc: Người dùng ⇒ Web React / Discord bot ⇒ Caddy ⇒ FastAPI (rate limit, auth) ⇒ LangGraph `ChatPipeline` (scope → memory → **agent** → context → prompt → generate) ⇒ DeepSeek LLM ⇒ Tools ⇒ Qdrant (hybrid index) + PostgreSQL + Redis + Tavily. Sơ đồ kiến trúc tổng thể, sơ đồ online (một lượt chat) và offline (ingest). Mô tả từng thành phần và lý do chọn công nghệ. | `docs/04_ARCHITECTURE.md`, `docs/01_TECHSTACK.md`, `backend/app/rag/pipeline.py` |
| | | | 2.2 | Thiết kế tool và API | 10 | 9 tool có schema (Pydantic → JSON Schema): `search_corpus` (hybrid search corpus), `search_web` (Tavily, allowlist wiki), `check_name` (tìm tiêu đề khớp tên), `open_evidence` (mở đầy đủ đoạn), `set_conditions` (điều kiện người chơi có kiểm nguồn), `run_python` (tính toán trong sandbox), `ask_user` (hỏi lại), `reply` (chào hỏi/ngoài phạm vi), `finish` (chốt bằng chứng, intent, ngôn ngữ). API: `POST /api/v1/chat` (JSON + SSE), conversations, feedback, admin trace/stats, health. | `backend/app/rag/true_agent.py`, `docs/api/openapi.json`, `backend/app/api/routes/` |
| | | | 2.3 | Thiết kế knowledge base và memory | 5 | **Knowledge base**: nguồn Elden Ring wiki.gg, Fan APIs, Wikipedia; làm sạch HTML, giữ bảng, chunk theo section, chỉ index tiếng Anh; vector E5 (384 chiều) + BM25 sparse trong Qdrant, metadata nguồn/URL/ảnh. **Memory**: hội thoại và trạng thái làm việc trong PostgreSQL; ký ức ngữ nghĩa (chủ đề, sự kiện) index E5 trong collection Qdrant riêng; giới hạn quyền riêng tư (không dùng ký ức `fact` ở thread Discord chung). | `docs/data-sources.md`, `docs/adr/003-chunking.md`, `backend/ingest/`, `docs/api/agent-semantic-memory.md` |
| 3 | Triển khai hệ thống Agentic RAG tích hợp LLM, retrieval và các công cụ | 40 | 3.1 | Xây dựng Agent bằng framework | 5 | LangChain (`ChatDeepSeek.bind_tools`, LCEL) + LangGraph (`StateGraph`, node `agent` chạy vòng lặp tool). Trình bày cấu trúc state, các node và cạnh của graph. | `backend/app/rag/pipeline.py`, `backend/app/rag/true_agent.py` |
| | | | 3.2 | Tích hợp LLM | 5 | DeepSeek `deepseek-flash` qua adapter chung, native tool calling, thinking chỉ bật ở bước viết khi Agent báo `needs_reasoning`. Thiết kế prompt: system prompt Agent, persona, prompt trả lời JSON có trích dẫn, prompt ngôn ngữ, tư vấn gameplay, sinh lại khi sai định dạng, Answer Guard, chọn ảnh. | `backend/app/adapters/llm.py`, `backend/app/rag/prompts/*.md` |
| | | | 3.3 | Tích hợp retrieval và tools | 20 | **Retrieval**: hybrid search Qdrant (prefetch dense 30 + BM25 30 → RRF → top 5, ngân sách 12.000 ký tự), Jina reranker tùy chọn, timeout và fallback. **Tool**: tra corpus, tra web, kiểm tên, mở bằng chứng. **Code tool / code agent**: Agent tự viết Python tính phân bổ 8 chỉ số build, chạy trong sandbox `run_python` (tập con Python, không import/file/mạng, có timeout). Xử lý lỗi tool: trả lỗi về cho Agent tự sửa. | `backend/app/rag/retriever.py`, `backend/app/rag/reranker.py`, `backend/app/adapters/tavily.py`, `backend/app/rag/python_sandbox.py` |
| | | | 3.4 | Xây dựng reasoning workflow | 10 | Vòng lặp: câu hỏi ⇒ Agent suy luận ⇒ chọn tool ⇒ thực thi + quan sát kết quả ⇒ lặp (tìm lại, kiểm tên, tính toán, hỏi lại) ⇒ `finish` chọn bằng chứng ⇒ dựng context ⇒ Generator viết JSON ⇒ kiểm trích dẫn nguyên văn ⇒ sinh lại tối đa 1 lần / Answer Guard ⇒ phản hồi. Ngân sách lượt gọi và thời gian; lượt cuối buộc `finish`. Minh họa bằng trace thật của 2–3 câu (lore, build, câu cần hỏi lại). | `backend/app/rag/generator.py`, `backend/app/rag/output.py`, trace `GET /api/v1/admin/trace/{id}` |
| 4 | Đánh giá, kiểm thử và triển khai hệ thống Agentic RAG | 10 | 4.1 | Đánh giá hiệu quả Agentic RAG | 5 | Golden set 200 câu (VI/EN, 3 mức khó, có câu gõ sai, ngoài phạm vi, nhiều lượt), đã duyệt. Đánh giá retrieval: Recall@5, MRR@5, so sánh hybrid với dense-only. Đánh giá câu trả lời: rubric chấm đúng ý, grounded/trích dẫn, hành vi (hỏi lại, từ chối), LLM-as-judge. Hiệu năng: p50/p95 latency, số lượt gọi model, token. So sánh trước/sau True Agent (baseline 25 câu, tập 100 ca). | `backend/eval/`, `docs/evaluation/s4-rubric.md`, `docs/testing/2026-11-14_s4-evaluation-100.md`, `docs/testing/2026-11-22_true-agent-gd2/` |
| | | | 4.2 | Triển khai hệ thống | 5 | Demo Web chat (SSE, nguồn, ảnh, trang admin xem trace) và Discord bot (`/ask`, mention, `/setup`). API service FastAPI; Docker Compose (PostgreSQL, Qdrant, Redis, API, Caddy HTTPS) trên VPS; CI GitHub Actions; rate limit, đăng nhập Discord OAuth. Hướng dẫn cài đặt và hướng dẫn sử dụng. | `README.md`, `docs/production.md`, `docs/staging.md`, `docker-compose.prod.yml`, `infra/` |

Tổng: CLO 20 + 30 + 40 + 10 = 100; PI 5+5+10+15+10+5+5+5+20+10+5+5 = 100.

### Thay đổi so với biểu mẫu gốc

| Chỗ | Mẫu gốc (AI Agent tư vấn tuyển sinh) | Index Beast |
|---|---|---|
| Tên CLO | "hệ thống AI Agent" | "hệ thống Agentic RAG" |
| PI 1.1 | So với FAQ / chatbot rule-based | So thêm với **RAG truyền thống** — trọng tâm của Agentic RAG |
| PI 2.1 | Agent Controller ⇒ LLM ⇒ Tools ⇒ Knowledge Base | Tách rõ **retrieval layer** (hybrid search, reranker) khỏi các tool khác |
| PI 2.3 | Knowledge base tuyển sinh | Knowledge base = **pipeline ingest + vector index**; memory = **ký ức ngữ nghĩa** |
| PI 3.3 | "Tích hợp tools" | "Tích hợp **retrieval** và tools"; code tool = `run_python` |
| PI 3.4 | Vòng lặp reasoning chung | Thêm bước **kiểm trích dẫn / grounding** sau khi sinh |
| PI 4.1 | Bộ test ≥ 30 câu | Golden set 200 câu + chỉ số retrieval và grounding |

## 2. Cấu trúc báo cáo

**Chương 1. Cơ sở lý thuyết và công nghệ Agentic RAG**
1.1. Mô hình ngôn ngữ lớn và hạn chế (hallucination, kiến thức tĩnh)
1.2. Retrieval-Augmented Generation: dense, sparse (BM25), hybrid search, RRF, rerank
1.3. Từ RAG truyền thống đến Agentic RAG: tool calling, vòng lặp ReAct, tự tìm lại, hỏi lại
1.4. Memory cho Agent: bộ nhớ hội thoại và ký ức ngữ nghĩa
1.5. Grounding và trích dẫn nguồn
1.6. Công nghệ sử dụng: DeepSeek, LangChain, LangGraph, Qdrant, multilingual-E5, FastAPI, React, discord.js, Docker

**Chương 2. Phân tích bài toán và thiết kế hệ thống Agentic RAG** (CLO 1, CLO 2)
2.1. Bài toán hỏi đáp Elden Ring và các loại câu hỏi (PI 1.1)
2.2. Hạn chế của wiki/FAQ, chatbot rule-based và RAG truyền thống (PI 1.1)
2.3. Workflow nghiệp vụ online và offline (PI 1.2)
2.4. Vai trò và nhiệm vụ của Agent; vì sao chọn một Agent thay multi-agent (PI 1.3)
2.5. Kiến trúc tổng thể và các thành phần (PI 2.1)
2.6. Thiết kế tool và API (PI 2.2)
2.7. Thiết kế knowledge base: nguồn dữ liệu, làm sạch, chunking, index (PI 2.3)
2.8. Thiết kế memory và quyền riêng tư (PI 2.3)

**Chương 3. Xây dựng hệ thống Agentic RAG** (CLO 3)
3.1. Pipeline dữ liệu: crawl → lọc → biến đổi → chunk → index
3.2. Xây dựng Agent bằng LangChain + LangGraph (PI 3.1)
3.3. Tích hợp LLM và thiết kế prompt (PI 3.2)
3.4. Tích hợp retrieval: hybrid search, reranker, tìm web (PI 3.3)
3.5. Tích hợp tools và code tool `run_python` (PI 3.3)
3.6. Reasoning workflow, kiểm trích dẫn và Answer Guard; ví dụ trace (PI 3.4)
3.7. Giao diện Web và Discord bot

**Chương 4. Đánh giá và triển khai hệ thống** (CLO 4)
4.1. Bộ dữ liệu đánh giá (golden set 200 câu) và rubric (PI 4.1)
4.2. Đánh giá retrieval: Recall@5, MRR@5, hybrid vs dense-only (PI 4.1)
4.3. Đánh giá câu trả lời: độ đúng, grounding, hành vi hỏi lại/từ chối (PI 4.1)
4.4. Hiệu năng và chi phí: latency, số lượt gọi model, token; trước/sau True Agent (PI 4.1)
4.5. Triển khai: Docker Compose, Caddy, CI, bảo mật (PI 4.2)
4.6. Hướng dẫn cài đặt và sử dụng (PI 4.2)
4.7. Hạn chế và hướng phát triển
