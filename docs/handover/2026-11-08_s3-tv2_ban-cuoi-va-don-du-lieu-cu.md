# TV2 — Bản dữ liệu cuối và dọn các lượt cũ, 08/11/2026

Người dùng yêu cầu bàn giao raw + clean + chunk cuối và xóa dữ liệu cũ không
còn dùng. Thực hiện trên `fix/s3-tv2-chat-luong-du-lieu`; không commit/push/merge
trong lượt này. Không thay PostgreSQL/Qdrant, retrieval/LLM hoặc file cấu hình
của các thành viên khác.

## Điểm vào cuối

`D:/Index-Beast/backend/data/delivery/final/README.md` và `manifest.json`.

Thư mục con dùng Windows junction, không sao chép hoặc đổi đường dẫn vật lý:

| Thư mục | Đích trong backend/data | Nội dung |
|---|---|---|
| raw | raw/wikigg | snapshots: 4.164 trang JSON chứa HTML thô |
| clean | clean_runs/s3-quality-language-20261108 | content_clean_all.csv, review.csv, images.csv, processed/filtered |
| chunk | chunk_runs/s3-quality-final-20261108 | chunks.csv/jsonl: 31.055 chunk; 25.607 EN |
| media | media | 10.371 file ảnh tham chiếu, cache URL đã bỏ entry file không dùng |
| source | crawl_runs/s2-full-20261028 | report/checkpoint/inventory/media manifest để chạy lại |
| audit | research_runs/s3-rag-readiness-20261108 | kiểm chứng, mẫu review, bằng chứng và nhật ký xóa |

Giữ đường dẫn vật lý vì source_snapshot và input-fingerprints đã tham chiếu chúng.
Khi chuyển máy phải copy dữ liệu vật lý và tạo lại junction; chỉ copy thư mục final
không tạo một gói portable. Dữ liệu bị Git ignore, chưa upload GitHub.

## Đã xóa

53 thư mục cũ và 253 file không còn tham chiếu, khoảng 1,44 GB. Gồm các lượt
20/200 trang, repeat, clean/chunk S2, trial trung gian S3, delivery S2/trial cũ,
nghiên cứu cũ, reports/validation cũ, media manifest cũ và crawl history tạm.
Giữ local-setup vì là cấu hình/khôi phục môi trường, không phải corpus cũ.
Giữ kết quả audit hiện tại và 34 chunk bằng chứng nhỏ được golden review trích dẫn,
không giữ toàn bộ corpus cũ. Golden review lịch sử vẫn có citation đường dẫn S2;
file dữ liệu S2 đã xóa, tra bản trích tại audit/legacy-golden-source-evidence.jsonl.

Trước khi xóa: lập cleanup-plan, kiểm absolute target nằm trong backend/data,
không trùng dependency của bản cuối, từ chối reparse point trong cây cần xóa.
Xóa bằng Remove-Item -LiteralPath trong một shell PowerShell. Nhật ký thực tế:
audit/cleanup-result-20261108.json; kiểm tra sau xóa ở cleanup-validation-20261108.json.
Script dọn là one-shot, không chạy lại vì các target cũ đã không tồn tại.

## Code và tài liệu điều chỉnh

- `ingest/debug/readiness_retrieval.py`: prepare protocol mới mặc định đọc
  documents/chunks tại delivery/final; hỗ trợ --baseline-documents để chọn inventory
  khác. Không còn bắt buộc corpus S2 đã xóa. Protocol audit cũ giữ nguyên.
- `backend/ingest/README.md`, báo cáo/handover audit trước: trỏ điểm vào final.
- Các kiểm chứng trước xóa trong báo cáo audit vẫn là kết quả lịch sử có thật;
  sau yêu cầu mới này không còn bản S2 để chạy lại so sánh toàn corpus. Muốn tái
  tạo phải dùng raw được giữ và đúng phiên bản code/policy lịch sử.

## Kiểm tra và hạn chế

Đã đọc lại CSV, kiểm checksum các artifact được bàn giao, fingerprint input,
4.164 snapshot và 10.371 file ảnh còn tồn tại. Kiểm prepare protocol mới bằng
thư mục tạm ngoài data, không gọi mạng/encoder/LLM. Lint/diff kiểm sau sửa.
Chi tiết số dòng và checksum trong manifest/cleanup-validation.

Bản cuối vẫn là kết quả offline đã kiểm cấu trúc, chưa phải chứng nhận toàn bộ
ngữ nghĩa/LLM. Hai mẫu cần thêm context, bảng phức tạp và license ảnh vẫn cần
review như báo cáo audit. Không tự re-index production. Runner TV1 chỉ nhận prefix
S2 nên cần dùng CLI S3 rõ ràng trong README; chưa thay runner để tự dùng corpus mới.
