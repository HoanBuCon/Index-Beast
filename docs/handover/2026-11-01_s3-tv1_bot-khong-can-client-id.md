# Bot Discord không cần DISCORD_CLIENT_ID và DISCORD_GUILD_ID

| | |
|---|---|
| Ngày | 01/11/2026 |
| Người thực hiện | TV1 (Hoanbucon), theo yêu cầu người dùng; phần mã thuộc bot của TV4 |
| Nhánh | `feature/s3-tv1-bot-application-id` (từ `origin/develop` tại `fc23c66`) |

## Thay đổi

- `bot/src/config.ts`: `DISCORD_CLIENT_ID` không bắt buộc. Nếu có giá trị thì vẫn phải đúng dạng Application ID (17–20 chữ số). `DISCORD_GUILD_ID` vốn không được dùng.
- `bot/src/utils/application.ts` (mới): `resolveApplicationId()` dùng `DISCORD_CLIENT_ID` nếu có; nếu trống, gọi `GET /applications/@me` bằng token bot để lấy Application ID.
- `bot/src/deploy-commands.ts`: đăng ký lệnh global bằng Application ID ở trên.
- `bot/src/index.ts`: thông báo lỗi khởi động chỉ nhắc `DISCORD_TOKEN`.
- `.env.example`, `README.md` (mục Discord bot), `bot/IMPLEMENTATION.md`: ghi hai biến là không bắt buộc; README sửa mô tả cũ "dev đăng ký vào guild" cho đúng code (luôn global).
- `bot/tests/application.test.ts`: 5 test (biến trống, sai định dạng, dùng ID có sẵn không gọi Discord, đọc ID từ Discord, Discord trả dữ liệu sai).

## Kiểm tra trên máy TV1

- `npm run typecheck`, `npm test` (26/26), `npm run format:check`: đạt. Backend `test_env_example`: đạt.
- `make bot-deploy` với `DISCORD_CLIENT_ID` để trống: `Đã đăng ký slash commands.` (global).
- `make bot`: bot online với tên `Ohno Ringe#0947`.
- Trước đó, đường gọi API của bot (`createApiClient` thật, `channel=discord`) với `CHAT_MODE=rag`: có service token thì trả lời có nguồn; câu hỏi tiếp theo cùng `external_ref` giữ ngữ cảnh ("his wife" → Queen Marika); thiếu token thì 401.
- **Chưa xác nhận** lệnh `/ask` gõ trực tiếp trên Discord (cần người dùng thử; lệnh global có thể mất vài phút mới hiện).

## Lưu ý

`API_SERVICE_TOKEN` phải giống nhau ở bot và API (cùng `.env` gốc) và khác `change-me`; nếu không, `/ask` ở chế độ `rag` bị 401.
