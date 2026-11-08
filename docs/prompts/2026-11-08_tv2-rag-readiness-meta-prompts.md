# Meta prompts đánh giá và sửa chất lượng dữ liệu TV2

Người dùng duyệt ngày 08/11/2026: kiểm dữ liệu và truy xuất bằng bằng chứng nguồn;
sửa clean/chunk TV2, xuất corpus thử riêng; không sửa RAG TV3. Chưa có ví dụ lỗi
người dùng, dùng golden hiện có và ca trang bị. Sau preflight thiếu key/Docker,
người dùng chọn hoàn tất offline/local trước; LLM để sau. Ngân sách API đã đề xuất
trần 0,50 USD, lượt offline không dùng ngân sách này. Không index/chỉnh production.

## Prompt điều phối

Bạn là Data Engineer của TV2, workspace D:/Index-Beast. Đọc AGENTS, quy ước, SRS,
kiến trúc, planning và handover trước khi sửa. Bảo toàn stash, raw, media, corpus cũ.
Kiểm nhánh riêng, không merge/push hoặc sửa công việc TV1/TV3/TV4 trong tác vụ này.
Xác định corpus từ manifest và checksum, không chọn trial theo mtime. Chia công việc
theo các prompt dưới đây, tự thực hiện và bàn giao kết quả thật. Không spawn agent.

## Prompt audit đầu vào và cấu trúc

Đọc toàn bộ clean/chunk cùng raw provenance. Lưu baseline checksum, số trang,
ngôn ngữ, source_type, độ dài body/full embedding_text, lỗi prefix/token limit,
metadata rỗng, chunk trùng, fragment UI, template và mâu thuẫn tab ngôn ngữ.
Chọn 50 chunk ngẫu nhiên trong tập EN được pilot dùng, seed cố định 20261108;
lưu ID/text/hash và nhận xét sạch/bẩn/review, không gọi đó là human ground truth.
Tách các ca rủi ro có chủ đích khỏi mẫu ngẫu nhiên. Không coi ngắn là rác tự động.
Kiểm xem stats còn đủ field/value/header/unit/variant hay mất ở bước nào, không
coi chỉ số xuất hiện đâu đó trong trang là giữ đúng fact tại vị trí nguồn.

## Prompt sửa dữ liệu TV2

Chỉ sửa core/text và ingest cùng tests/tài liệu của TV2. Dùng chế độ full hiện tại
để giữ gameplay fields/infobox stats có nguồn, loại production fields và template
có bằng chứng; sửa tab BR/TW và label hiển thị trùng; bảo toàn quote/dialogue/trigger.
Stats phải giữ item/title, nhóm cột, requirements/scaling và 1h/2h. Giữ bảng phức tạp
chưa hiểu ở review; không suy số cấp nâng cấp, patch hay ngữ cảnh thiếu từ raw.
Thêm context_type/table_header khi cần, giữ source_type riêng. Tránh mỗi field
infobox thành một chunk; vẫn đo đúng tokenizer 450 token cả prefix/context, overlap50.
Không thêm schema DB, không sửa retrieval/model/generator. Giữ tính tương thích
pipeline cũ khi caller không chọn chế độ full mới. Bump version của artifact mới.
Chạy subset20 và hồi quy/tests rồi full4164 vào run mới. Check source slices,
coverage, IDs, CSV round-trip, ảnh và checksum input trước/sau. Không đổi delivery.

## Prompt đánh giá truy xuất local

Đóng băng bộ câu hỏi trước khi sửa corpus. Golden100 hiện pending, chỉ dùng làm
source-URL diagnostic, không tự gán approval hoặc gọi là Recall/MRR chính thức.
Thêm ca raw-verified về stats (có expected evidence, source revision/hash). Không
index question, expected_answer, quote oracle hoặc rubric vào corpus/prompt runtime.
Embeddings phải do E5 thật tạo, đúng query:/passage:, dim384, hữu hạn và có kiểm
truncation; không tạo vector giả/tự suy điểm semantic. Ưu tiên model local/cache.
Khi không có index production khả dụng, dùng pool thí nghiệm chung trước/sau và ghi
rõ giới hạn pool; không suy điểm này là chất lượng full collection đang phục vụ.
So sánh source hit và evidence hit riêng: đúng trang nhưng thiếu fact không được
đánh evidence hit. Negative latest-patch/optimization case phải được ghi thiếu nguồn,
không lấy top cosine cao làm câu trả lời. Không sửa production retrieval để tăng điểm.

## Prompt nghiệm thu và bàn giao

Báo cáo ready/pilot-only/not-ready theo từng năng lực, kèm lỗi P0/P1 và bằng chứng.
Phân biệt corpus đủ cấu trúc vectorize với corpus đủ kiến thức trả lời. Không hứa
không hallucinate chỉ vì hash/token đạt. Ghi chất lượng mẫu, mức coverage nguồn và
case còn thiếu; không quy lỗi model nếu raw/clean không có evidence. Nêu chi phí
API thực (0 nếu không gọi), model cache/download, benchmark scope và việc chưa chạy.
Xuất mã/lệnh, run artifacts, before/after examples, tests, report và handover cùng
nhánh. Chỉ đề xuất TV3 reindex/eval end-to-end sau, không tự đổi collection/config.
