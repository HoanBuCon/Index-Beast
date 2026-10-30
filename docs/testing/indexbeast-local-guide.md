# Chạy và thử IndexBeast local

Từ gốc repository, mở Docker Desktop. Windows có thể gọi `make` từ PowerShell hoặc Git Bash;
cần GNU Make, Python venv backend hiện có, Node/npm và dependency web (`cd web; npm ci` nếu chưa cài).
Các target mới không tự cài thư viện, tải model, index hoặc gọi bài QA trả phí.

```powershell
make dev
```

Lệnh bật PostgreSQL/Qdrant/Redis rồi chạy API và Vite song song. Giữ terminal mở; Ctrl+C dừng API/web.
Docker tiếp tục chạy và giữ dữ liệu. Có thể tách thành ba terminal: `make up`, `make api`, `make web`.
`make down` dừng hạ tầng, không xóa volume.

Với cổng `.env` hiện tại, mở http://localhost:15173 và tạo hội thoại mới (API, không phải Xem thử).
Vite proxy `/api` tới backend theo `API_PORT`; không đưa DeepSeek key vào trình duyệt.
Kiểm health ở terminal khác:

```powershell
make health
make test-unit
```

`health` chỉ đọc trạng thái hạ tầng qua API. `test-unit` dùng đúng cấu hình pytest unit, không collect
integration hoặc gọi DeepSeek thật. `PYTHON` và `API_PORT` có thể override khi gọi make.
Nếu thiếu make, dùng lệnh PowerShell trong [hướng dẫn RAG](../../backend/app/rag/README.md).

## DeepSeek: cấu hình và giọng trả lời

Backend gửi cấu hình qua API; thay thông số trong giao diện chat/playground của DeepSeek không tự đổi ứng dụng này.
Giữ key trong `.env` gốc. Máy đã test dùng cấu hình dưới; không đổi collection nếu muốn dùng dữ liệu đã index:

```dotenv
CHAT_MODE=rag
RAG_THINKING_ENABLED=true
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096
```

Thinking đang dùng effort `low` trong adapter, không gửi temperature. Temperature 0.2 chỉ tác động khi
non-thinking; không phải nút chống ảo giác. Không thêm top_p/penalty tùy tiện.
Đối chiếu [tài liệu thinking chính thức](https://api-docs.deepseek.com/guides/thinking_mode/).
Prompt mới yêu cầu trả lời trực tiếp, tự nhiên, không lặp disclaimer; chỉ dè dặt ở chi tiết chưa rõ.
RAG vẫn chỉ dùng evidence, phân biệt suy đoán và không tự fallback sang kiến thức model.
Scope đã mở sang gameplay/build/quest. Xem [audit khả năng dữ liệu](2026-10-29_elden-ring-assistant-capabilities.md)
để biết phần nào có evidence và phần nào đã bị lọc khỏi artifact; tăng temperature không bù được dữ liệu thiếu.
Không bỏ validation citation/quote để đổi lấy câu trả lời trôi chảy. Thinking không bảo đảm mọi mệnh đề đều đúng.

Sau sửa `.env`, restart API; prompt được nạp khi ứng dụng dựng pipeline nên cũng restart sau sửa prompt.
Lần chat đầu có thể chậm vì nạp encoder. Chat thật dùng số dư DeepSeek; `make dev` chỉ khởi động server,
không tự gửi câu hỏi hoặc chạy index. Máy hiện tại đã có collection; Git không chứa vector/model/key.

Thử “Ranni là ai? Cha mẹ cô là ai?”, “Miquella và St. Trina có quan hệ thế nào?”, một câu EN
và một câu ngoài phạm vi. Bấm citation, đọc đoạn nguồn để kiểm từng khẳng định; không chỉ nhìn có citation.
Kết quả QA trước thay đổi prompt ở [báo cáo 29/10](2026-10-29_rag-integration-report.md);
chưa đánh giá chất lượng prompt mới bằng DeepSeek thật trong tác vụ này.
