# Bàn giao sửa trang trắng khi mở web qua HTTP LAN/VPN

TV3 — MinhMuc, nhóm 4 Hollows, 31/10/2026 (Asia/Saigon).
Nhánh `fix/s2-tv3-lan-http-uuid` từ develop `cf3c7ad`; chưa commit/push/PR/merge.
Người dùng báo localhost chạy nhưng cả máy host và thành viên mở IP đều không tải được giao diện.

## Chẩn đoán

- Vite đã lắng nghe `0.0.0.0:15173`, API chỉ nghe `127.0.0.1:18000` như thiết kế proxy.
- Từ máy host, HTML qua loopback, Ethernet, Wi-Fi và Radmin VPN đều HTTP 200.
- `ChatPage.fresh()` gọi trực tiếp `crypto.randomUUID()` trong khởi tạo React state;
  API request ID, message ID và frontend demo cũng gọi API này trực tiếp.
- `randomUUID()` chỉ có trong secure context. Localhost có thể dùng được nhưng HTTP qua IP không được
  hưởng ngoại lệ localhost; do đó code có thể throw khi dựng trang và khi gửi request.
  [MDN randomUUID](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/randomUUID),
  [MDN getRandomValues](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/getRandomValues).
- Lỗi riêng: health HTTP 503, postgres=false trong khi redis/qdrant=true.
  Container PostgreSQL còn publish cổng 5433, lệch `.env`/backend dùng 15432.

## Thay đổi và xử lý

- Thêm [uuid.ts](../../web/src/lib/uuid.ts): dùng native randomUUID khi có; nếu không thì tạo UUIDv4 bằng
  `getRandomValues`, đặt đúng version/variant bits. Không dùng Math.random; không có Web Crypto thì báo lỗi rõ.
- Thay tất cả lời gọi trực tiếp trong [ChatPage](../../web/src/pages/ChatPage.tsx),
  [API client](../../web/src/api/client.ts), [demo](../../web/src/api/demo.ts),
  [useChatStream](../../web/src/hooks/useChatStream.ts).
- [uuid.test.ts](../../web/tests/uuid.test.ts) kiểm native/fallback, version/variant, uniqueness mẫu và
  request header X-Request-ID khi không có randomUUID; fetch được mock, không gọi DeepSeek.
- [language.test.ts](../../web/tests/language.test.ts) render giao diện bằng React SSR/Vite với global crypto
  chỉ có getRandomValues, giữ các assertion UI/language/storage cũ. Không dùng nhiều SSR server song song
  chỉ để test UUID, tránh cảnh báo trùng WebSocket test port.
- Đã kiểm PostgreSQL dùng volume `index-beast_pgdata`, mount `/var/lib/postgresql`, rồi chạy
  `docker compose up -d --wait postgres`. Container recreate đúng mapping, giữ volume; không migration/xóa dữ liệu.
- Lượt sửa UUID không sửa `.env`, key, Vite proxy, backend, corpus hoặc Qdrant. Không đổi Firewall; rules Node.js hiện có là Allow.

## Kiểm chứng thực tế

- `npm test`: **21/21 đạt**, lượt cuối không còn cảnh báo trùng WebSocket.
- `npm run typecheck`, `npm run build`, Prettier check các file thay đổi đạt.
- `npm run test:integration`: **9/9 đạt**, backend FastAPI mock riêng; kiểm JSON/SSE/feedback/error/cancellation,
  không dùng backend RAG thật hoặc gọi LLM.
- Health sau sửa qua proxy web trên localhost, IP LAN và IP VPN: HTTP 200,
  postgres/redis/qdrant đều true. Backend hiện tại giữ nguyên tiến trình.
- HTTP probes chạy từ host; SSR là kiểm mô phỏng thiếu randomUUID, không phải chứng nhận trình duyệt ở máy thành viên.
  Sau khi yêu cầu hard refresh tại URL VPN, người dùng xác nhận: “Đã thấy giao diện và sử dụng được”.
  Xác nhận này áp dụng cho lần truy cập người dùng vừa thử, không tự suy ra mọi máy thành viên đã kiểm thành công.
- Không gọi DeepSeek, không chạy embedding/index, không mở Qdrant/PostgreSQL cho client VPN.

## Cách dùng và xử lý tiếp

Máy host chạy API local và web chia sẻ qua LAN/VPN; thành viên chỉ mở URL web.
Web gửi `/api` cùng origin, Vite proxy về API trên máy host nên không cần sửa CORS hoặc bind API ra mọi card mạng.

Từ web, dùng lệnh đã hướng dẫn (không tự mở thêm dev server nếu đã có một instance chạy):

```powershell
npm run dev -- --host 0.0.0.0
```

Hoặc bind riêng IP VPN. Người dùng truy cập IP LAN/VPN thật của máy host kèm WEB_PORT, không truy cập 0.0.0.0.
Sau cập nhật code cần Ctrl+F5; Vite hiện chạy có HMR nhưng hard refresh giúp loại state/cache lỗi cũ.

Nếu host đã mở được mà peer vẫn không kết nối, chạy trên máy peer:

```powershell
Test-NetConnection <IP-VPN-may-host> -Port <WEB_PORT>
```

Đó là kiểm kết nối từ peer; chưa chạy lệnh đó trên máy thành viên. Nếu TCP thất bại, kiểm chung mạng VPN,
tunnel/routing và firewall theo cổng; không tiếp tục thay UUID hoặc bật allowedHosts=true tùy tiện.
Hướng dẫn dùng localhost trước đây chưa bao phủ hạn chế secure-context này; bản sửa bổ sung trường hợp HTTP qua IP.

## Bổ sung lệnh make web theo yêu cầu người dùng

- Makefile đọc `WEB_HOST` từ `.env` gốc và truyền `--host` cho Vite; `.env.example` mặc định chỉ bind loopback.
- Đã đặt riêng `WEB_HOST` của máy người dùng sang chế độ chia sẻ web theo yêu cầu hiện tại,
  giữ nguyên các key, cổng và cấu hình khác. `make dev` cũng dùng target web này.
- Từ gốc repo chỉ cần `make web`. Có thể override một lần bằng `make web WEB_HOST=<IP-LAN-hoac-VPN>`
  hoặc `make web WEB_HOST=127.0.0.1` để chỉ local. Không đổi host của API hoặc proxy backend.
- Đã kiểm `make -n web`, override loopback/VPN và `make -n dev`; chỉ dry-run, không mở thêm server/trùng cổng.
  Không thêm unit test cho thay đổi lệnh chạy đơn giản; `git diff --check` đạt.
- Nếu server cũ đang chạy thì tiếp tục dùng hoặc Ctrl+C tại terminal đó trước khi chạy `make web` lại.
