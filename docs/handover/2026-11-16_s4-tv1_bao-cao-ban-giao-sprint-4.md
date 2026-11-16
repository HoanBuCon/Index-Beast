# Báo cáo bàn giao Sprint 4 — IndexBeast (nhóm 4 Hollows)

| | |
|---|---|
| Sprint | 4 — *Chất lượng & hoàn thiện tính năng*, kết thúc tuần 09–16/11/2026. **Đã đóng phần phát triển; chưa release** |
| Ngày lập | 16/11/2026 (Asia/Saigon) |
| Người lập | TV1 (Quỷ Tháng 5 Khóc), Tech Lead |
| Căn cứ | `develop` tại `65a9b73` (sau PR #107), CI trên commit này: success. 15 handover S4 trong [`docs/handover/`](README.md), báo cáo trong [`docs/testing/`](../testing/) và [`docs/evaluation/`](../evaluation/), [kế hoạch](../../planning/sprint_plan.json). Mã nguồn đọc qua đồ thị GitNexus (index tại `65a9b73`: 672 file, 7.060 nút, 306 luồng) và kiểm lại bằng lệnh. **Chưa đối chiếu Trello thật** |
| Cách đọc | Mục 2 chấm 6 mục tiêu Sprint 4 do chủ dự án giao; mục 3 chấm thẻ trong `sprint_plan.json`. Kết luận: **Đạt**, **Đạt một phần**, **Chưa đạt** |

## 1. Tóm tắt

- **Pipeline RAG đã hoàn thiện và đo được** (cấp đo giải thích ở mục 4.0): chỉ truy xuất (C1), Hybrid + rewrite trên corpus S4 (34.070 điểm EN) đạt **Recall@5 90,34%, MRR@5 0,767**; truy xuất + sinh một lượt (C2) đạt **Accuracy 160/195 (82,05%)**; Agent đầy đủ qua API (C3) với DeepSeek + Tavily Auto chạy 100 ca, 111/111 request HTTP 200, **Accuracy lượt đầu 76/83 (91,57%)**. Chưa có đợt nào qua giao diện web hay Discord với người dùng thật (C4). Vượt mục tiêu kế hoạch (Recall@5 ≥ 0,80, correctness ≥ 70%). **Người chấm là AI** (Codex, DeepSeek), chưa có người chấm độc lập.
- **Dữ liệu wiki đủ**: 4.164 trang, 39.574 chunk (34.070 EN), có `spoiler_level`, `game_scope`, đã index hybrid và kiểm bộ lọc.
- **Đăng nhập: backend xong, giao diện chưa nối.** Backend Discord OAuth (TV1) đã merge; trang đăng nhập web (TV4) chỉ là giao diện, nút Google/Discord báo "chưa sẵn sàng". GitNexus xác nhận 6 endpoint `/auth/*`, `/me/*` **chưa có client nào gọi**. Chưa thử với Discord thật.
- **Golden set 200/400 câu**, review do AI thực hiện theo ủy quyền TV2 (198 duyệt, 2 cần sửa).
- **Release v2 chưa làm**: không có tag, `develop` hơn `main` 91 commit. Việc release do TV1 quyết định.
- **12 PR S4** (#95–#107; #101 mở nhầm vào `main` và đã đóng) đã merge: TV3 6, TV1 3, TV2 2, TV4 1. **0/12 PR có lượt review** trên GitHub.

## 2. Mục tiêu Sprint 4 của chủ dự án

| # | Mục tiêu | Phụ trách | Kết luận | Bằng chứng và giải thích |
|---|---|---|---|---|
| 1 | Hoàn thiện toàn bộ dữ liệu wiki (~4.100 trang) | TV2 | **Đạt** | 4.164 tài liệu, 39.574 chunk, 1.543 mục review; đối chiếu S3→S4 giữ đủ 74.840 bộ định vị nguồn và 45.204 fact ID ([handover](2026-11-12_s4-tv2_wiki-quality.md)). Re-index hybrid 34.070 chunk EN, mọi point có vector `dense` + `bm25`; bộ lọc `spoilers=false` trả đúng 33 chunk mức 0 ([kiểm chứng](2026-11-13_s4-tv2_hybrid-verification.md)). Collection chính thức cho bản phát hành **chưa được chốt** (mặc định cấu hình vẫn `lore_chunks`; các lượt đo dùng `indexbeast_s4_wiki_ca98c06b`) |
| 2 | Golden set 400 câu, 3 mức suy luận, 2 ngôn ngữ (200 mỗi ngôn ngữ) | TV3 | **Đạt một phần** | `backend/eval/golden_set.jsonl` có **200 câu**: VI 110 / EN 90; dễ 60 / trung bình 90 / khó 50; thêm 12 câu bổ sung cân bằng. Thiếu 200 câu so với mục tiêu và lệch tỷ lệ ngôn ngữ. Rà soát: 198 `approved`, 2 `changes_requested` (IB-GS-265, IB-GS-279); **do Codex thực hiện thay TV2** (`human_direct_review=false`) ([handover](2026-11-16_s4-tv2_ra-soat-golden-local.md)). Gate `--require-reviewed` chưa đạt |
| 3 | Chốt pipeline RAG/LangGraph | TV3 | **Đạt** | Agent thích ứng: `check_name` sửa tên gõ sai, lập 2–4 mục tiêu cho câu phức hợp (`task_plan.py`), giữ bằng chứng qua lượt hỏi bổ sung, Auto kiểm độ phủ trước khi trả lời ([handover](2026-11-13_s4-tv3_adaptive-agent.md)); nối lượt hỏi đường bằng mốc tiến độ ([handover](2026-11-14_s4-tv3_progress-clarification.md)); cập nhật điều kiện khi người dùng đổi yêu cầu ([handover](2026-11-14_s4-tv3_superseded-constraints.md)); trợ lý chơi game nhiều nguồn ([handover](2026-11-14_s4-tv3_gameplay-multi-source.md)). Còn lỗi đã biết: hai lượt 502 trong thử điều kiện bị thay (SC03, SC04) đã có bản sửa nhưng chưa chạy thật lại |
| 4 | Đo Accuracy, Recall | TV3 | **Đạt** | Ma trận 6 cấu hình × 212 câu, Tavily Off ([báo cáo](../testing/2026-11-14_s4-retrieval-matrix.md)): Hybrid + rewrite tốt nhất (bảng mục 4). Chạy lại 100 ca với Agent đầy đủ ([báo cáo](../testing/2026-11-14_s4-retest-100.md)). Hai báo cáo **dùng tập, luồng và người chấm khác nhau**, không so trực tiếp ([handover](2026-11-15_s4-tv3_danh-gia-rag.md)) |
| 5 | Auth service (đăng nhập, chuẩn bị deploy cloud S5) | TV1, TV4 | **Đạt một phần** | **Backend đạt**: Discord OAuth2 + PKCE, phiên cookie `httpOnly` lưu băm, hội thoại gắn tài khoản, nhận lại hội thoại khách, admin theo Discord ID, migration `0004`, đã review và gia cố ([bàn giao](2026-11-13_s4-tv1_bao-cao-ban-giao.md), [review](2026-11-13_s4-tv1_review-va-sua-loi.md), [hợp đồng](../api/auth-tv4.md)). **Web chưa nối**: trang `/login` của TV4 có nút Google/Discord nhưng chỉ hiện thông báo, không gọi `/auth/discord/login`, không đọc `/auth/me` ([handover](2026-11-14_s4-tv4_giao-dien-dang-nhap-google-discord.md)). **Google không có backend** và không nằm trong ADR-005. ADR-005 vẫn ở trạng thái "đề xuất" |
| 6 | Đóng gói hệ thống, PR vào `main`, release v2 | TV1 | **Chưa đạt** | Không có tag hay GitHub Release; `develop` hơn `main` 91 commit. Chưa có CHANGELOG, hướng dẫn nâng cấp từ v1 (migration 0002–0004, biến môi trường mới). Theo chỉ đạo, việc release do TV1 quyết định |

## 3. Thẻ trong kế hoạch (`sprint_plan.json`)

Mục tiêu kế hoạch ban đầu (golden set 120 câu, Recall@5 ≥ 0,80, correctness ≥ 70%) đã được thay bằng các mục tiêu ở mục 2. Bảng dưới chỉ ghi các thẻ còn ý nghĩa.

| Thẻ | Phụ trách | Kết luận | Ghi chú |
|---|---|---|---|
| Xác thực client, CORS, bảo vệ admin | TV1 | **Đạt** | Service token cho bot; CORS theo `CORS_ORIGINS` có test; `/admin/*` cần token hoặc phiên admin; test 401/403. Không làm token riêng cho web (cố ý: bí mật trong trình duyệt không bảo vệ được gì) |
| Rate-limit bằng Redis | TV1 | **Đạt một phần** | IP (web), `external_ref` (bot), 429 + `Retry-After`, `.env`, giới hạn độ dài câu hỏi. Trần theo server Discord đã có ở backend (`guild_id`, PR #98) nhưng **bot chưa gửi `guild_id`** nên chưa có tác dụng |
| API feedback & conversations | TV1 | **Đạt** | `POST /feedback` lưu PostgreSQL, `GET /conversations/{id}`, `/me/conversations` |
| Test tích hợp pipeline | TV1 | **Đạt** | E2E với Qdrant + PostgreSQL thật, LLM giả; CI chạy integration; coverage `app/rag` ≥ 60% có cổng trong CI |
| Gắn `spoiler_level`, chuẩn hóa `game_scope` | TV2 | **Đạt** | Mẫu 50 trang; 33/38.505/1.036 chunk mức 0/1/2. Lưu ý mục 5.3 về chính sách spoiler |
| Golden set v2, sửa dữ liệu theo lỗi eval | TV2, TV3 | **Đạt** | Thay bằng mục tiêu 200/400 câu ở mục 2 |
| Tìm web dự phòng DuckDuckGo | TV2 | **Bỏ** | Đã thay bằng Tavily từ S3 |
| Eval LLM-as-judge, tối ưu retrieval | TV3 | **Đạt** | Ma trận E5/BM25/Hybrid × gốc/rewrite; `eval_runs` lưu lượt đo. Chưa kiểm tay 30 câu theo checklist để xác nhận judge |
| Guardrails | TV3 | **Đạt một phần** | 17/17 ca hành vi (từ chối, hỏi lại) đạt. Chưa thấy bộ 10 câu prompt injection riêng |
| Web: feedback, lịch sử, câu hỏi gợi ý, popover | TV4 | **Đạt một phần** | Bảng hỏi bổ sung hiện câu hỏi động ([handover](2026-11-14_s4-tv4_cau-hoi-va-hai-nut-bo-sung.md)). Component `FeedbackButtons` có sẵn nhưng **không được gắn vào giao diện** (không file nào render nó), nên web không gửi 👍/👎 |
| Bot: thread + nút feedback | TV4 | Không đổi trong S4 | Đã có từ S3; 33 test bot đạt |
| Sprint 4 Review & Retro | ALL | Chưa ghi nhận | Không có tài liệu retro hay quyết định model LLM cuối cùng trong repo |

## 4. Số đo trong Sprint 4

Mọi số dưới đây lấy nguyên từ báo cáo và handover đã merge; **chưa có lượt nào do người chấm độc lập**. Người chấm ghi ở từng bảng. Báo cáo thô nằm trong `backend/data/research_runs/` trên máy người chạy (Git bỏ qua). Mã `IB-GS-*` là golden set S4, `IB-BL-*` là 25 ca chẩn đoán, `IB-SUP-*` là 12 câu bổ sung.

### 4.0 Các cấp đo

Mỗi số đo thuộc một cấp. Số ở cấp khác nhau **không so trực tiếp được**: cấp càng cao thì càng nhiều thành phần tham gia (và càng nhiều chỗ có thể sai).

| Cấp | Tên | Đi qua những gì | Không đi qua | Gọi API thật | Đo được |
|---|---|---|---|---|---|
| **C0** | Kiểm dữ liệu offline | Đọc artifact: đếm, so quote với chunk, hash | Retriever, LLM | Không | Số trang/chunk, nhãn, quote khớp |
| **C1** | Chỉ truy xuất | Câu hỏi (nguyên văn hoặc đã rewrite) → encoder → Qdrant (E5, BM25 hoặc Hybrid RRF) → xếp hạng top 5 trang | Agent, generator, Tavily | Không (encoder local) | Recall@5, MRR@5, context chunk recall |
| **C2** | Truy xuất + sinh một lượt (harness) | `agent.decide()` (ý định, rewrite) → một lần truy xuất → chọn ngữ cảnh → `generator.generate()` → LLM chấm. Bản Auto thêm tối đa một lượt Tavily Search + Extract | Vòng lặp công cụ của Agent, bộ nhớ hội thoại, API HTTP, PostgreSQL | DeepSeek (+ Tavily ở Auto) | Accuracy, bám nguồn, ảnh hưởng của retriever và rewrite |
| **C3** | Agent đầy đủ qua API | `create_app()` thật, gọi `POST /api/v1/chat` và `/chat/stream` (JSON và SSE) qua `httpx.ASGITransport` trong cùng tiến trình: middleware, guard, Agent quyết định, vòng lặp công cụ (`check_name`, tìm local, Tavily Auto), assessor, generator, kiểm trích dẫn, lưu PostgreSQL, hỏi bổ sung nhiều lượt | Máy chủ HTTP thật (uvicorn, Caddy), giao diện web, bot Discord, người dùng thật | DeepSeek + Tavily | Accuracy cuối, hành vi, bám nguồn, HTTP 200/502, độ trễ, số lượt gọi |
| **C4** | End-to-end với người dùng | Web hoặc Discord thật, qua mạng, người thật thao tác | — | — | **Chưa có đợt nào trong S4** |

Ngoài ra có **kiểm thử phần mềm** (mục 4.8): unit test dùng LLM và retriever giả; integration test dùng PostgreSQL, Qdrant, Redis thật nhưng LLM và encoder giả. Các test này chứng minh mã chạy đúng, **không đo chất lượng câu trả lời**.

Hệ quả cần nhớ khi trình bày:

- **Recall@5 và MRR@5 chỉ có ở C1.** Ở C3, trace chưa ghi đủ danh sách truy xuất có thứ hạng nên chưa tính được Recall của Agent đầy đủ.
- **Accuracy có ở hai cấp:** C2 (ma trận, 160/195 = 82,05%, DeepSeek chấm) và C3 (100 ca, 76/83 = 91,57%, Codex chấm). Hai con số khác tập câu, khác luồng và khác người chấm.
- **Không có số nào ở C4.** Chưa thử qua giao diện web, bot Discord thật hay máy chủ đã deploy.

### 4.1 Tổng hợp theo thời gian

| Ngày | Đợt đo | Cấp | Người chạy | Tập | Kết quả chính | Nguồn |
|---|---|---|---|---|---|---|
| 12/11 | Dữ liệu wiki S4, đo lại local FTS5/E5 | C0 + C1 | TV2 | 25 câu golden cũ + 6 truy vấn bằng chứng | 4.164 trang, 39.574 chunk; source top 5 qua E5: 19/25 ở cả S3 và S4 | [handover](2026-11-12_s4-tv2_wiki-quality.md) |
| 13/11 | Re-index hybrid + eval qua API | C1 (20/22, 6 truy vấn) + C3 (25 câu API) | TV2 | 25 câu golden cũ | 34.070 point; 20/22 trang đúng ở top 5; 25/25 HTTP 200 | [handover](2026-11-13_s4-tv2_hybrid-verification.md) |
| 13/11 | Agent thích ứng, chạy thật | C3 | TV3 | 5 ca chẩn đoán | 5/5 HTTP 200 | [handover](2026-11-13_s4-tv3_adaptive-agent.md) |
| 14/11 | Hỏi đường theo tiến độ, chạy thật | C3 | TV3 | 6 lượt | 2 hội thoại SSE thành công, 1 ca 502 (đã sửa, kiểm offline) | [handover](2026-11-14_s4-tv3_progress-clarification.md) |
| 14/11 | Điều kiện bị thay, chạy thật | C3 | TV3 | 4 lượt | 2/4 HTTP 200, 2/4 HTTP 502 (đã sửa, kiểm offline) | [handover](2026-11-14_s4-tv3_superseded-constraints.md) |
| 14/11 | Gameplay nhiều nguồn, chạy thật | C3 | TV3 | 5 ca | 5/5 có câu trả lời cuối sau sửa | [handover](2026-11-14_s4-tv3_gameplay-multi-source.md) |
| 14/11 | Baseline S4 + chạy lại sau sửa | C3 | TV3 | 25 ca chẩn đoán | 25/25 phản hồi cuối, 27/27 HTTP 200 | [báo cáo](../testing/2026-11-14_s4-baseline-25.md) |
| 14/11 | Đánh giá 100 ca (trước sửa) | C3 (Accuracy) + C1 (Recall 83 câu) | TV3, Codex chấm | 100 ca từ golden S4 | Accuracy 71/83 (85,54%) | [báo cáo](../testing/2026-11-14_s4-evaluation-100.md) |
| 14/11 | Nghiệm thu 100 ca (sau sửa) | C3 | TV3, Codex chấm | cùng 100 ca | Accuracy 76/83 (91,57%), 111/111 HTTP 200 | [báo cáo](../testing/2026-11-14_s4-retest-100.md) |
| 14/11 | Ma trận truy xuất 6 cấu hình | C1 (Recall, MRR) + C2 (Accuracy, bám nguồn) | TV3, DeepSeek chấm | 212 câu | Hybrid + rewrite: Recall@5 90,34%, Accuracy 82,05% | [báo cáo](../testing/2026-11-14_s4-retrieval-matrix.md) |
| 16/11 | Rà soát golden set | C0 | Codex thay TV2 | 200 câu | 198 duyệt, 2 cần chỉnh; 256 lượt quote khớp corpus | [báo cáo](../evaluation/2026-11-16_s4-tv2-local-review.md) |

Cấu hình chung của các lượt chạy thật: DeepSeek `deepseek-flash`, temperature 0,2, Tavily Auto (trừ ma trận Off), corpus `indexbeast_s4_wiki_ca98c06b` 34.070 điểm (trừ các lượt Agent ngày 13–14/11 dùng collection cũ 18.383 điểm), timeout 45 giây mỗi request.

### 4.2 Dữ liệu (TV2) — C0, C1, một đợt C3

| Số đo | Giá trị |
|---|---|
| Tài liệu / có chunk | 4.164 / 4.163 (1 trang template vào review) |
| Chunk / tiếng Anh / mục review | 39.574 / 34.070 / 1.543 |
| Đơn vị chunk có coverage, giới hạn 450 token | 39.480/39.480 |
| Giữ nguyên qua S3 → S4 | 74.840 bộ định vị nguồn, 45.204 fact ID; số chunk +23 do đổi ranh giới |
| Chunk có nhãn chặng lấy từ HTML | 40 chunk trên 18 trang |
| `release_scope` | base 767, SotE 283, mixed/SotE 366, unknown 2.748 |
| `spoiler_level` 0 / 1 / 2 | 33 / 38.505 / 1.036 chunk |
| Mẫu đọc `game_scope` | 50 trang (seed 4164), không thấy trang thuộc game khác |
| Re-index hybrid 34.070 chunk EN | 642,38 giây; mọi point có `dense` + `bm25` |
| Bộ lọc `spoilers=false` | Trả đúng 33 ID mức 0; truy vấn ending Ranni loại 30 ứng viên mức cao |
| **C1** · Hybrid trên 25 câu golden cũ | 20/22 câu có URL kỳ vọng ở top 5 (2 câu trỏ trang ngoài cohort, 3 câu hành vi không có URL) |
| **C1** · 6 truy vấn đối chiếu bằng chứng | 6/6 ở top 2 |
| **C3** · Eval qua API 25 câu (13/11) | 25/25 HTTP 200 (baseline 24/25; IB-GS-086 hết 502); 93 lượt gọi model; 519.450 token vào, 12.857 token ra; 0 lượt Tavily |

Hạng bằng chứng local trước/sau chunk lại (**C1**, 12/11, FTS5 BM25 top 16 rồi E5, không qua Qdrant):

| Ca | Token bằng chứng S3 → S4 | Hạng BM25 | Hạng E5 |
|---|---|---|---|
| IB-GS-075 | 383 → 152 | 15 → 2 | 7 → 1 |
| IB-GS-052 | 442 → 218 | 10 → 8 | 7 → 10 |
| IB-GS-065, 031, 041, 086 | không đổi | không đổi (1, 1, 1, 4) | không đổi (1, 1, 3, 3) |

### 4.3 Golden set S4 — C0

| Số đo | Giá trị |
|---|---|
| Số câu | 200 (IB-GS-101–300) + 12 câu bổ sung |
| Ngôn ngữ | Việt 110, Anh 90 |
| Độ khó | Dễ 60, trung bình 90, khó 50 |
| Loại | 183 ca dữ kiện, 17 ca hành vi, 11 lượt bổ sung |
| Rà soát (Codex thay TV2) | 198 `approved`, 2 `changes_requested` (IB-GS-265, IB-GS-279), 0 `pending` |
| 26 ca từng sửa | 25 đạt, 1 cần chỉnh |
| Quote khớp corpus | 183/183 ca dữ kiện, 11/11 lượt bổ sung, 256 lượt quote |
| Gate `--require-reviewed` | **Chưa đạt** |

### 4.4 Ma trận truy xuất (212 câu) — C1 và C2

Recall@5, MRR@5, context chunk recall là **C1**; Accuracy và bám nguồn là **C2** (một lần truy xuất rồi sinh, không có vòng lặp công cụ). Tavily Off. Mẫu số: Recall@5 và MRR@5 trên 195 câu có nguồn; context chunk recall trên 183 câu; Accuracy trên 195 câu dữ kiện; 17 ca hành vi chấm riêng (cả sáu cấu hình 17/17). 152/212 ca dùng truy vấn đã viết lại. Chấm: DeepSeek Flash, ẩn cấu hình.

| Truy xuất | Query | Recall@5 | MRR@5 | Context chunk recall | Accuracy | Bám nguồn đủ |
|---|---|---:|---:|---:|---:|---:|
| E5 | Gốc | 82,82% | 0,728 | 61,38% | 149/195 · 76,41% | 95,32% |
| E5 | Rewrite | 88,63% | 0,742 | 59,84% | 152/195 · 77,95% | 97,19% |
| BM25 | Gốc | 79,83% | 0,590 | 46,63% | 138/195 · 70,77% | 95,88% |
| BM25 | Rewrite | 87,69% | 0,690 | 55,83% | 158/195 · 81,03% | 98,90% |
| Hybrid | Gốc | 86,41% | 0,701 | 62,80% | 155/195 · 79,49% | 96,61% |
| **Hybrid** | **Rewrite** | **90,34%** | **0,767** | **64,07%** | **160/195 · 82,05%** | 98,38% |

Accuracy theo nhóm:

| Nhóm | n | E5 gốc | E5 rewrite | BM25 gốc | BM25 rewrite | Hybrid gốc | Hybrid rewrite |
|---|---:|---:|---:|---:|---:|---:|---:|
| S4 có đáp án | 183 | 78,14% | 79,23% | 71,04% | 81,42% | 80,87% | 83,06% |
| Tập bổ sung | 12 | 50,00% | 58,33% | 66,67% | 75,00% | 58,33% | 66,67% |
| Tiếng Việt | 103 | 66,99% | 70,87% | 59,22% | 78,64% | 70,87% | 78,64% |
| Tiếng Anh | 92 | 86,96% | 85,87% | 83,70% | 83,70% | 89,13% | 85,87% |
| Dễ | 59 | 86,44% | 84,75% | 81,36% | 84,75% | 88,14% | 86,44% |
| Trung bình | 87 | 82,76% | 82,76% | 72,41% | 87,36% | 86,21% | 86,21% |
| Khó | 49 | 53,06% | 61,22% | 55,10% | 65,31% | 57,14% | 69,39% |
| Tính toán | 9 | 6/9 | 7/9 | 5/9 | 5/9 | 6/9 | 7/9 |
| Lỗi gõ hoặc tên | 32 | 21/32 | 22/32 | 18/32 | 22/32 | 22/32 | 22/32 |
| Truy vấn nhiễu | 7 | 1/7 | 2/7 | 4/7 | 5/7 | 3/7 | 3/7 |
| Tiếng Việt không dấu | 8 | 0/8 | 5/8 | 5/8 | 7/8 | 3/8 | 6/8 |

Recall@5 của Hybrid khi bật rewrite: câu Việt 80,58% → 87,22%; câu khó 62,24% → 71,77%; Việt không dấu 50,00% → 93,75%. Nhóm nhiễu: Hybrid + rewrite có Recall@5 92,86% nhưng đúng 3/7, còn BM25 + rewrite đúng 5/7. TV3 đề xuất giữ **Hybrid + rewrite** làm mặc định (hơn BM25 + rewrite 2/195 câu).

**Tavily Auto (C2 + một lượt web)** trên 18 câu × 6 cấu hình (16 câu dữ kiện): 35 lượt tìm web (32 có kết quả, 3 timeout); 21/108 câu trả lời dẫn nguồn web.

| Cấu hình | Đúng đủ Off | Đúng đủ Auto | Lượt Auto có trích dẫn web |
|---|---:|---:|---:|
| E5 gốc | 10/16 | 11/16 | 3/18 |
| E5 rewrite | 10/16 | 12/16 | 3/18 |
| BM25 gốc | 8/16 | 10/16 | 6/18 |
| BM25 rewrite | 11/16 | 11/16 | 4/18 |
| Hybrid gốc | 9/16 | 11/16 | 3/18 |
| Hybrid rewrite | 12/16 | 12/16 | 2/18 |

Kiểm riêng **C3** (Agent đầy đủ qua API) trên 6 câu đại diện: 6/6 phản hồi cuối, 7/7 request HTTP 200, không gọi Tavily.

### 4.5 Agent đầy đủ trên 100 ca (Tavily Auto) — C3, kèm một phép C1

Tập: 55 Việt / 45 Anh; 30 dễ / 45 trung bình / 25 khó; có 20 ca lỗi gõ, 11 ca có lượt bổ sung, 6 ca ngoài phạm vi. 75 ca JSON, 25 ca SSE. Chấm: Codex theo [rubric S4](../evaluation/s4-rubric.md). Hai lượt dùng cùng 100 câu, trong đó có các câu từng dùng để sửa Agent, nên đây là đo hồi quy, không phải tập kiểm tra độc lập.

| Chỉ số | Trước sửa | Sau sửa |
|---|---:|---:|
| Ca có phản hồi cuối | 99/100 | **100/100** |
| Request chat HTTP 200 | 107/108 | **111/111** |
| Accuracy dữ kiện ở lượt đầu | 71/83 · 85,54% | **76/83 · 91,57%** |
| Hành vi đạt | 15/17 · 88,24% | **17/17** |
| Bám nguồn đầy đủ (trong ca có trích dẫn) | 78/89 · 87,64% | **90/94 · 95,74%** |
| Lượt bổ sung đúng đủ | 7/8 | **10/11** |
| Độ trễ theo ca p50 / p95 | 9,68 s / 20,73 s | 8,84 s / 24,73 s |
| Lượt gọi mô hình logic | 629 | 652 |
| Request Tavily / ca có nguồn web | 32 / 3 | 27 / 7 |

| Nhóm (đúng đủ) | Trước sửa | Sau sửa |
|---|---:|---:|
| Việt | 35/42 | 39/42 |
| Anh | 36/41 | 37/41 |
| Dễ | 23/25 | 23/25 |
| Trung bình | 35/38 | 38/38 |
| Khó | 13/20 | 15/20 |
| Lỗi gõ hoặc sai tên | 17/20 | chưa tách |

Sau sửa: 76 đúng đủ, 6 đúng một phần, 1 hỏi lại thừa; 7 ca tăng điểm, 2 ca giảm. Trước sửa, IB-GS-278 trả 502.

Phép **C1** đi kèm: truy xuất local trên 83 câu có trang tham chiếu (truy vấn nguyên văn, không gọi DeepSeek hay Tavily, không qua Agent):

| Nhóm | n | Recall@5 | MRR@5 |
|---|---:|---:|---:|
| Toàn bộ | 83 | 81,33% | 0,748 |
| Việt | 42 | 73,41% | 0,633 |
| Anh | 41 | 89,43% | 0,866 |
| Dễ | 25 | 92,00% | 0,810 |
| Trung bình | 38 | 92,11% | 0,792 |
| Khó | 20 | 47,50% | 0,588 |

| So sánh (83 câu, chạy lại) | E5 dense-only | E5 + BM25 (RRF) |
|---|---:|---:|
| Recall@5 | 80,32% | 82,33% |
| MRR@5 | 0,733 | 0,748 |
| Câu có ít nhất một trang đúng ở top 5 | 71/83 | 73/83 |
| Recall@5 Việt / Anh | 70,24% / 90,65% | 74,21% / 90,65% |
| Recall@5 câu khó | 43,33% | 51,67% |

### 4.6 Baseline 25 ca chẩn đoán (trước khi sửa pipeline) — C3

14 Việt / 11 Anh; mỗi ca một hội thoại mới.

| Số đo | Giá trị |
|---|---:|
| Ca có phản hồi cuối | 25/25 |
| Request HTTP 200 | 27/27 |
| Ca có trích dẫn / có trích dẫn web | 22/25 / 3/25 |
| Độ trễ p50 / p95 | 9,26 s / 22,01 s |
| Lượt gọi mô hình logic | 164 |
| Request Tavily | 14 (8 Search, 2 lỗi; 6 Extract) |

Chạy lại 5 ca lỗi sau sửa (IB-BL-001, 010, 018, 020, 023): 5/5 có trích dẫn, 6/6 HTTP 200, không gọi Tavily; p50 trên 5 ca **12,88 s → 8,44 s**. Đợt này không có Accuracy đã chấm và trace chưa đủ để tính Recall@5.

### 4.7 Các lượt chạy thật nhỏ của Agent — C3

| Đợt | Lượt | HTTP | Gọi model / Tavily | Quan sát |
|---|---|---|---|---|
| Agent thích ứng (13/11, collection 18.383 điểm) | 5 ca | 5/5 200 | 24 / 2 | Độ trễ 1,99–20,01 s; ADAPT-02 thiếu vị trí và trích dẫn, ADAPT-04 hỏi lại sớm |
| Gameplay nhiều nguồn (14/11) | 5 ca, 10 request | 5/5 có câu trả lời cuối | 54 / 4 | PLAY-02 và PLAY-04 có 502 trước khi sửa |
| Hỏi đường theo tiến độ (14/11) | 6 lượt | 2 hội thoại thành công, 1 ca 502 | không ghi | Lỗi Reduvia (`changed_numeric_constraints`) đã phát lại offline thành công |
| Điều kiện bị thay (14/11) | 4 lượt | 2/4 200 (44,36 s; 44,13 s), 2/4 502 (4,11 s; 4,35 s) | 34 / 17 | Bản sửa chỉ kiểm offline |

### 4.8 Kiểm thử phần mềm (không đo chất lượng)

| Số đo | Giá trị | Nguồn |
|---|---|---|
| Unit test backend trên `develop` `65a9b73` | **1.161 đạt**, 2 cảnh báo; ruff, format, OpenAPI khớp | Chạy trên máy TV1, 16/11 |
| Web / bot | 49 / 33 test đạt | Chạy trên máy TV1, 16/11 |
| Integration test | CI success trên `65a9b73`; máy TV1 không chạy được (Docker tắt) | GitHub Actions |
| Test e2e pipeline (Qdrant + PostgreSQL thật, LLM giả) | 3 test đạt | TV1, PR #96 |
| Coverage `app/rag` | 95% (ngưỡng CI 60%) | TV1, 13/11 |
| Đăng nhập | Có test unit và integration; chưa thử Discord thật | TV1 |
| `eval_runs` | 2 lượt `s4-auto-100-task3`, `s4-auto-100-retest` lưu trong PostgreSQL local; `/admin/stats` đọc được | [báo cáo](../testing/2026-11-14_s4-retest-100.md) |
| Vòng import (GitNexus) | 0 | Index tại `65a9b73` |

## 5. Rủi ro và nợ kỹ thuật

1. **Web chưa có đăng nhập thật và feedback.** Backend sẵn sàng nhưng không có giao diện dùng; nếu release v2 với đăng nhập thì TV4 phải nối theo [`auth-tv4.md`](../api/auth-tv4.md) và gắn `FeedbackButtons`. Nếu chưa kịp, v2 nên phát hành ở chế độ khách và ẩn nút Google/Discord.
2. **Hai video 63 MB trong Git** (`web/src/video/ELDEN_RING_login_cut.mp4`, `ELDEN_RING_muted_trimmed.mp4`, thêm ngày 14/11). Làm repo nặng thêm ~126 MB vĩnh viễn trong lịch sử, và **quyền sử dụng chưa được xác minh** (handover TV4 tự ghi). Cần quyết định trước khi public: nén/thay bằng ảnh, đưa ra ngoài Git, hoặc xác nhận quyền.
3. **Chính sách spoiler đổi ngầm.** Từ PR #100, schema chuẩn hóa mọi `options.spoilers=false` thành `true` (web và Discord luôn cho spoiler). SRS FR-GEN-08 vẫn mô tả ẩn spoiler theo cài đặt; dữ liệu `spoiler_level` của TV2 hiện không còn tác dụng với người dùng. Cần ghi quyết định vào SRS hoặc ADR.
4. **Chưa có review chéo.** 0/12 PR có review trên GitHub; golden set do AI rà soát; số đo do AI chấm. Trước khi báo cáo giảng viên, nên có người chấm tay một mẫu (checklist thẻ eval yêu cầu 30 câu).
5. **Độ phức tạp tập trung ở Agent.** `run_tools` (`backend/app/rag/tool_agent.py`) là một hàm 522 dòng, gọi 21 hàm ở 13 file (theo GitNexus); `check_decision` 127 dòng. S4 thêm ~5.800 dòng vào backend, trong đó `tool_agent.py` +423 và `agent.py` +356. Nên tách theo bước (lập kế hoạch, gọi công cụ, kiểm độ phủ) trước khi thêm tính năng mới.
6. **Cấu hình phát hành chưa chốt.** Tên collection, `CHAT_PERSISTENCE=postgres` (cần cho đăng nhập và lịch sử), `WEB_URL` HTTPS (bắt buộc ở prod khi bật đăng nhập), Redirect URL Discord, migration `0004`. `.env` trên máy TV1 còn thiếu `CHAT_AGENT_ENABLED=true` khi bật `rag` + `postgres`.

## 6. Việc cần làm trước release v2

| # | Việc | Người |
|---|---|---|
| 1 | Quyết định phạm vi v2: có đăng nhập hay chỉ khách; Google có làm không (ADR-005 chuyển "Đã duyệt" hoặc sửa) | TV1 + nhóm |
| 2 | Nối web với `/auth/*` hoặc ẩn nút; gắn `FeedbackButtons`; bot gửi `guild_id` | TV4 |
| 3 | Xử lý hai video (kích thước, quyền) | TV4 + TV1 |
| 4 | Ghi quyết định spoiler vào SRS | TV3 + TV1 |
| 5 | Sửa IB-GS-265, IB-GS-279 trong phiên bản golden mới; chấm tay mẫu 30 câu | TV2, TV3 |
| 6 | Đăng nhập Discord thật trên máy dev; chốt collection và `.env` mẫu cho prod | TV1 |
| 7 | CHANGELOG v2, hướng dẫn nâng cấp từ v1, PR `develop` → `main`, tag `v2.0.0` | TV1 (quyết định release) |
| 8 | Sprint 4 Review & Retro, chốt model LLM | ALL |

## 7. Phụ lục: PR Sprint 4

| PR | Người | Nội dung |
|---|---|---|
| #95 | TV2 | Chất lượng wiki, spoiler, eval local |
| #96, #97, #98 | TV1 | Feedback, `eval_runs`, đăng nhập Discord; gia cố sau review; CORS test và trần theo guild |
| #99, #100 | TV3 | Agent thích ứng; hỏi đường theo tiến độ, điều kiện bị thay, gameplay nhiều nguồn |
| #102 | TV4 | Giao diện đăng nhập, bảng hỏi bổ sung, dọn ảnh, video nền |
| #103 | TV3 | Tài liệu pipeline hệ thống |
| #104 | TV2 | Kiểm chứng Qdrant hybrid |
| #105, #106 | TV3 | Golden 200 câu, ma trận truy xuất, đánh giá RAG |
| #107 | TV3 (thay TV2) | Rà soát golden bằng artifact local |
