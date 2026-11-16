# Báo cáo bàn giao Sprint 4 — IndexBeast (nhóm 4 Hollows)

| | |
|---|---|
| Sprint | 4 — *Chất lượng & hoàn thiện tính năng*, kết thúc tuần 09–16/11/2026. **Đã đóng phần phát triển; chưa release** |
| Ngày lập | 16/11/2026 (Asia/Saigon) |
| Người lập | TV1 (Quỷ Tháng 5 Khóc), Tech Lead |
| Căn cứ | `develop` tại `65a9b73` (sau PR #107), CI trên commit này: success. 15 handover S4 trong [`docs/handover/`](README.md), báo cáo trong [`docs/testing/`](../testing/) và [`docs/evaluation/`](../evaluation/), [kế hoạch](../../planning/sprint_plan.json). Mã nguồn đọc qua đồ thị GitNexus (index tại `65a9b73`: 672 file, 7.060 nút, 306 luồng) và kiểm lại bằng lệnh. **Chưa đối chiếu Trello thật** |
| Cách đọc | Mục 2 chấm 6 mục tiêu Sprint 4 do chủ dự án giao; mục 3 chấm thẻ trong `sprint_plan.json`. Kết luận: **Đạt**, **Đạt một phần**, **Chưa đạt** |

## 1. Tóm tắt

- **Pipeline RAG đã hoàn thiện và đo được**: Hybrid + rewrite trên corpus S4 (34.070 điểm EN) đạt **Recall@5 90,34%, MRR@5 0,767, Accuracy 160/195 (82,05%)**; Agent đầy đủ với DeepSeek + Tavily Auto chạy 100 ca, 111/111 request HTTP 200, Accuracy lượt đầu 76/83 (91,57%). Vượt mục tiêu kế hoạch (Recall@5 ≥ 0,80, correctness ≥ 70%). **Người chấm là AI** (Codex, DeepSeek), chưa có người chấm độc lập.
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

## 4. Số đo chất lượng

| Truy xuất | Query | Recall@5 | MRR@5 | Accuracy | Bám nguồn đủ |
|---|---|---:|---:|---:|---:|
| E5 | Gốc | 82,82% | 0,728 | 149/195 · 76,41% | 95,32% |
| BM25 | Rewrite | 87,69% | 0,690 | 158/195 · 81,03% | 98,90% |
| Hybrid | Gốc | 86,41% | 0,701 | 155/195 · 79,49% | 96,61% |
| **Hybrid** | **Rewrite** | **90,34%** | **0,767** | **160/195 · 82,05%** | 98,38% |

Trích từ [ma trận truy xuất](../testing/2026-11-14_s4-retrieval-matrix.md): 212 câu, Tavily Off, chấm bằng DeepSeek. TV3 đề xuất giữ **Hybrid + rewrite** làm mặc định. Hybrid cải thiện mạnh ở tiếng Việt không dấu (Recall@5 50% → 93,75%) nhưng nhóm này nhỏ, cần đo thêm.

Kiểm thử trên `develop` tại `65a9b73` (máy TV1, 16/11): **1.161 unit test backend** đạt, ruff và format sạch, OpenAPI khớp; web 49 test, bot 33 test đạt. Integration test không chạy được trên máy TV1 vì Docker tắt; CI trên commit này (có PostgreSQL, Redis, Qdrant) **success**. GitNexus không tìm thấy vòng import nào.

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
