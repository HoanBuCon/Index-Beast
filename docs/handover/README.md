# Tài liệu bàn giao (`docs/handover/`)

Mỗi khi hoàn thành một nhóm task, người thực hiện ghi lại **quy tắc, quy ước, quyết định và bài học** mà người khác cần biết để tiếp tục — đặt cùng mã nguồn, review trong cùng PR.

Theo yêu cầu ngày **26/10/2026**, đây là bước bắt buộc trước khi báo hoàn tất cho mọi nhóm task có thay đổi file, bao gồm tài liệu, notebook, bộ đánh giá và xử lý sự cố Git. Hướng dẫn cho trợ lý được lưu tại [`AGENTS.md`](../AGENTS.md). Với câu hỏi giải thích không làm thay đổi file, không cần tạo handover mới.

## Quy ước đặt tên

```text
<YYYY-MM-DD>_s<sprint>-tv<thành-viên>_<ten-ngan-khong-dau>.md
```

| Phần | Ý nghĩa | Ví dụ |
|---|---|---|
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

| Ngày | Người | Chủ đề |
|---|---|---|
| 2026-10-19 | TV1 (Hoanbucon) | [Nền tảng backend, hạ tầng dev và cấu hình](2026-10-19_s1-tv1_nen-tang-va-cau-hinh.md) |
| 2026-10-19 | TV3 (MinhMuc) | [DeepSeek LLM](2026-10-19_s1-tv3_deepseek-llm.md) |
| 2026-10-24 | TV2 (UncleThing) | [Crawler, mẫu raw và dữ liệu ảnh](2026-10-24_s1-tv2_crawler-va-du-lieu-anh.md) |
| 2026-10-26 | TV3 (MinhMuc) | [RAG baseline armor, golden set v0 và xử lý Git](2026-10-26_s1-tv3_rag-baseline-va-golden-set.md) |
| 2026-10-26 | TV1 (Hoanbucon) | [Báo cáo bàn giao Sprint 1](2026-10-26_s1-tv1_bao-cao-ban-giao-sprint-1.md) |
| 2026-10-26 | TV1 (Hoanbucon) | [Báo cáo môn NLP (LaTeX)](2026-10-26_s1-tv1_bao-cao-nlp-latex.md) |
| 2026-10-28 | TV1 (Hoanbucon) | [Hợp đồng API v1, mock và lỗi chuẩn](2026-10-28_s2-tv1_api-contract-v1-va-loi-chuan.md) |
