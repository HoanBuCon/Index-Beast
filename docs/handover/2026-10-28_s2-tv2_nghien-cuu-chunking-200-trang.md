# Bàn giao TV2 nghiên cứu cấu trúc 200 trang cho chunking

Ngày: 28/10/2026. Chủ sở hữu: TV2, Sprint 2, nghiên cứu phục vụ FR-ING-04/05. Nhánh hiện tại feature/s2-tv2-lam-sach-va-xuat-csv; các thay đổi làm sạch trước đó của người dùng được giữ nguyên, tác vụ nghiên cứu bổ sung script/report/handover, chưa commit/push/merge.

## Đã thực hiện

Đọc ADR-003, schema hiện tại, handover làm sạch và 200 artifact processed của s2-csv-200-v1. Dùng tokenizer e5-small có sẵn trong cache local; không tải model/tokenizer, không chạy embedding/LLM/indexing hoặc crawl. Đã đo toàn bộ 1.353 section và block theo scope; đối chiếu processed với CSV/checksum và revision nguồn. Các source artifacts không bị thay đổi.

## Kết quả chính

783 section base theo heuristic, 564 review, 6 excluded. Chỉ 154/200 trang có section base. 603/783 section base dưới 100 token, median body 42; max 7.083 token ở Alexander Dialogue. 33 section vượt tổng budget 450; 29 vượt 512.

27/43 block thoại vượt 450 token. Raw còn 860 ô th có thể dùng nhận diện header/trigger; processed chưa có typed turns. 91 nhóm heading path trùng trên 56 trang; 508 section base có heading thiếu anchor dù có DOM locator. Cả 200 document thiếu updated_at; 83 section base có image_ids. Cần giữ provenance/variant context và xác nhận ý nghĩa timestamp.

Kết luận: phù hợp spike chunking có cấu trúc, chưa đủ để index tất cả 200 trang. Giữ cap tổng 450, chấp nhận chunk ngắn có nghĩa; không ép tối thiểu 300. Ưu tiên prose nguyên block; dialogue chia theo ngôn ngữ/trigger/turn từ raw. Overlap 30–50 chỉ trong section dài. Cửa sổ token 450/50 ước khoảng 918 trước merge, chưa đánh giá retrieval hoặc phát hành chunk thật.

## File và cách dùng

- backend/ingest/debug/chunk_readiness.py: nghiên cứu read-only, kiểm checksum/metadata và thống kê bằng tokenizer local.
- docs/chunk-readiness-200.md: báo cáo và đề xuất chi tiết.
- backend/data/studies/chunk-readiness-200-verified/chunk-readiness.json: số đo/section/block/DOM header examples, Git ignore.

```powershell
# Từ backend; output mới/rỗng, tokenizer phải có sẵn local
.venv/Scripts/python.exe -m ingest.debug.chunk_readiness --input data/clean_runs/s2-csv-200-v1 --tokenizer "<tokenizer.json-local>" --output data/studies/new-study
```

Tokenizer đã chạy: snapshot 614241f622f53c4eeff9890bdc4f31cfecc418b3 của intfloat/multilingual-e5-small; SHA-256 0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39. Report JSON ghi đường dẫn tokenizer thực tế để tái lập, không tải lại.

## Kiểm tra và giới hạn

Ruff check/format đạt cho script. Đã xác nhận counts, checksum CSV đúng report, processed content_hash khớp dòng clean, revision đúng, DOM table locator đúng và input không đổi. Không chạy lại test production vì không sửa module production trong tác vụ nghiên cứu. Các con số chunk là mô phỏng số cửa sổ, chưa kiểm semantic boundary; không dùng chúng như kết quả retrieval.

## Việc kế tiếp

TV2 bổ sung typed dialogue/anchor/variant context rồi thử chunker với kiểm token coverage và trigger coverage. Chưa sửa các phần đó trong lượt nghiên cứu này; chưa cập nhật trạng thái ADR-003 hoặc SRS. TV3 review metadata và đo retrieval theo vai trò; không sửa embedding/indexing/LLM/entities/DB của các thành viên khác. Các file làm sạch và CSV của lượt trước được giữ nguyên.
