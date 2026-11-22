# IndexBeast — Công việc TV1 và TV3

**Nhóm 4 Hollows · Cập nhật 09/11/2026**

README này theo dõi toàn bộ công việc của TV1 và TV3 qua 6 sprint, gồm các thẻ trong kế hoạch, phần phát sinh đã triển khai và backlog có điều kiện. Mã thẻ dùng để đối chiếu với kế hoạch gốc. Mốc **đã triển khai** ghi nhận tính năng hoặc kết quả có trong repo. Mốc **một phần** chỉ rõ phần còn thiếu để nghiệm thu. Mốc **kế hoạch** ghi việc cần làm tiếp. [Kế hoạch 6 sprint](../docs/03_SPRINT_PLAN.md) · [SRS hiện hành](../docs/02_SRS.md) · [Handover theo ngày](../docs/handover/README.md)

<a name="tv1-hoanbucon"></a>

## TV1 — Hoanbucon · Tech Lead, Backend & DevOps

TV1 phụ trách nền tảng chạy chung, API cho web và Discord, cơ sở dữ liệu, bảo mật, triển khai và phát hành. Xuyên suốt các sprint, TV1 review các thay đổi ảnh hưởng contract API, migration, CI và môi trường dùng chung.

### Sprint 1–3 · Nền tảng, API và MVP

| Thẻ | Công việc | Tiến độ và đầu ra |
| --- | --- | --- |
| 1.2 | Monorepo và quy ước code | Đã có cấu trúc repo, quy trình nhánh/PR và cấu hình phát triển. Cần xác nhận branch protection trên GitHub khi nghiệm thu. |
| 1.3 | Docker Compose cho dev | Đã có PostgreSQL, Qdrant, Redis và lệnh Make để chạy môi trường chung. |
| 1.4 | FastAPI skeleton | Đã có health check, lifecycle, cấu hình môi trường và log theo request. |
| 1.5 | CI GitHub Actions | Đã có workflow kiểm backend, build web và kiểm kiểu Discord bot. |
| 2.1 | Schema PostgreSQL và migration | Đã triển khai Alembic và có ghi nhận chạy migration trên PostgreSQL. |
| 2.2 | OpenAPI v1 và mock | Đã có contract JSON/SSE, mode mock và schema để TV3, TV4 tích hợp. |
| 2.3 | Xử lý lỗi và logging | Đã chuẩn hóa mã lỗi, request ID và log JSON để truy vết. |
| 3.1 | Nối pipeline vào API chat | Đã có `/api/v1/chat` và `/api/v1/chat/stream` chạy qua service dùng chung. |
| 3.2 | Trace từng bước | Đã có trace lưu qua PostgreSQL khi dùng persistence tương ứng, API admin và công cụ xem trace. Khi chạy chế độ bộ nhớ, trace mất khi tiến trình khởi động lại. |
| 3.3 | Staging VPS | Một phần. Đã chuẩn bị Compose, Caddy và script bootstrap/deploy/đo tài nguyên. Cần chạy trên VPS thật và ghi nhận CPU/RAM, health và smoke test. |

Phần phát sinh gồm sửa xử lý bảng thông tin để giữ thông số, hỗ trợ di chuyển artifact giữa các máy, viết runner pipeline dữ liệu, thêm `make env` và chọn Python từ venv, cập nhật SRS/tech stack, xử lý các điểm review bảo mật, và bổ sung trang admin xem trace. Runner chọn artifact theo luồng Sprint 2. Khi dùng bundle dữ liệu mới của TV2, cần xác nhận đường dẫn và phiên bản đầu vào trước khi chạy. [Sprint 1](../docs/handover/2026-10-26_s1-tv1_bao-cao-ban-giao-sprint-1.md) · [Sprint 2](../docs/handover/2026-10-31_s2-tv1_bao-cao-ban-giao-sprint-2.md) · [Runner dữ liệu](../docs/handover/2026-11-02_s3-tv1_script-pipeline-du-lieu.md) · [Trace và admin](../docs/handover/2026-11-08_s3-tv1_trace-rag-postgres-va-admin.md) · [Staging](../docs/handover/2026-11-08_s3-tv1_staging-vps.md)

### Sprint 4–6 · Hoàn thiện backend, production và bàn giao

| Thẻ | Công việc | Phần còn lại và cách nghiệm thu |
| --- | --- | --- |
| 4.1 | Xác thực client, CORS, bảo vệ admin | Một phần. Đã có service token và bảo vệ admin. Kiểm lại CORS theo môi trường, quyền của web/bot/admin và phản hồi 401/403 cho các trường hợp thiếu hoặc sai quyền. |
| 4.2 | Rate limit Redis | Một phần. Đã có giới hạn theo IP hoặc định danh bot. Kiểm thử 429, `Retry-After` và các giới hạn trên staging. |
| 4.3 | Feedback và conversations | Một phần. Có contract hội thoại và kiểm quyền. Route feedback hiện kiểm tra yêu cầu và trả 204. Hoàn thiện lưu rating, kiểm lại bằng lần đọc dữ liệu đã lưu và phối hợp TV4 kiểm contract. |
| 4.4 | Kiểm thử tích hợp pipeline | Kế hoạch. Chạy LLM giả với PostgreSQL/Qdrant thật trong CI, kiểm JSON/SSE, lưu hội thoại và lỗi phụ thuộc. Ghi kết quả coverage theo mục tiêu ≥60% trong kế hoạch. |
| 5.1 | Production và HTTPS | Kế hoạch. Chốt cấu hình Caddy, TLS, health check, giới hạn tài nguyên, restart policy và quản lý secret. Nghiệm thu qua URL production với web/bot. |
| 5.2 | Script triển khai | Kế hoạch. Kiểm quy trình deploy, migration và rollback trên môi trường có thể thử lại. Ghi phiên bản được deploy và các bước quay lui. |
| 5.3 | Backup và monitoring | Kế hoạch. Backup PostgreSQL hằng ngày giữ 7 bản, snapshot Qdrant hằng tuần và thử restore. Theo dõi sức khỏe dịch vụ và tài nguyên. |
| 6.2 | Bug bash và đóng băng release | Kế hoạch. Gom lỗi UAT từ cả nhóm, xử lý Critical/High, chạy lại smoke test và chốt phiên bản demo. |
| 6.3 | Rà soát bảo mật | Kế hoạch. Rà secret, phụ thuộc, quyền bot, admin, CORS, rate limit và log. Ghi lỗi còn mở cùng mức độ. |
| 6.4 | Release v1.0 | Kế hoạch. Chốt changelog, README, tag `v1.0.0` và GitHub Release theo quy trình nhánh của nhóm. |

**Việc xuyên suốt và backlog.** TV1 duy trì CI, review PR và phối hợp chốt contract khi schema, SSE, citations, ảnh hoặc luồng hỏi bổ sung thay đổi. Mẫu `CHANGE-REQ` dùng để ghi yêu cầu mới, người phụ trách và ảnh hưởng tới sprint. [Quy ước Git](../docs/quy_uoc.md) · [Kế hoạch và backlog](../docs/03_SPRINT_PLAN.md)

<a name="tv3-minhmuc"></a>

## TV3 — MinhMuc · AI/RAG Engineer

TV3 phụ trách truy xuất, sinh câu trả lời, Agent, prompts, trích dẫn và đánh giá chất lượng. Các tác vụ cũ cần đọc cùng SRS và phạm vi hiện hành. Corpus có thể chứa base game và Shadow of the Erdtree. Câu hỏi gameplay được hỗ trợ theo chính sách hiện tại, đồng thời giữ nhãn release và độ chắc chắn của từng nguồn.

### Sprint 1–3 · Baseline, indexing, retrieval và Agent

| Thẻ | Công việc | Tiến độ và đầu ra |
| --- | --- | --- |
| 1.9 | Notebook RAG baseline | Đã chạy 240 dòng giáp với 10 câu gồm 5 VI và 5 EN. Baseline dùng multilingual E5 small, hybrid search và DeepSeek. Mốc 200 trang mẫu từ TV2 trong kế hoạch chưa được kiểm chứng bằng lần chạy này. |
| 1.10 | Benchmark reranker CPU | Còn mở. Chưa thấy kết quả so sánh recall và độ trễ CPU theo cùng tập câu để chốt ADR-002. |
| 1.11 | Xác nhận DeepSeek | Đã có adapter và chạy thử sinh câu trả lời. Còn cần đối chiếu thinking/non-thinking, JSON, cache và độ trễ theo cùng giao thức để chốt ADR-001. |
| 1.12 | Golden set v0 | Đã có 30 câu. Cần đối chiếu riêng bằng chứng đóng góp theo thành viên nếu nghiệm thu tiêu chí này. |
| 2.7 | Fanapis vào bảng `entities` | Còn mở. Luồng hiện ở mức stub hoặc hoãn theo SRS. Xác nhận lại nhu cầu trước khi mở rộng nguồn riêng. |
| 2.8 | Embedding và indexing vào Qdrant | Đã có E5 small ONNX, dense 384 chiều cosine, sparse BM25/IDF, ID ổn định, batch upsert và CLI `python -m ingest index`. Có báo cáo đo thời gian index toàn bộ corpus Sprint 2. |
| 2.9 | Hybrid retrieval | Đã có Qdrant Query API prefetch dense/sparse, fusion RRF, top-N cấu hình, metadata filters và kiểm thử. Benchmark Sprint 2 sau warm-up ghi median 31,9 ms và p95 57,9 ms cho retrieval. |
| 2.10 | Golden set v1 | Đã mở rộng lên 60 câu, bổ sung SotE, ngoài phạm vi và độ khó. Theo dõi review chéo của TV2 theo từng câu. |
| 3.7 | Rewrite và dịch truy vấn | Đã có rewrite VI/EN, truy vấn độc lập cho câu hỏi nối tiếp và giữ ngôn ngữ trả lời theo yêu cầu của người dùng. |
| 3.8 | Reranker service | Hoãn cross-encoder. Cấu hình hiện dùng `NoReranker`. Agent đánh giá độ đủ bằng chứng ở bước riêng. |
| 3.9 | Generation, prompt và citations | Đã tích hợp DeepSeek, chọn và kiểm nguồn, xử lý output JSON, luồng trả lời JSON/SSE và cách diễn đạt trực tiếp trong nội dung trả lời. |
| 3.10 | Script đánh giá retrieval | Một phần. Đã có benchmark và trace chẩn đoán. Cần chuẩn hóa nhãn liên quan, vị trí top-k và báo cáo tái lập để tính chỉ số chính thức. |

Phần phát sinh gồm truy vấn tiếng Anh cho câu hỏi tiếng Việt, semantic recall cho hội thoại, Agent có giới hạn bước và hỏi bổ sung bằng câu trả lời tự do, Tavily `off`/`auto`/`always`, chọn evidence và ảnh theo thực thể, tính phân bổ chỉ số khi có đủ dữ kiện, tư vấn gameplay và so sánh. Golden set đã mở rộng lên **100 câu, 64 VI và 36 EN**. Đợt chẩn đoán live gần nhất lấy **25 câu**, có **24 HTTP 200**, **21 câu có nguồn** và **1 lỗi 502** ở `IB-GS-086`. Báo cáo ghi nhận replay offline qua được khi khôi phục dấu phẩy trong `Leyndell, Ashen Capital`. Cần chạy lại trên API sau khi sửa guard. [Baseline](../docs/handover/2026-10-26_s1-tv3_rag-baseline-va-golden-set.md) · [Index](../docs/handover/2026-10-30_s2-tv3_do-thoi-gian-index-toan-bo.md) · [Độ trễ retrieval](../docs/handover/2026-10-31_s2-tv3_do-tre-retrieval.md) · [Tavily](../docs/handover/2026-11-04_s3-tv3_tavily-web-search.md) · [Agent và memory](../docs/handover/2026-11-06_s3-tv3_agent-va-semantic-memory.md) · [Evidence, ảnh và build](../docs/handover/2026-11-07_s3-tv3_evidence-anh-va-build-tong-quat.md) · [So sánh và hỏi bổ sung](../docs/handover/2026-11-09_s3-tv3_so-sanh-va-hoi-bo-sung.md) · [Golden set](eval/golden_set.jsonl) · [Báo cáo 25 câu](../docs/testing/2026-11-09_golden-25-by-difficulty/README.md)

### Sprint 4–6 · Đánh giá, tối ưu và nghiệm thu

| Thẻ | Công việc | Phần còn lại và cách nghiệm thu |
| --- | --- | --- |
| 4.9 | Eval câu trả lời | Chốt rubric correctness, faithfulness và hành vi theo nhóm câu. Đối chiếu LLM-as-judge với 30 câu được chấm tay theo kế hoạch. Lưu `eval_runs` và báo cáo kèm Git SHA, corpus, cấu hình, kết quả và người review. |
| 4.10 | Tối ưu retrieval | Gắn nhãn nguồn hoặc chunk đúng cho từng câu theo phiên bản corpus. Ghi thứ hạng ứng viên, tính Precision/Recall/MRR@5 và đối chiếu mục tiêu Recall@5 ≥0,80. Đo tác động của aliases, fusion, top-N và top-K. Tách kết quả retrieval khỏi tập evidence cuối của Agent. |
| 4.11 | Guardrails | Kiểm ít nhất 10 tình huống injection, ngoài phạm vi và giả thuyết theo kế hoạch. Bổ sung regression cho citation sai, dấu câu trong tên địa danh, thiếu evidence và lượt hỏi bổ sung. Kiểm riêng lore và gameplay để tránh từ chối nhầm. |
| 5.7 | Load test và độ trễ | Đo 20/50 người dùng đồng thời bằng Locust, p95 đầu-cuối và theo tầng. Dùng kết quả để điều chỉnh ONNX, top-N và giới hạn song song. Chỉ bật cache truy vấn lặp sau khi kiểm tra cách ly hội thoại và tính đúng của cache key. |
| 5.8 | Chi phí LLM và công cụ | Ghi số lượt DeepSeek/Tavily, token, cache hit và chi phí theo truy vấn/ngày. Kiểm soát ngân sách context và vòng lặp. So sánh `off`/`auto`/`always` trên cùng tập câu để thấy khi nào web search có ích. |
| 5.9 | Eval trên cấu hình production | Chạy lại tập chấm Sprint 4 với phiên bản corpus, model và cấu hình production đã ghi. So sánh chất lượng, lỗi, độ trễ và chi phí. |
| 6.8 | Eval cuối và báo cáo chất lượng | Tổng hợp xu hướng theo sprint, độ khó, ngôn ngữ và nhóm câu. Nêu tỉ lệ lỗi, mẫu bị loại và các trường hợp điển hình. |
| 6.9 | Sửa lỗi câu trả lời từ UAT | Tái hiện lỗi từ feedback và trace, sửa theo từng tầng rồi chạy lại ca lỗi cùng các ca lân cận. Ưu tiên questline, route/progression, build, vũ khí và mechanics theo kết quả UAT. |
| 6.10 | Tài liệu kiến trúc RAG/Agent | Đồng bộ sơ đồ, tài liệu thiết lập và eval với phiên bản phát hành. Mô tả dữ liệu, indexing, bộ nhớ, routing, search, evidence, citations và giới hạn hiện có. |

**Backlog có điều kiện.** Tách câu hỏi thành truy vấn con (`FR-RET-07`) khi eval cho thấy lỗi đáng kể ở câu đa bước. Hoàn thiện ẩn spoiler theo người dùng/guild (`FR-GEN-08`) khi corpus có nhãn đủ dùng và web/bot đã thống nhất cách hiển thị. [Kế hoạch và backlog](../docs/03_SPRINT_PLAN.md)

## Điểm phối hợp giữa TV1 và TV3

- **Mốc chung của cả nhóm.** Hai thành viên cùng tham gia kickoff (1.1), review/retro (1.16, 2.14, 4.15, 5.13), demo MVP nội bộ (3.14) và demo cuối kỳ (6.14). TV1 phụ trách phần vận hành và phát hành khi demo. TV3 chuẩn bị ca kiểm thử, kết quả và phân tích lỗi. [Kế hoạch sprint](../docs/03_SPRINT_PLAN.md)
- **Dữ liệu và index.** TV1 xác nhận môi trường và quyền truy cập. TV2 cung cấp artifact cùng manifest. TV3 chạy validation, index vào collection riêng và so sánh kết quả trước khi đề xuất đổi collection demo. Artifact dữ liệu structured nằm ngoài các file Git được bàn giao, nên các máy cần nhận đúng bundle trước khi chạy. [Handover dữ liệu của TV2](../docs/handover/2026-11-09_s3-tv2_tai-tao-facts-clean-chunk-tu-raw.md)
- **API và giao diện.** TV1 chốt contract và cung cấp trace theo request ID. TV3 chịu trách nhiệm logic trả lời, citations, ảnh và yêu cầu bổ sung. TV4 tích hợp contract trên web/Discord và kiểm hiển thị với hai người phụ trách. [Kiến trúc pipeline](../docs/indexbeast-system-pipeline.md)
- **Demo và release.** TV1 chốt bản triển khai và cách rollback. TV3 cung cấp kết quả eval có phiên bản corpus và cấu hình. Khi triage lỗi, đối chiếu request ID với trạng thái từng tầng thay vì suy ra từ HTTP status. [Hướng dẫn eval](eval/README.md)

## Meta-prompt cập nhật README

> **Vai trò.** Bạn là kỹ sư hỗ trợ nhóm 4 Hollows, phụ trách cập nhật README backend cho TV1 Hoanbucon và TV3 MinhMuc.
>
> **Ngữ cảnh.** Đọc kế hoạch sprint, SRS, Git trạng thái hiện tại, mã nguồn, handover và báo cáo kiểm thử. Đối chiếu toàn bộ lịch sử, sprint hiện tại, các sprint còn lại và backlog theo mã thẻ. Ghi nhận công việc phát sinh của đúng người phụ trách.
>
> **Ràng buộc.** Tách rõ đã triển khai, một phần, còn mở và kế hoạch. Dẫn bằng chứng cho kết quả thực tế. Với số đo, ghi tập dữ liệu, phiên bản và phạm vi phép đo. Giữ phân công TV2/TV4 trong mục phối hợp. Chỉ cập nhật tài liệu local và giữ nguyên dữ liệu, cấu hình thật, lịch sử Git.
>
> **Đầu ra.** Cập nhật `backend/README-TV1-TV3.md` bằng Markdown UTF-8. Tách hai phần theo thành viên, có mã thẻ, đầu ra đã có, tiêu chí nghiệm thu còn lại và việc cần phối hợp. Cập nhật handover nếu áp dụng, kiểm link và báo cáo ngắn các file đã sửa cùng giới hạn của bằng chứng.
