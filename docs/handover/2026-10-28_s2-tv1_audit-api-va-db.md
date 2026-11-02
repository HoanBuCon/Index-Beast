# Sprint 2 TV1: audit mã API và DB sau khi merge PR #28, #29

| | |
|---|---|
| Ngày | 28/10/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `fix/s2-tv1-audit-db-session-va-id` (từ `origin/develop` tại `20b6b5c`; chưa có PR khi viết tài liệu này) |

## Đã sửa

| Rủi ro | Sửa |
|---|---|
| **Mất dữ liệu âm thầm.** `get_session` dùng mặc định của FastAPI nên commit chạy *sau* khi đã gửi response: commit lỗi thì client vẫn nhận 200. Đã kiểm chứng bằng app thử (scope mặc định trả 200, `scope="function"` trả 500). | Thêm `SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]` trong `app/api/deps.py`. Route ghi DB phải dùng `SessionDep`. Route SSE cần mở session riêng trong generator. |
| **Id document ngẫu nhiên.** `upsert_document` sinh `uuid4` cho trang mới; dựng lại DB sẽ đổi `document_id`, kéo theo đổi `chunk_id` và để lại point mồ côi trong Qdrant. | `core/ids.py`: `document_id(source, source_id)` và `chunk_id(doc_id, ordinal)` dùng uuid5; repository dùng `document_id` làm mặc định. TV2 dùng `chunk_id` khi chia đoạn. |
| **Câu hỏi toàn khoảng trắng** qua được `min_length=1` và sẽ tới LLM ở S3. | `ChatRequest.message` strip trước khi kiểm tra độ dài; trả 422. Hợp đồng OpenAPI không đổi. |

## Rủi ro ghi nhận, chưa sửa (đúng sprint của nó)

- **Chưa có xác thực và rate-limit (S4).** Khi nối `/chat` với LLM thật ở S3, chưa được mở API ra Internet trước khi có rate-limit, vì mỗi request tốn tiền LLM (NFR-COST-01).
- **`GET /conversations/{id}` không kiểm tra chủ sở hữu.** UUID khó đoán, nhưng ai có id đều đọc được lịch sử, kể cả hội thoại Discord. S3/S4 cần gắn hội thoại với `channel` và `external_ref`, đồng thời từ chối `conversation_id` của kênh khác.
- **Dịch vụ mock luôn được gắn**, kể cả khi `environment=prod`. Chưa deploy trước S5 nên chưa ảnh hưởng; S3 thay bằng dịch vụ thật.
- Mock giữ tối đa 500 hội thoại trong RAM nhưng không giới hạn số tin mỗi hội thoại. Chỉ dùng ở dev.
- JSON 500 do middleware tự trả nằm ngoài CORS, nên trình duyệt khác origin thấy lỗi CORS thay vì JSON. Production dùng chung origin qua Caddy nên không ảnh hưởng.
- `ix_chunks_document_id` trùng với unique `(document_id, ordinal)`: tốn thêm chi phí ghi. Bỏ ở migration kế tiếp.
- Feedback chưa chống gửi trùng, cùng chỗ với rate-limit ở S4.

## Kiểm tra đã chạy

- `pytest` backend: 92 passed (3 test mới: commit lỗi trả 500, id ổn định, câu toàn khoảng trắng bị từ chối).
- `pytest -m integration tests/integration/test_db_schema.py`: 10 passed trên PostgreSQL thật, gồm kiểm tra upsert trả đúng `document_id`.
- `ruff check`, `ruff format --check`, `export_openapi --check` đạt.
- CI trên GitHub của `develop` tại `20b6b5c`: backend, web, bot đều success (đọc qua GitHub API). Chưa chạy CI cho nhánh này.
