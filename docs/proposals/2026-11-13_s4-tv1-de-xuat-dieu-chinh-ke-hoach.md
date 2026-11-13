# Sprint 4: phân tích nhiệm vụ TV1 và đề xuất điều chỉnh kế hoạch

| | |
|---|---|
| Ngày | 13/11/2026 |
| Người lập | TV1 (Quỷ Tháng 5 Khóc) |
| Căn cứ | `develop` tại `14bda7f`; `planning/sprint_plan.json`; SRS 0.7.1; handover đến 12/11; báo cáo Sprint 3 ([PR #93](../handover/2026-11-09_s3-tv1_bao-cao-ban-giao-sprint-3.md)) |
| **Hạn chế** | **Chưa đối chiếu với Trello thật** (board riêng tư; chủ dự án yêu cầu bỏ bước này). Trạng thái "đã xong" bên dưới chỉ dựa trên repo |

Phân công Sprint 4 theo chủ dự án: TV1 = Quỷ Tháng 5 Khóc, TV2 = Himmel, TV3 = Thợ Săn Lợn Sang, TV4 = Riley.

## 1. Mục tiêu Sprint 4 (theo chủ dự án)

| Mục tiêu | Người phụ trách | Trạng thái theo repo |
|---|---|---|
| Hoàn thiện dữ liệu wiki (~4.100 trang) | TV2 | Gần xong: PR #95 (13/11), 4.164 trang, 39.574 chunk, có `spoiler_level`, `game_scope`. **Chưa nạp PostgreSQL/Qdrant** |
| Golden set 400 câu, 3 cấp suy luận, 200 câu mỗi ngôn ngữ | TV3 | Hiện 100 câu (64 VI / 36 EN), **0 câu được review chéo** |
| Chốt pipeline RAG, LangGraph; hoàn thiện pipeline | TV3 | Đang chạy; còn 502, p95 sát 10 s |
| Đo Accuracy, Recall | TV3 | **Chưa có số nền nào** (không có Recall@k/MRR baseline) |
| Auth service | **TV1 + TV4** | Chưa có. Hiện chỉ có service token cho bot, `ADMIN_TOKEN` chung, `conversation_token` cho khách |
| Đóng gói, PR vào `main`, release v2 | **TV1 quyết định** | `main` chậm `develop` 62 commit; **repo chưa có tag hay release nào** |

## 2. Việc của TV1

### 2.1 Thẻ gốc Sprint 4 (11 điểm) và hiện trạng

| Thẻ | Hiện trạng | Đề xuất |
|---|---|---|
| 4.1 Xác thực client, CORS, bảo vệ admin | Một phần: service token, `X-Admin-Token`, chặn dò token (#87) | **Gộp vào Auth service** |
| 4.2 Rate-limit Redis | Gần xong: `/chat` (#48), `/admin/*` (#87) | Giữ phần còn lại: giới hạn theo người dùng đã đăng nhập |
| 4.3 API feedback và conversations | `/feedback` chỉ trả 204, **chưa lưu** | Làm: lưu đánh giá; danh sách hội thoại theo người dùng |
| 4.4 Test tích hợp pipeline | Chưa làm | Giữ, làm **điều kiện trước release v2** |

### 2.2 Việc mới

| Việc | Mô tả | Ước lượng |
|---|---|---|
| **Auth service** | Theo [ADR-005](../adr/005-dang-nhap.md): Discord OAuth2, phiên trong PostgreSQL, vai trò admin, hội thoại thuộc người dùng, hợp đồng API cho TV4 | 8 điểm |
| **Ghi `eval_runs`** | TV3 cần chỗ lưu kết quả đo (Accuracy, Recall) để so giữa các lần; bảng đã có, chưa ai ghi | 2 điểm |
| **Runner dữ liệu nhận bản S3/S4** | `make data` chỉ tự chọn bản S2; cần nhận bản mới của TV2 để nạp thử vào collection riêng | 1 điểm |
| **Gói release v2** | Changelog, hướng dẫn nâng cấp từ v1 (migration, biến `.env`), checklist trước release. **Không tag, không release, không merge vào `main`** | 2 điểm |
| Cập nhật SRS, TechStack, ADR | SRS 0.8.0 (`FR-AUTH-*`), ADR-005, sửa ADR-004 còn ghi "base game" | 1 điểm |

**Tổng:** khoảng 11 điểm gốc + 14 điểm mới ≈ 25 điểm, gấp đôi một sprint thường. Vì sprint hoàn thành trong tuần này, đề xuất thứ tự ở mục 4 và cắt phần ngoài lõi.

## 3. Đề xuất điều chỉnh kế hoạch

1. **Đóng các thẻ lỗi thời:** "Tìm web dự phòng qua DuckDuckGo" (đã thay bằng Tavily, S3); "Golden set v2 (120 câu)" (thay bằng golden set 400 của TV3); "Gắn `spoiler_level` và chuẩn hoá `game_scope`" (TV2 đã xong, PR #95).
2. **Chốt số nền trước mục tiêu chất lượng:** Recall@5 ≥ 0.80 và correctness ≥ 70% chưa có số đo nào. Đề xuất: TV3 đo số nền trên golden set 400 trước, rồi nhóm mới khóa mục tiêu cho v2.
3. **Golden set 400 câu cần người duyệt:** hiện 0/100 câu được duyệt. Đề xuất TV2 review chéo ngay khi TV3 có bản nháp, và mọi điểm chất lượng ghi rõ "đã/chưa duyệt".
4. **Điều kiện trước release v2** (đề xuất cho chủ dự án): test tích hợp (4.4) xanh; dữ liệu S4 đã nạp thử vào collection riêng và so với bản đang chạy; migration `0004` chạy được trên bản sao dữ liệu v1; branch protection yêu cầu 1 lượt review (hiện 1/30 PR S3 có review).
5. **Auth trên cloud cần tên miền HTTPS.** Đề xuất chốt tên miền trong Sprint 5 trước khi triển khai; Sprint 4 chỉ cần chạy trên `localhost`.
6. **Quyết định cho TV4 (Riley):** nút 👍/👎 đã gỡ khỏi web từ 05/11; nếu muốn thu feedback ở v2 thì khôi phục sau khi API lưu feedback xong.
7. **Chính sách trả lời:** chế độ tư vấn gameplay không cần trích dẫn (TV3, 09/11) đổi nguyên tắc "chỉ trả lời từ nguồn"; cần chủ dự án quyết định trước release.

## 4. Thứ tự thực hiện của TV1

| # | Việc | Phụ thuộc | Ghi chú |
|---|---|---|---|
| 1 | ADR-005 và tài liệu này | — | Làm trước, để duyệt hướng |
| 2 | Lưu feedback; ghi `eval_runs`; runner nhận bản S4 | — | Nhỏ, TV3 dùng ngay |
| 3 | Auth service (backend + hợp đồng TV4) | ADR-005 | Việc lớn nhất, chia lát nhỏ |
| 4 | Test tích hợp pipeline (4.4) | 2, 3 | Điều kiện release |
| 5 | Gói release v2 | 4 | Chủ dự án tự quyết merge, tag, release |
| 6 | Báo cáo bàn giao Sprint 4 | tất cả | |

**Ngoài phạm vi lượt này:** giao diện đăng nhập (TV4); xóa tài khoản và dữ liệu; đăng nhập bằng nhà cung cấp khác; bắt buộc đăng nhập; triển khai cloud (Sprint 5).

## 5. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Đăng nhập chưa thử với Discord thật (cần client secret và người bấm) | Cao | Kiểm thử bằng giả lập ở mức mã; chủ dự án thử một lần thật trước khi dùng |
| Auth chạm các file của TV3 (`chat.py`, `memory_repository.py`) | Trung bình | Chỉ thêm tham số tùy chọn, giữ hành vi cũ khi không đăng nhập; TV3 review |
| Lộ phiên, CSRF, chuyển hướng mở | Cao nếu sai | `state` dùng một lần, PKCE, cookie `httpOnly`, kiểm `Origin`, `next` chỉ đường dẫn tương đối, test từng trường hợp |
| Khối lượng ≈ gấp đôi một sprint | Trung bình | Thứ tự mục 4; cắt phần ngoài lõi |
