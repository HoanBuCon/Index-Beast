# Tài liệu bàn giao (`docs/handover/`)

- [TV3 · Chẩn đoán lỗi generation và citation (31/10/2026)](2026-10-31_s2-tv3_chan-doan-loi-generation.md)

- [TV4 · Ảnh minh họa trong câu trả lời bằng fixture (31/10/2026)](2026-10-31_s2-tv4_anh-minh-hoa-cau-tra-loi.md)

- [TV4 · Ghép favicon và rà soát Quản trị (31/10/2026)](2026-10-31_s2-tv4_favicon-va-ra-soat-admin.md)

- [TV4 · Khung chat kiểu menu Elden Ring (31/10/2026)](2026-10-31_s2-tv4_khung-chat-menu.md)

Mỗi khi hoàn thành một nhóm task, người thực hiện ghi lại **quy tắc, quy ước, quyết định và bài học** mà người khác cần biết để tiếp tục — đặt cùng mã nguồn, review trong cùng PR.

Theo yêu cầu ngày **26/10/2026**, đây là bước bắt buộc trước khi báo hoàn tất cho mọi nhóm task có thay đổi file, bao gồm tài liệu, notebook, bộ đánh giá và xử lý sự cố Git. Hướng dẫn cho trợ lý được lưu tại [`AGENTS.md`](../AGENTS.md). Với câu hỏi giải thích không làm thay đổi file, không cần tạo handover mới.

## Quy ước đặt tên

```text
<YYYY-MM-DD>_s<sprint>-tv<thành-viên>_<ten-ngan-khong-dau>.md
```

| Phần | Ý nghĩa | Ví dụ |
|---|---|---|
| 2026-10-31 | TV3 (MinhMuc) | [Backend ảnh liên quan cho RAG và contract TV4](2026-10-31_s2-tv3_rag-images-backend.md) |
| 2026-10-31 | TV3 (MinhMuc) | [Mở rộng golden set và phiếu review chéo TV2](2026-10-31_s2-tv3_mo-rong-golden-set.md) |
| 2026-10-31 | TV3 (MinhMuc) | [Sửa web HTTP LAN/VPN và PostgreSQL health](2026-10-31_s2-tv3_sua-web-http-lan-vpn.md) |
| 2026-10-31 | TV3 (MinhMuc) | [Đo độ trễ retrieval hybrid / Query API](2026-10-31_s2-tv3_do-tre-retrieval.md) |
| 2026-10-30 | TV3 (MinhMuc) | [Đo thời gian index toàn bộ corpus được chọn](2026-10-30_s2-tv3_do-thoi-gian-index-toan-bo.md) |
| 2026-10-29 | TV3 (MinhMuc) | [Trợ lý Elden Ring: gameplay, build và audit corpus](2026-10-29_s2-tv3_gameplay-assistant.md) |
| `YYYY-MM-DD` | Ngày bàn giao | `2026-10-19` |
| `s<sprint>-tv<thành-viên>` | Sprint và người phụ trách, khớp mã task trong tên nhánh (`feature/s1-tv1-…`) | `s1-tv1` |
| `ten-ngan-khong-dau` | Chủ đề, chữ thường không dấu, nối bằng `-` | `nen-tang-va-cau-hinh` |

Ví dụ: `2026-10-19_s1-tv1_nen-tang-va-cau-hinh.md`. Tên bắt đầu bằng ngày nên file tự xếp theo thời gian.

## Nội dung tối thiểu

1. Phạm vi: thẻ Trello, nhánh, PR
2. Quy tắc / quy ước mới phải tuân theo
3. Cách dùng và điểm mở rộng của phần vừa làm
4. Sự cố đã gặp và cách xử lý
5. Việc còn lại, nợ kỹ thuật

Ghi thêm các file thay đổi, cách kiểm tra và **kết quả thực tế**; phân biệt kiểm tra tĩnh với chạy notebook/model/API. Nếu chưa có PR hoặc chưa merge, ghi đúng trạng thái, không điền thông tin giả. Khi thêm handover mới, cập nhật bảng danh sách bên dưới. Trước khi kết thúc task, kiểm tra liên kết và UTF-8, rồi dẫn link handover trong phần bàn giao cho người dùng.

Không ghi secret (token, mật khẩu, key) vào tài liệu bàn giao.

## Danh sách

- [TV2 full chunk và PostgreSQL base/SotE](2026-10-29_s2-tv2_chunk-full-base-sote.md)

- [TV2 cài Docker local — chờ reboot](2026-10-28_s2-tv2_docker-local.md)

- [TV2 chunk và PostgreSQL — chờ nghiệm thu DB](2026-10-28_s2-tv2_chunk-postgresql.md)
- [TV2 clean full base + SotE](2026-10-29_s2-tv2_clean-full-base-sote.md)

- [TV2 khảo sát raw và kế hoạch clean/chunk](2026-10-29_s2-tv2_khao-sat-raw-va-ke-hoach-clean-chunk.md)

- [TV2 clean theo inventory](2026-10-28_s2-tv2_clean-inventory.md)
- [TV2 resume qua Windows Task Scheduler](2026-10-29_s2-tv2_resume-task-scheduler.md)

- [TV2 đồng bộ các nhánh GitHub](2026-10-28_s2-tv2_dong-bo-cac-nhanh.md)

- [TV2 full crawl — đang kiểm chứng](2026-10-28_s2-tv2_full-crawl.md)

| Ngày | Người | Chủ đề |
|---|---|---|
| 2026-10-29 | TV3 (MinhMuc) | [Tích hợp corpus pilot vào RAG LangChain và kiểm thử thật](2026-10-29_s2-tv3_corpus-pilot-rag.md) |
| 2026-10-19 | TV1 (Hoanbucon) | [Nền tảng backend, hạ tầng dev và cấu hình](2026-10-19_s1-tv1_nen-tang-va-cau-hinh.md) |
| 2026-10-19 | TV3 (MinhMuc) | [DeepSeek LLM](2026-10-19_s1-tv3_deepseek-llm.md) |
| 2026-10-24 | TV2 (UncleThing) | [Crawler, mẫu raw và dữ liệu ảnh](2026-10-24_s1-tv2_crawler-va-du-lieu-anh.md) |
| 2026-10-26 | TV3 (MinhMuc) | [RAG baseline armor, golden set v0 và xử lý Git](2026-10-26_s1-tv3_rag-baseline-va-golden-set.md) |
| 2026-10-26 | TV1 (Hoanbucon) | [Báo cáo bàn giao Sprint 1](2026-10-26_s1-tv1_bao-cao-ban-giao-sprint-1.md) |
| 2026-10-26 | TV1 (Hoanbucon) | [Báo cáo môn NLP (LaTeX)](2026-10-26_s1-tv1_bao-cao-nlp-latex.md) |
| 2026-10-28 | TV1 (Hoanbucon) | [Schema PostgreSQL và migrations](2026-10-28_s2-tv1_schema-postgresql-va-migrations.md) |
| 2026-10-28 | TV1 (Hoanbucon) | [Hợp đồng API v1, mock và lỗi chuẩn](2026-10-28_s2-tv1_api-contract-v1-va-loi-chuan.md) |
| 2026-10-28 | TV1 (Hoanbucon) | [Audit mã API và DB sau PR #28, #29](2026-10-28_s2-tv1_audit-api-va-db.md) |
| 2026-10-28 | TV2 (UncleThing) | [Làm sạch dữ liệu và xuất CSV](2026-10-28_s2-tv2_lam-sach-va-xuat-csv.md) |
| 2026-10-28 | TV2 (UncleThing) | [Nghiên cứu chunking trên 200 trang](2026-10-28_s2-tv2_nghien-cuu-chunking-200-trang.md) |
| 2026-10-28 | TV2 (UncleThing) | [Prototype chunking có cấu trúc](2026-10-28_s2-tv2_chunking-co-cau-truc.md) |
| 2026-10-28 | TV2 (UncleThing) | [Đẩy mã nguồn làm sạch và chunking lên GitHub](2026-10-28_s2-tv2_day-ma-nguon-github.md) |
| 2026-10-28 | TV4 (QuyVuiVe) | [Web: đối chiếu OpenAPI v1 và tích hợp API mock Sprint 2](2026-10-28_s2-tv4_web-api-mock.md) |
| 2026-10-29 | TV4 (QuyVuiVe) | [Favicon HoanGiapVang](2026-10-29_s2-tv4_favicon.md) |
| 2026-10-29 | TV4 (QuyVuiVe) | [Đổi font Agmena và sửa lỗi khởi động web](2026-10-29_s2-tv4_font-va-khoi-dong-web.md) |
| 2026-10-29 | TV4 (QuyVuiVe) | [Cài Taste Skill cho công việc frontend](2026-10-29_s2-tv4_cai-taste-skill.md) |
| 2026-10-29 | TV4 (QuyVuiVe) | [Tinh chỉnh giao diện chat bằng Taste Skill](2026-10-29_s2-tv4_tinh-chinh-giao-dien-taste.md) |
| 2026-10-30 | TV4 (QuyVuiVe) | [Bot ask và API client mock Sprint 2](2026-10-30_s2-tv4_bot-ask-api-mock.md) |
| 2026-10-31 | TV4 (QuyVuiVe) | [Một lệnh chạy bot và API mock](2026-10-31_s2-tv4_make-bot-dev.md) |
| 2026-10-31 | TV4 (QuyVuiVe) | [Nút sidebar với vệt sáng Grace và icon item](2026-10-31_s2-tv4_sidebar-grace-menu.md) |
| 2026-10-31 | TV1 (Hoanbucon) | [Rate-limit, hội thoại bot theo external_ref, hạn thời gian](2026-10-31_s2-tv1_rate-limit-hoi-thoai-bot-timeout.md) |
