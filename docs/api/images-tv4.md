# Backend trả ảnh RAG — bàn giao TV4

TV3 — MinhMuc, 31/10/2026. Nhánh `feature/s2-tv3-rag-images`.
Đây là truy xuất ảnh raster local đã có của TV2; không tạo ảnh, OCR, hiểu ảnh đầu vào hoặc CLIP search.
Tác vụ backend ban đầu không sửa frontend/bot. Ngày 31/10/2026 TV3 đã nối contract ảnh vào web thật,
xem [bàn giao tích hợp](../handover/2026-10-31_s2-tv3_noi-anh-backend-web.md).
[OpenAPI](openapi.json) được sinh lại bằng script của repository.

## Contract additive, client text cũ vẫn chạy

| Vị trí | Field mới |
|---|---|
| POST /api/v1/chat | `images`, list mặc định rỗng, tối đa 3 |
| GET /api/v1/conversations/{id} | `messages[].images`, mặc định rỗng |
| SSE `sources` | `data.images`, cùng payload với `data.sources`, tối đa 3 |
| GET /api/v1/images/{id} | Bytes PNG/JPEG/WebP/GIF, hoặc error JSON 404 |

Không thêm event `images`, không đổi event `done`/`token` hoặc field cũ. Web đã đọc images từ JSON và event sources,
lưu metadata trong message/history, ánh xạ sang component ảnh TV4. Client cũ vẫn có thể bỏ qua field bổ sung.
Không cần request opt-in; server dùng RAG_IMAGES_ENABLED. mock/llm_only trả images=[] cho chat.

Ảnh chỉ được resolve **sau khi đáp án và citation validation thành công**. SSE vẫn stream token thật trước đó,
sau đó gửi sources (có ảnh) và done. Nếu generation/citation lỗi, không gửi ảnh hoặc done thành công.
Ảnh thiếu/hỏng hoặc resolver lỗi không làm hỏng đáp án text đã hợp lệ; trả images=[] hoặc phần ảnh hợp lệ còn lại.

## Schema một ảnh

| Field | Ý nghĩa |
|---|---|
| id | SHA-256 64 ký tự hex của blob, không phải occurrence_id |
| url | URL tương đối `/api/v1/images/{id}`, dùng làm src trên web cùng origin |
| caption / alt | Text từ metadata, có thể null; backend không bịa mô tả ảnh |
| source_url | Trang nguồn của citation đầu tiên đóng góp ảnh, không phải file path hoặc URL tải bytes |
| source_indices | Các số citation 1-based thực sự đóng góp ảnh; tra theo Source.index, không theo vị trí array |
| attribution / license | Metadata nếu có; null khi chưa có; plain text, không render bằng HTML |
| license_status | Giữ trạng thái gốc, ví dụ unknown_review_required; không phải backend đã duyệt quyền sử dụng |
| file_page_url | Trang mô tả file ở wiki nếu có và là URL HTTP(S) hợp lệ |
| game_scope / release_scope | Metadata gốc của context đóng góp ảnh; unknown/candidate giữ nguyên |

Ví dụ response **minh họa contract**, không phải một lượt DeepSeek được chạy trong tác vụ này:

```json
{
  "conversation_id": "11111111-1111-4111-8111-111111111111",
  "message_id": "22222222-2222-4222-8222-222222222222",
  "answer": "Infobox trong snapshot ghi Bloodhound's Fang gây blood loss buildup 55 [1].",
  "sources": [{
    "index": 1, "title": "Bloodhound's Fang", "section": "Infobox",
    "url": "https://eldenring.wiki.gg/wiki/Bloodhound%27s_Fang",
    "text": "effects: Causes blood loss buildup (55)", "origin": "corpus"
  }],
  "grounded": true,
  "latency_ms": 1000,
  "images": [{
    "id": "6545369b5499a0f38df4f4b3b54cb75159990d6901324002695d666ea4cc4c7d",
    "url": "/api/v1/images/6545369b5499a0f38df4f4b3b54cb75159990d6901324002695d666ea4cc4c7d",
    "caption": null,
    "alt": "ER Icon weapon Bloodhound's Fang.png",
    "source_url": "https://eldenring.wiki.gg/wiki/Bloodhound%27s_Fang",
    "source_indices": [1],
    "attribution": null, "license": null, "license_status": "unknown_review_required",
    "file_page_url": "https://eldenring.wiki.gg/wiki/File:ER_Icon_weapon_Bloodhound%27s_Fang.png",
    "game_scope": "elden_ring", "release_scope": "base_candidate"
  }]
}
```

Ví dụ SSE không có ảnh (wire hợp lệ, ID chỉ minh họa):

```text
event: status
data: {"status":"generating"}

event: token
data: {"token":"Mình chưa có đủ bằng chứng để trả lời."}

event: sources
data: {"sources":[],"images":[]}

event: done
data: {"conversation_id":"11111111-1111-4111-8111-111111111111","message_id":"22222222-2222-4222-8222-222222222222","grounded":false,"latency_ms":1000}

```

Khi có ảnh, event sources dùng cùng mảng images như JSON minh họa trên. Web đã giữ ảnh trong state/history;
không tìm `images` trong từng token hoặc suy ra ảnh từ text model. Backend history vẫn RAM, không phải lưu DB bền vững.

## Chính sách chọn và phục vụ

- Chỉ lấy image_ids có trong hit thực sự được trích, image_association=section.
- Join đúng source wikigg, source_id, revision_id, section và image_id vào CSV và document metadata.
- Chỉ association exact_section, status downloaded/cached; loại UI, gallery/review/failed, review rejected nếu có.
- Không tự lấy infobox của cùng trang nếu chunk được trích không có liên kết đó. Không fallback gallery hoặc ảnh cùng tên.
- Dedup theo blob hash, tối đa 3, thứ tự citation rồi image_ids của artifact; caption từ occurrence đầu tiên.
  Không merge source_indices của cùng blob khi game/release context khác nhau.
- spoilers=false cần cả chunk và ảnh có nhãn an toàn rõ ràng. CSV hiện thiếu spoiler_level, vì vậy thường không có ảnh.
- Endpoint chỉ phục vụ ID có trong catalog đủ provenance; không nhận path hoặc proxy remote URL.
  Resolve đường dẫn dưới media root, kiểm hash bytes, MIME/extension, byte/pixel limits và Pillow verify/decode.
  GIF kiểm frame đầu, không hứa kiểm toàn bộ frame animation.
- Response có Content-Type đúng, nosniff, inline filename theo hash, Cache-Control public/max-age=3600, ETag.
  If-None-Match có thể trả 304 nhưng vẫn kiểm file hợp lệ; ảnh mất/bị đổi hash trả 404, không trả nội dung ngoài root.
- Backend trả bytes đã kiểm trong cùng lần đọc, không đưa path local cho trình duyệt. Root media cần do ứng dụng quản lý.

## Cấu hình và dữ liệu phải có

Các biến mẫu trong `.env.example` và Compose, đường dẫn tương đối từ backend:

```dotenv
RAG_IMAGES_ENABLED=true
RAG_IMAGES_CATALOG=data/clean_runs/s2-full-v2/images.csv
RAG_IMAGES_DOCUMENTS=data/chunk_runs/s2-full-v1/documents.jsonl
RAG_IMAGES_ROOT=data/media/blobs
RAG_IMAGES_MANIFESTS=data/crawl_runs/s2-full-20261028/media
RAG_IMAGES_MAX_BYTES=20000000
RAG_IMAGES_MAX_PIXELS=40000000
```

Không sửa `.env` thật trong tác vụ. Defaults khớp artifact local; Docker đã mount ./backend/data vào /app/data.
Catalog load lazy một lần/app trong worker, không scan mỗi request; restart app để reload khi thay catalog.
Metadata manifest có cache giới hạn 64 entry. Không cache toàn bộ bytes ảnh; mỗi request chỉ xác minh số ảnh hữu hạn.
Đường dẫn absolute Windows do TV2 ghi được relocate về root blob cấu hình bằng layout content-addressed đã kiểm,
không cố đọc ổ D: của máy producer khi chạy trên máy khác hoặc Docker.

Máy clone mới cần CSV, documents JSONL và blob tương ứng (manifest bổ sung attribution khi có).
Thiếu dữ liệu thì text vẫn chạy, images=[] hoặc endpoint 404. Không cần reindex vì metadata image_ids đã nằm trong payload.

## TV4 tích hợp

- Web: render `image.url` tương đối trên cùng origin; Vite/Caddy đã proxy `/api`, dùng được LAN/VPN như text.
  Không ghép localhost, không đưa key DeepSeek vào web. Null caption dùng alt nếu có hoặc nhãn UI trung tính.
- Khi ảnh 404, ẩn/hiện placeholder; không đổi ảnh lỗi thành lỗi cả message và không retry vô hạn.
- Hiển thị source/attribution/license theo metadata; unknown không được đổi thành nhãn “đã cấp phép”.
- Discord: relative URL không dùng trực tiếp làm embed URL. Bot có thể tải ảnh từ backend rồi gửi attachment,
  hoặc dùng absolute URL HTTPS công khai mà Discord truy cập được. IP VPN chỉ truy cập trong VPN, không mặc định
  là URL công khai cho Discord. TV3 chưa sửa bot hoặc gửi ảnh lên Discord thật.

## Tự test và kiểm chứng đã chạy

Khởi động lại backend để nạp schema/code mới. `make dev` dùng hạ tầng/cấu hình hiện tại; không index lại.
Trong Swagger `/api/docs`, thử GET /api/v1/images/{id} bằng ID Bloodhound's Fang trong ví dụ.
Sau đó thử POST /chat hoặc /chat/stream, bật spoilers=true để baseline ảnh không bị loại vì thiếu nhãn.
Chat thật dùng DeepSeek credits; **chưa gọi trong tác vụ này**. Không cam kết model sẽ trích đúng section chứa ảnh.

Đã chạy offline: fake model/retriever cho JSON/SSE/history; local TestClient cho ba blob thật (PNG/JPEG),
read-only census và mẫu 30 file khớp hash/định dạng. Xem [audit JSON](../testing/2026-10-31_images-audit.json).
Chưa test browser hiển thị ảnh, Discord Gateway, container API hoặc lượt chat DeepSeek thật.

Kiểm thử cuối: backend **368 passed, 1 warning** so với baseline 331; warning Qdrant memory dự kiến.
Ruff lint/format, OpenAPI check và pip check đạt. Web hiện có 21 unit + 9 integration test, typecheck đạt,
không sửa source web. Symlink/junction escape kiểm bằng fixture mô phỏng Path.resolve; chưa load test ảnh.
