# Meta prompts — tái tạo dữ liệu có cấu trúc từ raw cuối

Đã được người dùng chốt qua 4 câu hỏi: giữ raw cuối + ảnh + manifest/crawl state;
xóa clean/chunk/report cũ; thực hiện P0/P1/P2, không crawl bổ sung; giữ phần có
căn cứ, phần mơ hồ review; bàn giao raw/facts/clean/chunk/review/report offline,
không embedding/index/push. Đây là quyền thực hiện mới, thay trạng thái chờ duyệt
của đề xuất structured-tables ngày 08/11/2026. Chỉ làm TV2, không spawn subagent.

## 1. Điều phối và bảo toàn

Đọc AGENTS, quy ước, kiến trúc, ADR và kế hoạch bảng. Giữ nguyên thay đổi/stash
đang có trên nhánh fix/s3-tv2-chat-luong-du-lieu. Trước dọn, đóng băng danh sách
4.164 snapshot, media manifest và hash của input; giữ 15 ca fact raw để regression.
Không giữ cả corpus dẫn xuất cũ dưới tên backup. Cấu hình local-setup không phải
dữ liệu RAG, không xóa nhầm. Kiểm target tuyệt đối trong backend/data và junction
trước thao tác filesystem. Nếu công cụ chặn, không vượt chặn; ghi rõ phần còn lại.

## 2. Parser thuần trong core/text

Xử lý grid rowspan/colspan, header nhiều tầng và ô gốc. Không shift cột khi ô
gộp kéo qua hàng. Không tính toán/interpolate số thiếu. Giữ 0, dấu -, raw cell,
grade/coefficient, level/affinity/patch/locale và source locator. Màu không tự
chứng minh loại damage. Grid xung đột, header không rõ, nested layout, thiếu label
đưa review; phần độc lập có căn cứ vẫn được giữ. Phân loại tất cả bảng kể cả
UI/references/quote/catalog/crafting/shop/drop/dialogue và nhóm unknown.

## 3. Filter → transform → chunk

Inventory/decision trước facts. Facts có table/row/cell ID, nguồn/revision/hash,
đơn vị nếu có bằng chứng. Dùng schema riêng cho upgrade, infobox, các bảng gameplay,
dialogue và quote. Không xóa literal quote hoặc chỉ số đang giữ. Bảng chưa hiểu
được phải có review record, không ép keep. Không sinh caption hay gán mọi ảnh
trang vào mọi fact. Tích hợp pipeline hiện có bằng opt-in structured tables.
Xuất CSV UTF-8 BOM qua csv và JSONL; chỉ decision=keep vào clean/chunk. Chunk
giữ hàng/nhãn/số thành đơn vị nguyên, giới hạn toàn embedding_text 450 token.

## 4. Kiểm chứng và phát hiện lỗi

Test span conflict, rowspan=0, nested table, header nhiều tầng, grade/coeff,
placeholder, variant, locale, source scope và ID ổn định. Crystal Sword: 68/166
thuộc Atk, không Grd Boost; chưa đủ legend thì review damage type. Longsword
giữ 13 bảng. Chạy mẫu đa dạng trước, xem đầu ra, sửa lỗi rồi full 4.164 trang.
Hạch toán mỗi bảng và ô nguồn: keep/review/excluded có lý do. Kiểm 15 fact trang
bị baseline, stats đang giữ, CSV round-trip, provenance, token, ảnh và input hash.
Không công bố Recall/MRR/LLM accuracy vì lượt này không chạy retrieval/LLM.

## 5. Bàn giao

Chỉ giữ một bộ output mới trong data và điểm vào delivery/final; raw/media/source
trỏ nguồn thật, báo cáo mới đi cùng. Viết lệnh CLI, schema, số liệu trước/sau,
ví dụ lỗi và hạn chế còn lại; thêm handover đúng quy ước. Không gọi API AI/crawl,
không nạp DB/index, không tự commit/push/merge. Không gọi dữ liệu sạch hoàn toàn.
