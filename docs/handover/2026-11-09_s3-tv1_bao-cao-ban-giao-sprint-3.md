# Báo cáo bàn giao Sprint 3 — IndexBeast (nhóm 4 Hollows)

| | |
|---|---|
| Sprint | 3 — *RAG end-to-end → MVP nội bộ*, 02/11 – 08/11/2026. **Đã đóng** |
| Ngày lập | 09/11/2026 (Asia/Saigon) |
| Người lập | TV1 (Hoanbucon), Tech Lead |
| Căn cứ | `develop` tại `d706167` (sau PR #92), CI trên commit này: success. Các handover S3 trong [`docs/handover/`](README.md), báo cáo test trong [`docs/testing/`](../testing/), mã nguồn, và 3 phép đo trên máy TV1 ghi ở mục 5. **Chưa đọc Trello** |
| Cách đọc | Mỗi mục trong outline tiến độ tuần 02–08/11 được giải thích, dẫn bằng chứng, và gắn một kết luận: **Đúng**, **Đúng một phần** hoặc **Sai, đã sửa**. Các mục outline ghi chưa chính xác được sửa ở mục 2 |

## 1. Tóm tắt

- **Sản phẩm dùng thử được trên máy phát triển**, chưa có staging: web trả lời dần (SSE), Discord `/ask` `/help` `/about` dùng chung backend, có trace từng câu trả lời. Sản phẩm bàn giao "Staging chạy trên VPS" của sprint **không đạt** vì chưa có VPS.
- **30 PR S3** (#60–#92) đã merge vào `develop`: TV1 14, TV3 11, TV4 4, TV2 1. **Chỉ 1/30 PR có lượt review** trên GitHub.
- **Còn thiếu so với kế hoạch S3:** báo cáo Recall@k/MRR baseline (không có), staging VPS, reranker chưa bật, golden set 100 câu **0/100 được review chéo**.
- **Chất lượng đo được là sơ bộ:** 25 câu golden chạy thật ngày 09/11 đạt 24/25 (1 lỗi HTTP 502), do trợ lý AI chấm, chưa người nào duyệt; bộ câu này cũng đã dùng để sửa lỗi nên không phải tập kiểm tra độc lập.
- **Còn lỗi 502** ở mọi đợt chạy thật: 1/10, 3/10 và 1/25 (mục 3.3).

## 2. Các chỗ outline cần sửa

| # | Outline ghi | Thực tế | Mục |
|---|---|---|---|
| 1 | "Nạp bộ clean mới" | **Sai.** Bộ clean/chunk mới của TV2 (39.551 chunk, 34.047 tiếng Anh) mới được **tạo và kiểm validate-only**, **chưa nạp PostgreSQL hay Qdrant**, và chỉ nằm trên máy TV2 (Git bỏ qua). Sửa thành: "Tạo bộ clean/chunk mới; chưa nạp" | 3.1 |
| 2 | "Web hỗ trợ … ảnh" | Chỉ **ảnh từ nguồn cục bộ** (wiki.gg đã lưu). Ảnh từ kết quả tìm web có mã ở backend nhưng lần chạy thật không trả ảnh web nào. Sửa thành "ảnh minh họa từ nguồn cục bộ" | 3.4 |
| 3 | Mục tiêu "có thể dùng thử trên web và Discord" | Đúng **trên máy phát triển**. Chưa có staging; lệnh Discord thật chưa được người dùng bấm kiểm (TV4 chỉ chạy interaction giả lập với backend thật). Sửa thành "dùng thử cục bộ" | 3.4, 4 |
| 4 | "Có thông tin theo dõi từng bước" | Có, nhưng **mặc định tắt**: cần `CHAT_PERSISTENCE=postgres`, `ADMIN_TOKEN` và migration `0003`. Mới có **1 mẫu thật**, và mẫu đó không có bước truy xuất | 3.4 |
| 5 | "sửa các trường hợp (502) đã xác định" | Đúng, nhưng **chưa hết 502** (1/10, 3/10, 1/25 ở các đợt chạy thật) | 3.3 |
| 6 | "tránh phụ thuộc web quá mức" | Đúng; đã tìm ra nguyên nhân và có số đo, nhưng hai đợt đo dùng **hai bộ 25 câu khác nhau** nên không so trực tiếp được | 3.3 |

## 3. Giải thích và bằng chứng từng yêu cầu

### 3.1 Dữ liệu

| Yêu cầu | Kết luận | Giải thích và bằng chứng |
|---|---|---|
| Rà soát và cải thiện làm sạch, chia đoạn | **Đúng** | **TV1** rà toàn bộ 4.164 trang: cách chia theo heading đúng, 76 "tiêu đề giả" trên 53 trang, 3 chunk lẫn nhẹ, không mất heading thật ([báo cáo](2026-11-02_s3-tv1_ra-soat-section-chunk.md)). **TV2** audit cấu trúc và khả năng tìm bằng chứng, viết lại parser bảng, xuất `facts_clean`, `content_clean`, `chunks` ([audit](2026-11-08_s3-tv2_chat-luong-du-lieu-va-rag-readiness.md), [tái tạo](2026-11-09_s3-tv2_tai-tao-facts-clean-chunk-tu-raw.md), PR #90). Kết quả: 8.506 bảng, 255.039 ô được hạch toán; 118.498 fact (70.561 giữ, 47.937 chuyển review); 39.457/39.457 unit chunk được phủ |
| Xử lý mất bảng chỉ số | **Đúng** | Lỗi mất bảng chỉ số infobox của ~1.500 trang được TV1 sửa từ S2 (PR #53, 1.551 khối chỉ số). TV2 S3 giữ chỉ số có nhãn: trong pool nguồn cố định, 15 ca thông số có bằng chứng từ **1/15 lên 15/15** và tìm đúng nguồn ở top 5 là 15/15. Đây là diagnostic dùng để sửa lỗi, **không phải Recall/MRR** |
| Thiếu ngữ cảnh | **Đúng** | Chunk bảng dài lặp tiêu đề/ngữ cảnh hàng, cắt theo ký tự nguyên vẹn, giới hạn 450 token và overlap 50 vẫn đạt ([báo cáo TV2](../testing/2026-11-09_tv2-structured-release.md)). 50 mẫu do trợ lý đọc: 38 nhất quán với nguồn, 10 chuyển review đúng, 2 cần xem ngữ cảnh; chưa người duyệt |
| Lẫn các biến thể | **Đúng một phần** | Bảng hội thoại nhiều cột EN/JP và bảng bị nhận nhầm là hội thoại được tách vai trò hoặc chuyển review thay vì nối chung; bảng chưa tách được giữ nguyên văn trong review. Còn hạn chế: header/legend/compatibility chưa rõ, `source_updated_at`, `spoiler_level` và giấy phép ảnh |
| **Nạp bộ clean mới** | **Sai, đã sửa** | TV2 ghi rõ: validate-only 4.164 document/39.551 chunk, **ghi database 0, gọi encoder/API 0**, "không tự re-index production". Qdrant dùng khi TV3 chạy thật có **18.383 point** (báo cáo ngày 09/11), khác 18.368 của S2. Không handover nào ghi lượt index tạo ra 18.383. Con số này trùng số chunk tiếng Anh khi chunk lại bằng cleaner đã sửa ở PR #53 (TV1 đo ngày 02/11); đó là suy luận của TV1, chưa xác nhận. Script `data_pipeline.py` của TV1 chỉ tự chọn bản mang phiên bản S2, **chưa nhận bản S3 của TV2** (việc TV1 tuần tới) |
| Độ phủ hướng dẫn chơi và build còn hạn chế | **Đúng** | 327/486 ứng viên trang trang bị chưa thấy bảng upgrade trong raw. Calculator build chỉ xử lý một tay, không bonus, không AR/DPS; ở lần chạy 07/11 ca Vagabond/Zweihander lỗi calculator và ca Bandit/Reduvia "chưa có bảng 8 chỉ số đã kiểm" ([báo cáo](../testing/2026-11-07_evidence-media-build-10/README.md)) |

### 3.2 Xử lý hội thoại

| Yêu cầu | Kết luận | Giải thích và bằng chứng |
|---|---|---|
| Làm rõ câu hỏi trước khi tìm kiếm, xử lý câu hỏi tiếp nối | **Đúng** | Một agent (LangGraph, `app/rag/agent.py`) quyết định ý định, câu tiếp nối thuộc chủ đề nào, có viết lại truy vấn không, hỏi lại hay tìm; server vẫn kiểm giữ tên riêng, số, phủ định ([handover](2026-11-06_s3-tv3_agent-va-semantic-memory.md)). Chạy thật 20 lượt: 20/20 HTTP 200, 48 lượt gọi mô hình; TV3 ghi nhận **còn lỗi chất lượng** ([báo cáo](../testing/2026-11-06_agent-memory-20-live/README.md)) |
| Tìm lại thông tin hội thoại liên quan | **Đúng một phần** | Lịch sử đưa vào chỉ gồm tối đa 3 lượt người dùng liên quan; bộ nhớ ngữ nghĩa (PostgreSQL + Qdrant `conversation_memories`) tìm lại chủ đề và dữ kiện. Trong lần chạy 20 lượt: sau khi khởi động lại dịch vụ vẫn nhớ chủ đề gia phả Marika và câu hỏi Moonveil đang chờ; cấp độ sửa từ 100 sang 120 được đánh dấu thay thế. **Mặc định `CHAT_PERSISTENCE=memory`**, nên tính năng bền chỉ chạy khi bật cấu hình và migration `0002` |
| Hỏi bổ sung khi thiếu cấp độ, mục tiêu, tình trạng | **Đúng** | Tối đa 2 trường mỗi lần hỏi, hết hạn sau 30 phút, chỉ ghi trạng thái khi trả lời thành công; ô nhập tự do (PR #75); ngày 09/11 thêm lý do `player_detail` và so sánh theo tiêu chí ([handover](2026-11-09_s3-tv3_so-sanh-va-hoi-bo-sung.md)). Trong 25 câu ngày 09/11, ba ca hành vi (từ chối ngoài phạm vi, hỏi lại) đều đạt |

### 3.3 Tìm kiếm và trả lời

| Yêu cầu | Kết luận | Giải thích và bằng chứng |
|---|---|---|
| Kết hợp dữ liệu nội bộ với tìm kiếm web | **Đúng** | Tavily Search + Extract, chỉ giữ domain trong allowlist, nguồn web gắn nhãn `origin=web`, đoạn trích qua cùng bước kiểm quote như nguồn cục bộ ([handover](2026-11-04_s3-tv3_tavily-web-search.md)). Có lượt tìm web thật: 48 request Tavily trong đợt 04/11, 4 request trong đợt 07/11. Web có nút OFF/ON/ALWAYS, Discord luôn `auto` |
| Điều chỉnh đánh giá bằng chứng để tránh phụ thuộc web quá mức | **Đúng** | **Nguyên nhân tìm ra** ngày 04/11: 23/24 kết quả đánh giá bị từ chối vì sai định dạng nên chế độ `auto` gần như lúc nào cũng tìm web (24 Search + 24 Extract). Đã sửa ngày 05/11 (danh sách mã bằng chứng; phát lại 24/24 kết quả thật đều đọc được) ([handover](2026-11-05_s3-tv3_rag-evidence-guards.md)). **Số đo sau sửa:** 25 câu ngày 09/11 chạy với Tavily `auto`, **chỉ 1 câu có tìm web** (2 request). Hai đợt dùng hai bộ câu khác nhau, nên đây là minh chứng chiều hướng, không phải so sánh đối chứng |
| Phát hiện lỗi định dạng, trích dẫn, kiểm tra quá chặt gây 502; sửa các trường hợp đã xác định | **Đúng một phần** | Đã sửa: JSON thiếu trường được sinh lại một lần (TV3, 04/11); đoạn không có trích dẫn bị bỏ thay vì báo 502, và lỗi trích dẫn được sinh lại ([TV1](2026-11-02_s3-tv1_thu-lai-loi-trich-dan.md), PR #67). **Chưa hết:** đợt 06/11 1/10 lượt 502; đợt 07/11 **3/10** lượt 502 (mô hình dịch constraint thay vì trích nguyên văn, hỏi 3 trường trong khi schema cho 2, truy vấn làm mất phủ định); đợt 09/11 1/25 lượt 502 |

### 3.4 Sản phẩm

| Yêu cầu | Kết luận | Giải thích và bằng chứng |
|---|---|---|
| Web trả lời dần | **Đúng** | SSE là chế độ mặc định của web (PR #83); hội thoại cũ gửi lượt mới cũng chuyển sang SSE ([handover](2026-11-08_s3-tv4_web-sse-bot-va-about.md)). Web 48/48 test đạt |
| Dừng và thử lại | **Đúng** | Nút dừng huỷ luồng đang chạy, thử lại dùng lại mã lượt hỏi để không nhân đôi tin nhắn (`web/src/hooks/useChatStream.ts`, `chatState.ts`) |
| Nguồn | **Đúng** | Khối nguồn bị gỡ ngày 05/11 rồi **khôi phục ngày 08/11**, gồm số `[n]`, tiêu đề, đoạn trích, link; nút đánh giá 👍/👎 đã gỡ ([handover](2026-11-08_s3-tv4_nguon-va-link-xem-day-du.md)) |
| Ảnh | **Đúng một phần** | Ảnh minh họa từ nguồn cục bộ, có chú thích nguồn và giấy phép "chưa xác minh". Backend có bộ chọn ảnh từ kết quả web (PR #88), nhưng lần chạy thật 07/11 không có ảnh web nào đủ điều kiện gắn với câu trả lời |
| Khung trả lời bổ sung | **Đúng** | Khung theo kiểu thông báo vật phẩm Elden Ring, Enter gửi, 41/41 test ở thời điểm đó ([handover](2026-11-07_s3-tv4_khung-tra-loi-bo-sung-menu.md)) |
| Discord dùng chung backend | **Đúng** | Bot gọi cùng `/api/v1/chat`. Lệnh global `ping, ask, help, about` được đăng ký ngày 08/11 và đọc lại xác nhận. Probe backend thật với interaction giả lập: 2 lượt đều `grounded`, 6,66 s và 5,66 s, cùng một hội thoại ([handover](2026-11-08_s3-tv4_dang-ky-global-va-thu-backend-that.md)). **Chưa có bằng chứng người dùng bấm lệnh thật.** Bot 33/33 test đạt |
| Xem đầy đủ câu trả lời trên web | **Đúng** | Câu trả lời dài chia thành nhiều embed; nút "Xem đầy đủ trên web · 24 giờ" mở trang chỉ đọc (router `answer_shares`, [handover](2026-11-08_s3-tv4_nguon-va-link-xem-day-du.md)). **Quyền riêng tư:** ai có link đều đọc được đến khi hết hạn; snapshot trong Redis không mã hóa |
| Có thông tin theo dõi từng bước để điều tra lỗi | **Đúng một phần** | **TV1** (PR #79, #82, #85, #87): mỗi câu trả lời lưu vào PostgreSQL câu viết lại, độ trễ, token và trace đã che secret (tối đa 64 KB); xem bằng `GET /api/v1/admin/trace/{message_id}`, `make trace ID=…` hoặc nút "Xem trace" trên web; `/admin/stats` cho nút "Kết nối"; chặn dò token (429 sau 10 lần sai/phút/IP). **Bằng chứng thật:** database dev của TV1 có 1 câu trả lời ngày 09/11 với trace 769 ký tự, độ trễ 1.649,73 ms, token 1.848 vào/108 ra, gồm các khóa `agent, memory, rewrite, web_search, generation_graph_nodes, graph_nodes, model_calls, prepare_ms, latency_ms`. Mẫu này **không có bước truy xuất** (`retrieved`, `selected_ids`). **Hạn chế:** mặc định tắt; thời gian riêng của bước sinh câu trả lời chưa có; `tokens_in/out` chưa gồm lượt đánh giá bằng chứng và tool agent; trang Admin hiện JSON thô; mục "Phản hồi chưa hữu ích" trống vì `/feedback` chưa lưu |

### 3.5 Kiểm thử và hạn chế

| Yêu cầu | Kết luận | Giải thích và bằng chứng |
|---|---|---|
| Golden set 100 câu: 64 Việt, 36 Anh | **Đúng** | Đã đếm trực tiếp `backend/eval/golden_set.jsonl`: **100 câu, 64 vi / 36 en**; độ khó 33 dễ / 44 vừa / 23 khó; 13 ngoài phạm vi, 7 thiếu bằng chứng |
| Chạy các đợt test nhỏ bằng dịch vụ thật, lưu lỗi, thêm test hồi quy | **Đúng** | Xem bảng dưới. Test hồi quy: unit test backend tăng từ 529 (đầu S3) lên **1.004**; mỗi lỗi tìm ra đều có test (ví dụ 70 test guard bằng chứng từ kết quả thật, test chặn quay lại lỗi Caddy allowlist) |
| Chưa hoàn thiện build tổng quát | **Đúng** | Xem 3.1; calculator chỉ kiểm bảng 8 chỉ số một tay. Ngày 09/11 TV3 thêm chế độ tư vấn gameplay cho phép đề xuất **từ kiến thức chung, không cần trích dẫn** (`prompts/gameplay_advice.md`): đây là thay đổi chính sách "chỉ trả lời từ nguồn", **cần nhóm quyết định** |
| Chưa hoàn thiện walkthrough, ảnh web | **Đúng** | Walkthrough/tiến trình quest chỉ trả lời có điều kiện hoặc hỏi lại; ảnh web xem 3.4 |
| Bộ đáp án cần review chéo | **Đúng** | Sidecar `backend/eval/reviews/s2-golden-set-review.jsonl`: **100 pending, 0 approved** |

**Các đợt chạy thật (đều do TV3, kết quả đã lưu):**

| Ngày | Đợt | Kết quả | Ghi chú |
|---|---|---|---|
| 04/11 | [25 câu chẩn đoán](2026-11-04_s3-tv3_golden-25-diagnostic.md) | 24/25 phản hồi hợp lệ; trung vị 8,3 s, p95 12,4 s | Tìm ra sai định dạng bộ đánh giá, 8/24 viết lại bị loại |
| 05/11 | [Gameplay 25 + OFF ghép cặp + retest](2026-11-05_s3-tv3_gameplay-clarification-va-golden-100.md) | 38 yêu cầu HTTP | Giữ cả lỗi trước sửa |
| 06/11 | [20 lượt hội thoại](../testing/2026-11-06_agent-memory-20-live/README.md) | 20/20 HTTP 200 | Có lỗi chất lượng |
| 06/11 | [10 lượt tool agent](../testing/2026-11-06_tool-agent-10/README.md) | 9/10 HTTP 200; trung vị 4,48 s, p95 7,19 s | 0 request Tavily |
| 07/11 | [10 lượt evidence/ảnh/build](../testing/2026-11-07_evidence-media-build-10/README.md) | **7/10 HTTP 200**, 3 lỗi 502 | Trung vị 10,2 s; "không phải 7 đáp án hoàn toàn đúng" |
| 09/11 | [25 câu theo độ khó](../testing/2026-11-09_golden-25-by-difficulty/README.md) | 24/25 đạt; C 48/48, F 42/42; trung vị 7,24 s, **p95 10,31 s** | **Trợ lý AI chấm**, chưa người duyệt; chạy trên bộ câu đã dùng để phát triển |

Mọi bảng chấm đều ghi rõ là sơ bộ. Điểm tuyệt đối (48/48, 42/42) trên tập đã dùng để sửa lỗi **không** phản ánh độ đúng trên câu hỏi mới.

## 4. Đối chiếu sản phẩm bàn giao của kế hoạch S3

| Sản phẩm | Trạng thái |
|---|---|
| Pipeline rewrite → hybrid → rerank → generate có trích dẫn | **Đạt một phần.** Có hybrid (dense + BM25, RRF), trích dẫn kiểm bằng `quote_id` do server cấp. **Reranker chưa bật**, thay bằng bước đánh giá bằng chứng của agent |
| `/chat`, `/chat/stream` thật + lưu hội thoại | **Đạt**, lưu PostgreSQL khi bật `CHAT_PERSISTENCE=postgres` (mặc định `memory`) |
| Web streaming + nguồn; bot trả lời thật | **Đạt** trên máy phát triển |
| Báo cáo Recall@k/MRR baseline | **Không đạt.** Không có tệp nào; golden set chưa được duyệt nên chưa có số đo chính thức. Số duy nhất gần nhất là diagnostic 15/15 ca thông số của TV2 |
| Staging trên VPS | **Không đạt.** Chưa có VPS, chưa có tên miền. TV1 đã viết sẵn `docker-compose.staging.yml`, Caddy (basic auth + lọc IP), `scripts/staging/*` và `docs/staging.md`, mới kiểm bằng `caddy validate` và `docker compose config`; **chưa chạy trên máy thật, chưa có số RAM/CPU** |
| Sprint 3 Review — MVP Demo nội bộ | **Không có ghi nhận** kết quả 10 kịch bản Phụ lục A trong repo |

Độ trễ: mục tiêu p95 < 10 s; đợt gần nhất 10,31 s (chưa đạt sát biên), đợt 07/11 trung vị đã 10,2 s.

## 5. Phần việc của TV1 trong S3

| PR | Nội dung | Ghi chú |
|---|---|---|
| #60, #62 | Căn trái menu web; bỏ `.claude/` khỏi Git | — |
| #61 | `make data STEP=...`: script chạy từng bước crawl/clean/chunk/load/index | Chỉ chọn được bản S2 (xem 3.1) |
| #65, #66, #67 | Câu chào/danh tính không gọi LLM, bỏ nhãn "thiếu bằng chứng" sai; viết lại câu từ chối; bỏ đoạn thiếu trích dẫn thay vì 502 | Sửa lỗi thật gặp khi bật rewrite |
| #79, #82, #85 | Lưu trace và số đo vào PostgreSQL; endpoint, CLI, web xem trace; `/admin/stats` | Thẻ 3.2. Làm hộ TV4 phần web của #85 |
| #80 | Staging: compose, Caddy, script cài đặt/deploy/đo | Thẻ 3.3, **chưa chạy thật** |
| #81 | SRS 0.6.0 → 0.7.0 (sau đó 0.7.1), TechStack 1.5 → 1.6 | Trạng thái thật từng yêu cầu |
| #84, #86 | `make env` đồng bộ `.env` với `.env.example`; Makefile dùng Python của venv | Công cụ cho nhóm |
| #87 | Allowlist IP của Caddy staging thực sự chặn; giới hạn thử token `/admin/*` | Hai lỗi bảo mật tái hiện thật trước khi sửa |

**Code review tự thực hiện:** hai lượt trên phần S3 của TV1 tìm **12 lỗi** (9 + 3), đã sửa hết: đường dẫn `REPO_ROOT` sai trong container, `bootstrap.sh` dừng trước khi bật tường lửa, token thiếu lượt gọi agent, cột trace nạp lại mỗi lượt, Caddy allowlist vô hiệu, thiếu giới hạn dò token… ([lượt 1](2026-11-08_s3-tv1_sua-loi-review.md), [lượt 2](2026-11-08_s3-tv1_sua-loi-review-lan-2.md)).

**Kiểm tra trên `develop` tại `d706167` (máy TV1, ngày 09/11):**

| Lệnh | Kết quả |
|---|---|
| `pytest tests/unit`, `ruff check .`, `pip check`, `export_openapi --check` | **1.004 passed**; ruff đạt; không có gói xung đột; OpenAPI khớp |
| `npm test` web / bot | **48/48** và **33/33** |
| `pytest -m integration` | 16 đạt, **1 lỗi** (`test_health_against_real_services`): do `.env` máy TV1 đang đặt `CHAT_MODE=rag` + `CHAT_PERSISTENCE=postgres`; đặt `CHAT_MODE=mock` thì đạt. CI không có `.env` nên không gặp. Test này đọc `.env` thật của máy dev, nên dễ lỗi như vậy |
| CI GitHub trên `d706167` | success |

## 6. Còn lệch và rủi ro

| Điểm | Chi tiết |
|---|---|
| Review PR | 1/30 PR S3 có lượt review; DoD yêu cầu ít nhất 1 người approve. Đề nghị bật branch protection trên `develop` |
| Golden set | 0/100 approved; mọi điểm chất lượng hiện là sơ bộ của AI |
| 502 | Mọi đợt chạy thật đều còn 502; cần log `RAG validation failed` kèm `request_id` để xác định từng loại |
| Dữ liệu | Bộ mới của TV2 chỉ có trên máy TV2, Git bỏ qua; muốn nạp phải copy dữ liệu và tạo lại junction (TV2 ghi rõ không portable). Không rõ nguồn của 18.383 point đang chạy |
| Chính sách trả lời | Chế độ tư vấn gameplay cho phép trả lời không trích dẫn; chia sẻ link Discord cho ai có link đọc 24 giờ |
| Trace | `messages.rag_trace` của tin nhắn người dùng lưu JSON `null` thay vì NULL của SQL (nhỏ, chưa sửa); Admin dùng một token chung, không có tài khoản |
| Hiệu năng | p95 10,31 s sát ngưỡng 10 s; mỗi câu hỏi tốn khoảng 2–5 lượt gọi mô hình |

## 7. Thành viên cần làm gì để cập nhật

**Mọi thành viên:**

1. `git switch develop && git pull`.
2. Cài lại dependency backend (S3 thêm LangGraph): trong `backend/`, `python -m pip install -r requirements-dev.txt -c constraints.txt`.
3. `make env` để thêm biến mới vào `.env` (không đụng giá trị cũ), rồi điền `TAVILY_API_KEY`; muốn xem trace thì đặt `CHAT_PERSISTENCE=postgres` và `ADMIN_TOKEN` (`openssl rand -hex 32`).
4. `make migrate` (migration `0002`, `0003`). Với bộ nhớ bền, chạy thêm `python -m scripts.memory_admin setup --apply` trong `backend/`.
5. Khởi động lại API; `make test-unit`, `npm test` trong `web/` và `bot/`.

**TV2:** copy bộ `structured-release` (hoặc `delivery/final`) cho TV3 và TV1 để nạp thử vào **collection mới**; review chéo golden set với TV3.

**TV3:** index thử bộ TV2 vào collection mới, so với collection đang chạy trước khi đổi `RAG_COLLECTION`; chạy Recall@k/MRR baseline ngay khi golden có bản được duyệt; điều tra các ca 502 còn lại.

**TV4:** `ADMIN_TOKEN` đặt thì mọi người dùng thấy ID câu trả lời và liên kết "Xem trace"; quyết định có ẩn ở production không. Sửa câu "không gồm DLC" ở trang About (SRS TBD-08).

**TV1:** cho `data_pipeline.py` nhận phiên bản S3; chạy thử staging khi có VPS; `/feedback` lưu dữ liệu (TBD-09).

## 8. Sprint 4

1. Ổn định luồng hiện có; giảm 502 và độ trễ.
2. Nạp dữ liệu mới của TV2 vào collection riêng, đo lại.
3. Review chéo golden set, đo **riêng** ba khâu: hiểu câu hỏi, tìm nguồn, trả lời đúng, trên tập không dùng để sửa lỗi.
4. Quyết định chính sách tư vấn gameplay không trích dẫn.
5. Staging khi có VPS; Recall@k/MRR chính thức; review PR bắt buộc.
