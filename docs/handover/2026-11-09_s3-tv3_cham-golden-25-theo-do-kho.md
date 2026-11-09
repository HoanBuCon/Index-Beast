# TV3 — Lưu và chấm 25 câu golden set theo độ khó

Ngày 09/11/2026 · MinhMuc · Nhánh tài liệu `docs/s3-tv3-golden25-review`.

- Lưu kết quả gốc của lượt test trên `develop` `6dfb6bf` và bảng chấm từng câu trong [báo cáo testing](../testing/2026-11-09_golden-25-by-difficulty/README.md).
- Chấm C và F theo thang 0–2, tách ba ca hành vi và một lỗi HTTP 502. Có 24/25 lượt đạt, C 48/48 trên 24 câu trả lời được, F 42/42 trên 21 câu có dữ kiện. Đây là điểm sơ bộ do Codex đối chiếu, chờ review chéo.
- Lượt test đã dùng DeepSeek và Tavily Auto với 25 câu. Phần lưu và chấm đọc lại report gốc. Tái hiện offline lỗi dấu phẩy ở `IB-GS-086` trong lượt kiểm tra trước khi lưu báo cáo.
- Đọc cột nhận xét theo ID rồi mở `report.json` để xem câu hỏi, câu trả lời và từng đoạn trích. Qdrant corpus có 18.383 point trước và sau lượt test.
