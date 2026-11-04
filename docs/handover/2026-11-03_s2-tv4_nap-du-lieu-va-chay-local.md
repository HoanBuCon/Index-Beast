# Nạp dữ liệu và chuẩn bị chạy RAG trên máy TV4

Ngày: 03/11/2026 (Asia/Saigon). Nhánh: `docs/s2-tv4-nap-du-lieu-local`.

## Phạm vi và quyền thực hiện

- Người dùng TV4 yêu cầu trực tiếp thực hiện toàn bộ bước nạp dữ liệu và khởi động local sau khi được giải thích về migration, PostgreSQL, embedding và Qdrant.
- Đây là thao tác vận hành trên máy TV4 bằng công cụ đã có; không phải phần triển khai pipeline mới của TV4. Migration thuộc TV1, artifact và loader thuộc TV2, encoder/index/retrieval thuộc TV3.
- Không sửa mã nguồn backend, bot, frontend, planning hoặc README gốc. Không crawl, clean/chunk lại, chạy notebook hoặc gọi API LLM.
- Chỉ thay đổi cấu hình local trong `.env` (được Git bỏ qua), dữ liệu Docker, model cache và tài liệu bàn giao này cùng danh sách handover. Không commit, push hoặc mở PR.

## Trạng thái trước khi chạy

- Docker PostgreSQL, Qdrant, Redis hoạt động nhưng PostgreSQL chưa có bảng, Qdrant chưa có collection.
- Artifact `backend/data/chunk_runs/s2-full-v1` có 4.164 document, 23.765 chunk; chưa được nạp trên máy này.
- Backend chưa lắng nghe cổng API local, mode mặc định là mock, chưa có model trong cache cấu hình.

## Các bước và kết quả đã xác minh

1. Bật hạ tầng bằng `docker compose up -d --wait postgres qdrant redis`: cả ba healthy.
2. Chạy Alembic trong venv backend: schema đạt revision `0001`.
3. `scripts.data_pipeline load --input data/chunk_runs/s2-full-v1 --validate-only`: 4.164 document và 23.765 chunk hợp lệ, không ghi database.
4. Chạy loader thật: 4.164 document thành công, 23.765 chunk, 0 document lỗi. Đối chiếu lại bằng truy vấn COUNT trên PostgreSQL đạt đúng các số này.
5. Index theo policy pilot/en vào collection mới `lore_chunks_v2`: **hoàn tất**, exit 0; 18.368/18.368 bản ghi được embed và upsert, Qdrant có đúng 18.368 point, 0 bản ghi invalid. Có 5.397 chunk ngoài tập chọn, không phải lỗi index.
6. Report xác nhận hash artifact không đổi; payload của 8 point mẫu sau nạp khớp input. Không coi kiểm tra mẫu là đối chiếu toàn bộ payload/vector. Lượt hoàn chỉnh với 8 luồng mất khoảng 23 phút 40 giây cho index; không cộng thời gian lượt đầu bị dừng thành benchmark chính thức.
7. Sao lưu `.env` sang file `.env.before-rag-local-*` được Git bỏ qua; chuyển `CHAT_MODE` sang RAG và đồng bộ collection/policy/ngôn ngữ với lượt index. Giữ nguyên key và các cấu hình khác, không thay mặc định encoder trong code.
8. Chạy hybrid retrieval trực tiếp với câu thử tiếng Anh về Ranni: nhận 5 hit có văn bản, gồm trang `Ranni the Witch`. Kiểm tra này có embed query nhưng **không gọi LLM**; không phải đánh giá chất lượng câu trả lời.
9. Khởi động API và Vite local. GET API health, Swagger, web và health qua Vite proxy đều HTTP 200; PostgreSQL, Redis và Qdrant đều true.

## Quyết định vận hành

- Dùng chính artifact đã tải, giữ nguyên raw, clean và nội dung chunk.
- PostgreSQL lưu toàn bộ chunk; Qdrant chỉ nhận tập tiếng Anh theo policy hiện có. 5.397 chunk ngoài tập chọn không được coi là lỗi nạp.
- Dùng `scripts.benchmark_index --allow-write` để gọi chính `index_chunks` hiện có, đồng thời lưu tiến độ và kết quả xác minh. Report nằm ngoài Git trong thư mục tạm của Windows.
- Lượt đầu dùng 2 luồng CPU đã được dừng sau 1.376 point. Lượt thay thế dùng 8 luồng cho riêng tiến trình, upsert lại cùng ID vào cùng collection; không có hai writer đồng thời và không sinh bản ghi trùng do chạy lại.
- Không thay các mặc định encoder trong code. Cảnh báo symlink của Hugging Face trên Windows không chặn tải model; cache vẫn hoạt động.
- Chỉnh địa chỉ backend của bot về API local, không trỏ tới cổng Vite. Chỉ chuyển backend sang RAG sau khi index được xác minh hoàn tất; việc chuyển đã được thực hiện sau bước 6.

## Cách chạy sau khi hoàn tất thiết lập

Từ thư mục gốc, mở Docker Desktop rồi chạy `make dev` để bật hạ tầng, API và web. Muốn chỉ chạy backend: `make up` rồi `make api`. Bot chạy riêng bằng `make bot`.

`make bot-dev` ép backend về mock nên không dùng target này khi muốn hỏi bằng corpus thật. Dùng endpoint health để kiểm hạ tầng; health không xác nhận chất lượng câu trả lời RAG.

Sau thiết lập, API và web đã được bật nền và kiểm tra thành công. Swagger ở `/api/docs`; health ở `/api/v1/health`. Chưa chạy thêm bot Discord trong lượt thiết lập này.

Người dùng sau đó gặp `Port 15173 is already in use` khi tự chạy Vite. Đã xác minh PID 26220 là đúng Node/Vite được bật nền ở lượt thiết lập, rồi dừng riêng tiến trình này. API trên `http://127.0.0.1:18000` vẫn hoạt động, health HTTP 200. Người dùng chạy `make web` từ gốc repo hoặc `npm.cmd run dev` từ `web/` để quản lý frontend trong terminal của mình; không chạy `make dev` khi API nền vẫn giữ cổng 18000.

API được khởi động không có auto-reload; Vite vẫn có HMR. Log khởi động nằm trong `%TEMP%` với tiền tố `indexbeast-api-20261103-003642` và `indexbeast-web-20261103-003642` (hai file `.out.log`/`.err.log` mỗi dịch vụ). Report index hoàn tất: `%TEMP%/indexbeast-index-8threads-20261103-001212.json`.

Muốn chuyển sang chạy qua Makefile trong terminal, dừng đúng hai dịch vụ nền đang chiếm cổng trước (xác minh PID và command line bằng `Get-NetTCPConnection`/`Get-CimInstance Win32_Process`), sau đó chạy `make dev`. Không khởi động thêm một API/Vite thứ hai trên cùng cổng. Khi khởi động lại máy, dữ liệu vẫn ở Docker volume và model cache; không phải nạp/index lại chỉ để chạy demo.

## Giới hạn và việc còn lại

- Không tự gửi câu hỏi tới DeepSeek; chưa kết luận chất lượng hay độ đúng của câu trả lời và chưa kiểm thử `/ask` thực tế trên Discord.
- Key hiện có được giữ nguyên; chưa xác minh key/số dư bằng request trả phí. Người dùng tự thử câu hỏi thật từ web khi muốn kiểm tra generation.
- Không chạy lại unit suite/build vì không sửa code; kiểm tra thực tế tập trung vào migration, loader, số point/payload/hash, retrieval, HTTP health và proxy.
- Model, corpus, cấu hình bí mật và dữ liệu Docker không nằm trong Git. Thành viên khác cần chuẩn bị môi trường riêng hoặc thống nhất dịch vụ dùng chung với TV1/TV2/TV3.
