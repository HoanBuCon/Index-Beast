# Tài liệu bàn giao (`docs/handover/`)

Mỗi khi hoàn thành một nhóm task, người thực hiện ghi lại **quy tắc, quy ước, quyết định và bài học** mà người khác cần biết để tiếp tục — đặt cùng mã nguồn, review trong cùng PR.

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

Không ghi secret (token, mật khẩu, key) vào tài liệu bàn giao.

## Danh sách

| Ngày | Người | Chủ đề |
|---|---|---|
| 2026-10-19 | TV1 (Hoanbucon) | [Nền tảng backend, hạ tầng dev và cấu hình](2026-10-19_s1-tv1_nen-tang-va-cau-hinh.md) |
| 2026-10-19 | TV3 (MinhMuc) | [DeepSeek LLM](2026-10-19_s1-tv3_deepseek-llm.md) |
