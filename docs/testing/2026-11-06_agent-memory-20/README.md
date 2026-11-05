# Agent và semantic memory — preflight bộ 20 lượt

06/11/2026 · TV3 — MinhMuc · IndexBeast / 4 Hollows.

**Trạng thái thực tế: BLOCKED, chưa gửi lượt hỏi nào.** Không có đáp án để chấm correctness/faithfulness.
Đây không phải một đợt 20 câu thất bại do model, cũng không phải 20 câu đã chạy xong.

| Chỉ số | Thực tế |
|---|---:|
| User turn đã lên kế hoạch | 20 |
| Lượt đã gửi API chat | 0 |
| DeepSeek call | 0 |
| Tavily request | 0 |
| Embedding/model thật đã chạy | 0 |
| Database/collection test đã tạo | 0 |
| Migration thật đã chạy | 0 |

Raw snapshot: [report.json](report.json). Manifest SHA-256:
`8cf5d2cc3a75ee9c4cbd0725ee3e51f39a3bb7104629e785459c0b30bbf6b676`.
Các tên `test_database`/`test_memory_collection` trong snapshot là tên **dự kiến**, chưa được tạo.
`created_at` lưu UTC; ngày tại Asia/Saigon là 06/11/2026.

## Nguyên nhân và phạm vi đã kiểm

- PostgreSQL ở địa chỉ/cổng lấy từ settings trả `ConnectionRefusedError` ngay preflight.
- Probe Qdrant riêng cũng không kết nối được; runner chưa tới bước probe Qdrant sau PostgreSQL.
- Docker Desktop được thử khởi động; daemon không lên. Log backend báo
  `stopReason: engine linux/wsl failed to start`, `noVirtualizationReason: WslVirtualMachinePlatformNotEnabled`
  và `Virtual Machine Platform not enabled`.
- Đã dừng lệnh CLI start đang chờ sau khi xác định nguyên nhân. Không tự bật optional feature Windows,
  sửa cấu hình BIOS, reboot máy, flush Redis hoặc dùng database thật thay test resource.
- Không đọc được corpus point count từ server, nên không ghi một số count giả hoặc khẳng định đã kiểm server.

Đã chạy từ `backend`:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_agent_memory --execute --allow-llm --allow-web --allow-embedding --output ../docs/testing/2026-11-06_agent-memory-20
```

Runner dừng trước tạo resource, khởi tạo provider để gọi API hoặc warm encoder.
Đã chạy riêng lệnh plan và memory setup dry-run: không tạo client/model/write.
Không dùng fake output thay cho live answers. Không có AI-assisted score hoặc review của TV2.

## Manifest và chạy tiếp

Manifest `backend/eval/agent_memory_20.json` dùng 8 golden câu độc lập và 4 scenario x 3 lượt,
10 VI/10 EN. Có lore/mechanics/acquisition/build/route/quest, đổi chủ đề, correction,
ambiguity, khôi phục pending/memory sau service recreation và một request SSE.
Golden set gốc và nhãn review không thay đổi. Tập này là development smoke, không phải held-out test cuối.

Sau khi người vận hành khắc phục Virtual Machine Platform và xác nhận PostgreSQL/Qdrant/Redis đã chạy,
runner có thể chạy lại vào **thư mục mới**. Phần live còn lại vẫn là đúng 20 user turn, chưa dùng lượt nào:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_agent_memory --execute --allow-llm --allow-web --allow-embedding --output ../docs/testing/agent-memory-20-live-new
```

Lệnh trên là **hướng dẫn chưa chạy**. Giữ report preflight này làm dấu vết; không xóa/ghi đè nó.
Runner chỉ tạo DB/collection test riêng sau probe; không migrate database ứng dụng, reindex corpus hoặc tự retest lượt 21.
Thiết kế/setup/call budget/giới hạn trong [hướng dẫn agent](../../api/agent-semantic-memory.md).
