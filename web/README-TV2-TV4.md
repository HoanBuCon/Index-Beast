# IndexBeast — Công việc TV2 và TV4

**Nhóm 4 Hollows · Cập nhật 09/11/2026**

README theo dõi thẻ của TV2 và TV4 qua 6 sprint, công việc phát sinh và backlog có điều kiện. **Đã triển khai** ghi nhận phần có mã nguồn hoặc bằng chứng đã lưu. **Một phần** nêu phần còn thiếu để nghiệm thu. **Kế hoạch** ghi các bước tiếp theo theo kế hoạch hoặc yêu cầu hiện hành. [Kế hoạch sprint](../docs/03_SPRINT_PLAN.md) · [SRS](../docs/02_SRS.md) · [Handover](../docs/handover/README.md) · [Công việc TV1 và TV3](README-TV1-TV3.md)

<a name="tv2-unclething"></a>

## TV2 — UncleThing · Data Engineer

TV2 phụ trách khảo sát nguồn, thu thập và bảo quản raw/ảnh, làm sạch, chia đoạn, metadata và bàn giao corpus cho TV3. TV2 review chéo nguồn và đáp án của golden set. Corpus hiện có nội dung Elden Ring base game và Shadow of the Erdtree. Cần giữ provenance và nhãn chưa xác định khi chưa đủ thông tin về release, ngôn ngữ hoặc giấy phép.

### Sprint 1–3 · Khảo sát, thu thập và chuẩn hóa corpus

| Thẻ | Công việc                   | Tiến độ và đầu ra                                                                                                                                                                                                 |
| --- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1.6 | Khảo sát nguồn lore         | Đã khảo sát category, endpoint MediaWiki của wiki.gg và phân trang fanapis. Fandom trả 403 ở bước kiểm robots nên lượt đối chiếu 10 trang chưa thực hiện.                                                         |
| 1.7 | Prototype crawler wiki.gg   | Đã bàn giao 200 trang mẫu cùng manifest. Có raw theo revision, kiểm checksum và ảnh liên kết theo trang/section với caption, alt và metadata quyền khi có.                                                        |
| 1.8 | Chiến lược chunk (ADR-003)  | Đã ghi quy tắc giữ title/section và chia đoạn theo cấu trúc. Lượt full Sprint 2 dùng trần 450 token.                                                                                                              |
| 2.4 | Crawl full wiki.gg          | Đã ghi nhận lượt crawl 4.164 trang base và SotE. Có báo cáo, lưu raw/ảnh theo manifest và hỗ trợ resume.                                                                                                          |
| 2.5 | Làm sạch và chuẩn hóa       | Đã xuất artifact clean, giữ lore, hội thoại và metadata nguồn. Có hàng đợi review cho nội dung khó phân loại. Sprint 3 mở rộng để giữ thêm fact gameplay từ bảng.                                                 |
| 2.6 | Chunking và metadata        | Đã tạo 23.765 chunk cho bản Sprint 2 và kiểm tra hai lượt nạp PostgreSQL. Số liệu thuộc artifact Sprint 2. Nhãn spoiler và mốc cập nhật nguồn vẫn cần hoàn thiện.                                                 |
| 3.4 | Wikipedia và khử trùng lặp  | Một phần. Module Wikipedia còn là khung. SRS hiện ghi nhận dedup chunk và alias URL web trong ngữ cảnh. Nếu mở rộng corpus Wikipedia, cần đánh giá trùng lặp giữa các nguồn trên artifact cụ thể.                 |
| 3.5 | Bảng alias thực thể v1      | Hoãn sang Sprint 4 theo SRS. Module alias còn là khung. Cần chốt nguồn redirect, danh hiệu/biệt danh, xử lý xung đột và contract lookup với TV3.                                                                  |
| 3.6 | Kiểm tra chất lượng dữ liệu | Đã audit độ phủ, tái tạo facts/clean/chunk và kiểm offline. Lượt structured-release có 39.551 chunk, trong đó 34.047 EN. Đã xem 50 mẫu bằng trợ lý, còn chờ người review và kiểm retrieval trên collection riêng. |

Phần phát sinh gồm audit độ phủ gameplay, đọc bảng có ô gộp và nhiều cấp header, giữ provenance đến ô nguồn, tách fact đủ điều kiện khỏi hàng đợi review và kiểm CSV round-trip. Mã structured ingestion đã vào lịch sử nhánh tại merge PR #90. Bundle raw/ảnh/facts/chunk vẫn được bàn giao riêng ngoài Git. Dùng manifest để chọn đúng phiên bản và dùng `chunks.jsonl` khi cần giữ metadata đầy đủ. [Khảo sát nguồn](../docs/data-sources.md) · [Crawler và ảnh](../docs/handover/2026-10-24_s1-tv2_crawler-va-du-lieu-anh.md) · [ADR chunking](../docs/adr/003-chunking.md) · [Crawl full](../docs/handover/2026-10-28_s2-tv2_full-crawl.md) · [Chunk Sprint 2](../docs/handover/2026-10-29_s2-tv2_chunk-full-base-sote.md) · [Structured release](../docs/testing/2026-11-09_tv2-structured-release.md) · [Lệnh ingest](ingest/README.md)

### Sprint 4–6 · Cải thiện dữ liệu, cập nhật và bàn giao

| Thẻ | Công việc                     | Phần còn lại và cách nghiệm thu                                                                                                                                                                |
| --- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.5 | Golden set v2                 | Kế hoạch sprint ghi 120 câu. SRS yêu cầu tối thiểu 100 câu, repo hiện có 100 với 64 VI/36 EN. Review nguồn/đáp án từng câu bằng sidecar, chốt mốc 120 với nhóm và khóa phiên bản dùng để eval. |
| 4.6 | Spoiler và `game_scope`       | Đặt quy tắc spoiler, kiểm mẫu 50 trang và giữ `unknown` khi chưa xác minh release. Bàn giao payload mới để TV3 kiểm filter trước khi đổi collection.                                           |
| 4.7 | Tìm web dự phòng              | Kế hoạch gốc ghi DuckDuckGo. SRS hiện hành dùng Tavily do TV3 tích hợp. Phần phối hợp TV2 là góp ý phạm vi nguồn, ghi công và chất lượng đoạn trích khi đánh giá.                              |
| 4.8 | Sửa dữ liệu theo eval         | Phối hợp TV3 phân loại lỗi dữ liệu, retrieval và generation. Sửa cleaning/chunking theo trace, so sánh độ phủ và chạy lại các ca liên quan trên collection thử.                                |
| 5.4 | Cập nhật tăng dần             | Theo revision/recentchanges, xử lý lại trang thay đổi, loại chunk cũ của trang bị xóa, ghi `ingestion_jobs`. Thử cập nhật lặp và phối hợp TV1 lên lịch ngoài giờ cao điểm.                     |
| 5.5 | Quyền riêng tư và lưu trữ log | Thống nhất cách hash ID Discord, chính sách giữ log và job dọn quá 90 ngày theo kế hoạch. Phối hợp TV1 kiểm backend và TV4 cập nhật About theo chính sách đã duyệt.                            |
| 5.6 | Tài liệu pipeline dữ liệu     | Ghi đầu vào, cấu hình, CLI, luồng crawl–clean–chunk và cách thêm nguồn. Nêu rõ bước chỉ kiểm, bước ghi DB và đường dẫn artifact local.                                                         |
| 6.5 | Đóng băng dữ liệu cuối        | Chạy cập nhật cuối, chốt manifest, thống kê theo nguồn/phạm vi và đối chiếu snapshot Qdrant cùng TV1/TV3.                                                                                      |
| 6.6 | Sửa lỗi dữ liệu từ UAT        | Tái hiện lỗi qua câu hỏi và nguồn, sửa rồi kiểm trên corpus mới. Bổ sung câu UAT có đáp án kiểm chứng được vào tập đánh giá.                                                                   |
| 6.7 | Bàn giao kỹ thuật dữ liệu     | Hoàn thiện tài liệu và sơ đồ pipeline. Ghi cách nhận bundle, xác minh manifest, dựng lại index và kiểm coverage.                                                                               |

Tại thời điểm bàn giao, 100 câu trong sidecar vẫn chờ TV2 review. Đoạn trích do người soạn gắn là đầu vào để đối chiếu. [Golden set và trạng thái review](eval/README.md) · [Phiếu review](../docs/evaluation/2026-10-31_golden-set-s2-review.md) · [Handover structured release](../docs/handover/2026-11-09_s3-tv2_tai-tao-facts-clean-chunk-tu-raw.md)

<a name="tv4-quyvuive"></a>

## TV4 — QuyVuiVe · Frontend & Discord Bot

TV4 phụ trách trải nghiệm chat web và bot Discord, tích hợp API, hiển thị nguồn/ảnh, quản lý trạng thái tương tác và điều phối UAT. TV1 hỗ trợ contract, quyền và triển khai. TV3 cung cấp output Agent, citation và yêu cầu hỏi bổ sung để hai client hiển thị đúng.

### Sprint 1–3 · Web, Discord và tích hợp API

| Thẻ  | Công việc                  | Tiến độ và đầu ra                                                                                                                                                                                                                                                     |
| ---- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1.13 | Wireframe và design system | Đã có giao diện theo chủ đề Elden Ring, font, icon, bố cục chat và trạng thái. Cần xác nhận review nhóm cho wireframe/design system nếu nghiệm thu theo thẻ gốc.                                                                                                      |
| 1.14 | Khởi tạo web React         | Đã có React, Vite, TypeScript, cấu hình kiểm kiểu và build, cùng các trang chat, About và admin.                                                                                                                                                                      |
| 1.15 | Khởi tạo Discord bot       | Đã có khung bot discord.js/TypeScript, `/ping`, registry và script đăng ký lệnh.                                                                                                                                                                                      |
| 2.11 | UI chat cơ bản             | Đã có ô nhập, danh sách tin nhắn, sidebar, trạng thái chờ/lỗi và nối API mock.                                                                                                                                                                                        |
| 2.12 | API client cho web và bot  | Đã có client/types hai phía. Web có xử lý timeout, abort và lỗi API. Bot dùng service token từ cấu hình tiến trình.                                                                                                                                                   |
| 2.13 | Bot `/ask` gọi API mock    | Đã kiểm gọi API mock, defer trước khi xử lý và định dạng câu trả lời/nguồn. Có hướng dẫn `make bot-dev`.                                                                                                                                                              |
| 3.11 | Web SSE và nguồn           | Đã có luồng token, dừng/thử lại, nguồn dạng `[n]`, popover và danh sách nguồn. Đã thử lỗi giữa luồng và màn hình 360 px với fixture. Cần đo độ trễ hiển thị trên môi trường demo.                                                                                     |
| 3.12 | Discord trả lời thật       | Đã có `/ask`, `/help`, `/about`, chia embed và đăng ký global. Handover ghi hai lượt handler giả lập gọi backend RAG thật giữ chung hội thoại và có xác nhận `/help`, `/about` trên client. Link xem đầy đủ đã có, còn cần nghiệm thu cú bấm từ Discord với URL demo. |
| 3.13 | About và ghi nguồn         | Đã có giới thiệu, ghi công wiki.gg, giấy phép văn bản và mô tả fan project. Cần đồng bộ câu mô tả phạm vi DLC còn cũ và giữ quyền của ảnh/font theo từng nguồn.                                                                                                       |

Phần phát sinh gồm công tắc Web `Off → On → Always`, khung hỏi bổ sung nhập tự do trên web, ảnh minh họa, trạng thái “Đang suy nghĩ”, nút dừng, focus ô chat và khóa điều hướng khi đang trả lời. Bot có link chia sẻ một câu trả lời đọc riêng trong 24 giờ. Trang chia sẻ dùng bố cục và khối nguồn của chat chính. [Web tích hợp mock](../docs/handover/2026-10-28_s2-tv4_web-api-mock.md) · [Bot mock](../docs/handover/2026-10-30_s2-tv4_bot-ask-api-mock.md) · [Sprint 3](../docs/handover/2026-11-08_s3-tv4_web-sse-bot-va-about.md) · [Discord và backend thật](../docs/handover/2026-11-08_s3-tv4_dang-ky-global-va-thu-backend-that.md) · [Chia sẻ và hiển thị nguồn](../docs/handover/2026-11-08_s3-tv4_nguon-va-link-xem-day-du.md)

### Sprint 4–6 · Hoàn thiện trải nghiệm, UAT và demo

| Thẻ  | Công việc                           | Phần còn lại và cách nghiệm thu                                                                                                                                                              |
| ---- | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.12 | Feedback, lịch sử và câu gợi ý      | Đã có gợi ý và lịch sử khách. Kiểm tạo mới, tải lại, xóa và thông báo 429. Nút feedback đã được gỡ theo quyết định trước đó. Chờ chốt lại phạm vi và cơ chế lưu với TV1 trước khi khôi phục. |
| 4.13 | Popover trích dẫn                   | Đã có nút `[n]`, đoạn trích và link. Kiểm bàn phím, màn hình nhỏ, citation bị thiếu và nhiều nguồn trên cấu hình demo.                                                                       |
| 4.14 | Hỏi tiếp trong thread và feedback   | Một phần. `/ask` đã phân biệt `external_ref` theo thread. Cần nghiệm thu tạo thread từ nút, hết hạn và cách ly ngữ cảnh. Feedback phụ thuộc quyết định chung và API lưu rating.              |
| 5.10 | Theme, responsive và a11y           | Đã có theme và kiểm mẫu 360 px. Kiểm lại focus, bàn phím, tương phản và mobile trên bản demo. Đo Lighthouse theo mục tiêu ≥85 trong kế hoạch.                                                |
| 5.11 | Admin                               | Đã có trang và khả năng xem stats/trace do TV1 bổ sung. Phối hợp nghiệm thu quyền truy cập và nối dữ liệu feedback, ingestion, eval khi các contract tương ứng sẵn sàng.                     |
| 5.12 | Bot production `/config` và mention | Kế hoạch. `/config` chưa có trong registry hiện tại. Nếu làm, kiểm quyền admin guild, allowlist kênh, mention, link mời và cấu hình trên server demo.                                        |
| 6.1  | UAT với người chơi                  | Điều phối 10–15 người theo kế hoạch. Thu độ đúng, độ hữu ích và UX. Tổng hợp theo web/Discord, chuyển lỗi dữ liệu cho TV2, lỗi câu trả lời cho TV3 và lỗi vận hành cho TV1.                  |
| 6.11 | Hoàn thiện UI theo UAT              | Ưu tiên vấn đề cản trở người dùng, thử lại trên mobile và Discord, kiểm regression nguồn/ảnh/hỏi bổ sung.                                                                                    |
| 6.12 | Slide và video demo                 | Phối hợp cả nhóm làm slide bài toán, kiến trúc, dữ liệu, eval và kết quả. Quay video 3–5 phút với web và Discord, tập dượt trên môi trường đã chốt.                                          |
| 6.13 | Hướng dẫn dùng web và bot           | Chốt hướng dẫn người dùng, cài/mời bot, hỏi tiếp, xem nguồn và chia sẻ. Kiểm bằng lượt làm theo hướng dẫn từ người mới.                                                                      |

**Backlog có điều kiện.** Discord OAuth (`FR-WEB-09`) hiện hoãn theo ADR-005. Xem lại khi nhóm chốt đăng nhập và đồng bộ lịch sử giữa web/Discord. [SRS](../docs/02_SRS.md) · [Hướng dẫn web](../web/IMPLEMENTATION.md) · [Hướng dẫn bot](../bot/IMPLEMENTATION.md)

## Điểm phối hợp

- **Mốc chung của nhóm.** Kickoff (1.1), review/retro (1.16, 2.14, 4.15, 5.13), demo MVP (3.14) và demo cuối (6.14). TV2 trình bày provenance, độ phủ và phiên bản corpus. TV4 điều phối luồng demo web/Discord và tổng hợp phản hồi. [Kế hoạch sprint](../docs/03_SPRINT_PLAN.md)
- **Dữ liệu và hiển thị.** TV2 giữ URL, section, release và metadata ảnh/giấy phép. TV3 chọn evidence và ảnh để trả về. TV4 hiển thị theo contract và cùng TV2 kiểm nội dung ghi công trên About. [Kiến trúc hệ thống](../docs/indexbeast-system-pipeline.md)
- **Tích hợp và UAT.** TV4 ghi kênh sử dụng, bước tái hiện và request ID khi có. TV1 đối chiếu log và quyền. TV3 kiểm Agent/retrieval/generation. TV2 xử lý những ca có nguồn gốc từ dữ liệu. [Công việc TV1 và TV3](README-TV1-TV3.md)

## Meta-prompt cập nhật README

> **Vai trò.** Bạn là kỹ sư hỗ trợ nhóm 4 Hollows và cập nhật README công việc TV2 UncleThing, TV4 QuyVuiVe.
>
> **Ngữ cảnh.** Đọc kế hoạch sprint, SRS, mã nguồn, lịch sử Git, handover và kết quả đã lưu. Đối chiếu thẻ từ Sprint 1 đến Sprint 6, việc phát sinh, mốc chung và backlog. Dùng yêu cầu hiện hành khi thẻ gốc đã đổi phạm vi.
>
> **Ràng buộc.** Tách việc đã triển khai khỏi nghiệm thu người dùng và việc theo kế hoạch. Ghi phiên bản artifact và cách kiểm nếu dẫn số đo. Phân biệt fixture UI, handler giả lập gọi backend thật và lượt dùng trực tiếp trong Discord. Giữ dữ liệu và cấu hình local của nhóm.
>
> **Đầu ra.** Cập nhật `backend/README-TV2-TV4.md` bằng Markdown UTF-8, chia hai phần theo thành viên và giữ mã thẻ. Kiểm liên kết trong README gốc và ghi handover cho phần cập nhật tài liệu.
