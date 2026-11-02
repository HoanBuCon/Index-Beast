# TV2 — khảo sát raw toàn corpus, phân vùng và đề xuất clean/chunk

Nhánh feature/s2-tv2-clean-chuan-hoa. Ngày 29/10/2026. Người dùng yêu cầu nghiên cứu và
lập kế hoạch; chưa cho chạy clean/chunk production toàn corpus. Không làm embedding,
retrieval, LLM, entities hoặc sửa schema TV1. Không tạo nhánh hệ thống thứ tư.

Mã: backend/ingest/debug/raw_scope_study.py. Test: tests/unit/test_raw_scope_study.py.
Kế hoạch: docs/tv2-full-raw-clean-chunk-plan.md. Lệnh CLI trong kế hoạch.

Đã khảo sát 4164 raw từ report/checkpoint (4157 thành công + 7 media failed), 24723 section
chẩn đoán, xác minh hash/ID/revision và input không đổi. Phân vùng tạm: base context 1295,
DLC evidence 524, mixed/review 566, unresolved 1779; không phải nhãn đã nghiệm thu.
Artifact local: backend/data/research_runs/s2-full-scope-20261029-v2, không đưa data lên Git.
v1 dừng do đường dẫn tương đối, không có summary nghiệm thu. Đã sửa đường dẫn và thêm
test cohort/không đổi raw. Mô phỏng được chạy lại sau khi bổ sung lang/source_type cho section
và tăng mẫu để có dialogue/long tail: 35 trang, 1195 chunk, max450, không review/error.
Không tạo bộ chunk production; sample gồm cả DLC/review nhằm thử cấu trúc.

Kiểm chứng: 154 unit tests passed, 11 integration tests deselected; 5 test mới gồm scope
không mặc định base, bỏ paragraph rỗng, marker DLC không loại cả bài, bỏ nav evidence,
manifest tương đối/cohort và bảo toàn input. Ruff check/format file mới đạt.

Giới hạn: marker scope hữu hạn, generic 2022 không đủ chứng cứ, content source/language
heuristic, speaker chưa có bằng chứng trực tiếp. Chunk cap/coverage không là benchmark
retrieval. Người dùng cần duyệt kế hoạch trước khi sửa luật và chạy clean toàn corpus.
Đã trả lời đường dẫn lore_clean.csv mẫu 200 trong khi nghiên cứu; chưa có bản final full.
