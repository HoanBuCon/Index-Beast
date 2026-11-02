# Hướng dẫn trình bày đăng ký đề tài IndexBeast

Nhóm 4 Hollows. Phạm vi lore Elden Ring base game. Thời lượng đề xuất 10–12 phút cho 14 slide chính, 2 slide phụ lục.

Kế hoạch 9 tuần là bản đề xuất theo yêu cầu học phần, tính từ 19/10/2026. Tài liệu sprint 6 tuần cũ trong repo chưa được chuyển đổi; khi chốt mốc học phần cần đồng bộ planning/sprint_plan.json và tài liệu sinh tự động. Không coi các nhiệm vụ trong bản đề xuất là việc đã hoàn thành.

Trước khi nộp: điền họ tên, MSSV, lớp, giảng viên. Đọc phần Notes của từng slide khi tập nói.

## Slide 1 IndexBeast

Chatbot RAG hỏi đáp lore
Elden Ring base game

**Gợi ý lời nói:** Chào thầy/cô, nhóm chúng em là 4 Hollows. Nhóm đăng ký đề tài xây dựng chatbot RAG hỏi đáp lore Elden Ring base game bằng tiếng Việt và tiếng Anh. Sản phẩm dự kiến có web và Discord dùng chung một backend. Hôm nay nhóm trình bày bài toán, khảo sát ban đầu, phân công và kế hoạch 9 tuần. Thời lượng đề xuất: 10–12 phút cho slide 1–14, slide 15–16 để tham khảo khi hỏi đáp. Thay TV1–TV4 bằng họ tên và MSSV trước khi nộp.

## Slide 2 Bài toán và người sử dụng

- Người chơi hỏi về nhân vật, sự kiện, địa điểm và mô tả vật phẩm.
- Thông tin nằm rải rác trong các trang và đoạn văn khác nhau.
- Sinh viên và giảng viên cần thử chatbot, mở nguồn và kiểm tra câu trả lời.

**Gợi ý lời nói:** Đây là mô tả bài toán dự kiến, chưa phải kết quả khảo sát người dùng. Ví dụ đầu vào là “Godrick the Grafted là ai?”. Đầu ra cần trả lời ngắn, đúng ngôn ngữ người hỏi, giữ tên riêng và dẫn đến đoạn nguồn. Khi không đủ bằng chứng, chatbot cần nói rõ giới hạn thay vì suy đoán.

## Slide 3 Phạm vi và sản phẩm dự kiến

- Nội dung: lore Elden Ring base game, hỗ trợ tiếng Việt và tiếng Anh.
- Web chat và lệnh /ask trên Discord sử dụng chung API.
- Mỗi câu trả lời kèm liên kết nguồn và đoạn văn tham chiếu.
- Bàn giao corpus có metadata, mã nguồn, bộ đánh giá và báo cáo thí nghiệm.

**Gợi ý lời nói:** Nhóm tập trung hỏi đáp lore. Bài toán tính sát thương, tối ưu build và voice chat nằm ngoài mục tiêu sản phẩm. Web và Discord là hai giao diện kiểm thử cho cùng hệ thống NLP. Những sản phẩm liệt kê ở đây là đầu ra dự kiến, không tuyên bố đã hoàn thành.

## Slide 4 Câu hỏi nghiên cứu NLP

- Hybrid có tìm đúng nguồn hơn dense hoặc BM25 riêng lẻ không?
- Reranker cải thiện thứ hạng nguồn đến mức nào, với chi phí độ trễ bao nhiêu?
- Chunking và truy vấn tiếng Việt ảnh hưởng thế nào đến retrieval?
- Ngữ cảnh truy xuất có giúp câu trả lời bám nguồn hơn LLM không dùng RAG?

**Gợi ý lời nói:** Giữ cố định corpus, tập test và cấu hình sinh khi so sánh. Chúng em sẽ đo mức cải thiện thực tế, không mặc định hybrid hay rerank chắc chắn tốt hơn. Khía cạnh nghiên cứu nằm ở thiết kế đối chứng, đánh giá và phân tích lỗi, không chỉ ở việc gọi API LLM.

Nguồn: https://arxiv.org/abs/2005.11401, https://qdrant.tech/documentation/search/hybrid-queries/

## Slide 5 Khảo sát phương pháp ban đầu

| Phương pháp | Điểm cần khảo sát | Vai trò trong đề tài |
| --- | --- | --- |
| LLM không RAG | Thiếu nguồn kiểm chứng | Đối chứng câu trả lời |
| BM25 | Khớp từ khóa và tên riêng | Baseline từ vựng |
| Dense đa ngôn ngữ | Hiểu nghĩa, truy vấn Việt/Anh | Baseline ngữ nghĩa |
| Hybrid + rerank | Kết hợp kết quả, chấm lại độ liên quan | Cấu hình cần kiểm nghiệm |

**Gợi ý lời nói:** Survey ban đầu dựa trên bài RAG của Lewis và cộng sự, model card multilingual-e5-small và tài liệu hybrid queries của Qdrant. Bảng này tóm tắt hướng áp dụng, không phải kết quả benchmark của nhóm. Tuần 1 mỗi thành viên phải đọc tài liệu gốc và ghi bài toán, phương pháp, dữ liệu, metric, hạn chế và ý nghĩa đối với IndexBeast.

Nguồn: https://arxiv.org/abs/2005.11401, https://huggingface.co/intfloat/multilingual-e5-small, https://qdrant.tech/documentation/search/hybrid-queries/

## Slide 6 Dữ liệu và khảo sát nguồn

- Nguồn ứng viên: wiki.gg, Wikipedia và Fan APIs.
- Ưu tiên mô tả nhân vật, sự kiện, địa điểm, vật phẩm thuộc base game.
- Lưu title, section, URL, revision và thời điểm lấy dữ liệu.
- Tuần 1 xác minh truy cập, giấy phép và chất lượng trước khi chốt nguồn.

**Gợi ý lời nói:** Chưa có thống kê corpus đã crawl trong repo. Không nêu số trang toàn bộ khi chưa đo. Tuần 1 lấy mẫu 20–30 trang, kiểm tra API, quyền sử dụng, cách ghi nguồn và độ sạch. Fan APIs là nguồn ứng viên cho danh sách thực thể, không mặc định đủ lore. wiki.gg chưa truy cập được bằng công cụ khảo sát trong lần chuẩn bị này, nên việc xác minh nguồn vẫn là công việc cần làm. Ảnh minh họa game không phải ảnh dữ liệu đã thu thập.

Nguồn: https://en.bandainamcoent.eu/elden-ring/elden-ring, https://eldenring.wiki.gg/, https://en.wikipedia.org/wiki/Elden_Ring, https://eldenring.fanapis.com/

## Slide 7 Luồng xử lý RAG dự kiến

| Giai đoạn | Đầu vào và xử lý | Đầu ra |
| --- | --- | --- |
| Chuẩn bị dữ liệu | Thu thập, làm sạch, chia đoạn | Corpus và chunk có nguồn |
| Đánh chỉ mục | Embedding và BM25 | Qdrant |
| Truy xuất | Câu hỏi, viết lại truy vấn nếu cần | Top-k đoạn, sau hybrid/rerank |
| Sinh câu trả lời | Câu hỏi và ngữ cảnh có đánh số | Câu trả lời kèm trích dẫn |

**Gợi ý lời nói:** Pipeline offline có thể chạy lại từ artifact từng bước. Pipeline online tìm bằng chứng trước khi sinh. Nguồn số [1], [2] trong câu trả lời phải ánh xạ tới chunk thật; việc có số trích dẫn chưa chứng minh câu trả lời đúng. Luồng này sẽ triển khai dần: dense baseline trước, hybrid và rerank sau.

Nguồn: https://arxiv.org/abs/2005.11401, https://qdrant.tech/documentation/search/hybrid-queries/

## Slide 8 Kiến trúc triển khai dự kiến

- React web và Discord bot gọi FastAPI dùng chung.
- Qdrant lưu vector; PostgreSQL lưu hội thoại, metadata và feedback.
- Docker Compose đóng gói các dịch vụ; Redis bổ sung khi cần cache hoặc rate limit.
- LLM qua API cấu hình được; lựa chọn local dùng llama.cpp sau khi đo tài nguyên.

**Gợi ý lời nói:** Đây là lựa chọn kiến trúc, chưa phải công suất hệ thống đã kiểm chứng. API LLM giúp nhóm có baseline sớm. Adapter gom lời gọi model để đổi nhà cung cấp. Không chốt tên model, giá hoặc RAM khi chưa kiểm tra. Với local, llama.cpp là phương án khảo sát; phải đo tốc độ và chất lượng trên máy thật trước khi chọn.

Nguồn: https://github.com/ggml-org/llama.cpp/tree/master/tools/server, D:/Index-Beast/docs/04_ARCHITECTURE.md

## Slide 9 Thiết kế đánh giá

- Dự kiến 120 câu, ít nhất 50% tiếng Việt, có nguồn và đáp án tham chiếu.
- Tách 60 câu dev và 60 câu test theo nhóm chủ đề hoặc thực thể.
- Retrieval: Recall@5, Recall@10, MRR; báo cáo riêng câu Việt và Anh.
- Generation: đúng đáp án, bám nguồn, trích dẫn hợp lệ; đo độ trễ và chi phí.

**Gợi ý lời nói:** Đây là quy mô đề xuất. Các biến thể câu hỏi gần trùng phải cùng một phía của split để tránh rò rỉ. Tập test chỉ mở sau khi chốt cấu hình. Định nghĩa Recall@k bằng tỷ lệ nguồn liên quan được tìm thấy trong k kết quả trên các câu có nhãn nguồn. MRR là trung bình nghịch đảo hạng của kết quả đúng đầu tiên. Người chấm đối chiếu câu trả lời với nguồn. Nếu dùng LLM-as-judge phải kiểm tra chéo bằng người và ghi rubric.

## Slide 10 Kế hoạch 9 tuần

| Tuần | Thời gian | Trọng tâm | Đầu ra |
| --- | --- | --- | --- |
| 1 | 19–25/10 | Đăng ký, survey, khảo sát dữ liệu | Đề cương, bảng survey, 30 câu mẫu |
| 2 | 26/10–01/11 | Crawler và làm sạch dữ liệu | Corpus mẫu, schema và báo cáo chất lượng |
| 3 | 02–08/11 | Chunk, embedding và Qdrant | Dense baseline và Recall@5 ban đầu |
| 4 | 09–15/11 | BM25, hybrid và rerank | Bảng so sánh retrieval trên tập dev |
| 5 | 16–22/11 | Generation và API dùng chung | Câu trả lời có nguồn, lưu hội thoại |

**Gợi ý lời nói:** Giả định tuần 1 bắt đầu ngày 19/10/2026. Kế hoạch này là đề xuất 9 tuần cho học phần, thay cho mốc 6 tuần khi trình bày. Tuần 1 hoàn tất đăng ký, phân công, bài toán, dữ liệu và survey. Mỗi tuần có sản phẩm bàn giao kiểm tra được, không chỉ ghi “tìm hiểu” hoặc “code”. Tuần 3 có baseline; tuần 5 có pipeline sinh câu trả lời.

## Slide 11 Tích hợp và hoàn thành

| Tuần | Thời gian | Trọng tâm | Đầu ra |
| --- | --- | --- | --- |
| 6 | 23–29/11 | Tích hợp web và Discord | MVP chạy được trên cả hai kênh |
| 7 | 30/11–06/12 | Đánh giá, phân tích lỗi | Bảng thí nghiệm, sửa lỗi theo nhóm |
| 8 | 07–13/12 | Docker deploy và kiểm thử người dùng | Bản demo, feedback, bản sao lưu |
| 9 | 14–20/12 | Ổn định và báo cáo cuối | Release, báo cáo, slide và video demo |

**Gợi ý lời nói:** Cuối tuần 6 có MVP web và Discord. Tuần 7 tập trung đánh giá, tuần 8 triển khai và lấy feedback. Tuần 9 dành cho sửa lỗi, báo cáo và tập dượt. Nếu chậm tiến độ, giảm trang admin, cache và các tính năng giao diện phụ để giữ đủ thời gian đánh giá NLP.

## Slide 12 Phân công nhóm 4 Hollows

| Thành viên | Phụ trách chính | Đầu ra chịu trách nhiệm |
| --- | --- | --- |
| TV1 (Hoanbucon) | Lead, backend, DevOps | API, DB, Docker, tích hợp và deploy |
| TV2 (UncleThing) | Dữ liệu | Khảo sát nguồn, crawler, corpus sạch |
| TV3 (MinhMuc) | RAG và đánh giá | Retrieval, generation, thí nghiệm |
| TV4 (QuyVuiVe) | Web và Discord | Giao diện, /ask, phản hồi người dùng |

**Gợi ý lời nói:** Điền tên và MSSV trước khi nộp. Mỗi hạng mục có một người chịu trách nhiệm chính và một người review. TV2 và TV3 thống nhất schema chunk; TV1 và TV4 thống nhất API sớm. Cả nhóm cùng đóng góp câu hỏi và review đáp án. Quy trình Git theo docs/quy_uoc.md: feature từ develop, PR và Mentor review trước khi merge.

## Slide 13 Đầu ra cần hoàn tất tuần này

- Hoanbucon (TV1): phiếu đăng ký, đề cương bài toán, repo và bảng phân công.
- UncleThing (TV2): bảng nguồn dữ liệu, 20–30 trang mẫu, báo cáo truy cập và giấy phép.
- MinhMuc (TV3): bảng survey, 30 câu hỏi mẫu, thiết kế baseline và metric.
- QuyVuiVe (TV4): wireframe web, luồng /ask, tổng hợp slide và kịch bản demo.

**Gợi ý lời nói:** Tuần 1 không cần tuyên bố hệ thống đã chạy. Đến ngày 25/10, mỗi đầu ra phải có link hoặc file minh chứng. Các số lượng 20–30 trang và 30 câu là mục tiêu tuần 1. Cả nhóm review chéo cuối tuần để chốt phạm vi, dữ liệu, câu hỏi nghiên cứu và kế hoạch. Họp giữa tuần ngắn để gỡ vướng.

## Slide 14 Rủi ro và tiêu chí hoàn thành

- Nguồn khó truy cập: dùng corpus mẫu đã được phép và lưu bản thô có nguồn.
- Retrieval yếu: kiểm tra dữ liệu, chunk và lỗi truy vấn trước khi tăng độ phức tạp.
- Model chậm hoặc tốn phí: giảm ngữ cảnh, đo token và chọn cấu hình phù hợp.
- Hoàn thành: demo hai kênh, có nguồn kiểm chứng và báo cáo so sánh tái lập được.

**Gợi ý lời nói:** Các ngưỡng chất lượng trong tài liệu cũ là mục tiêu, không phải kết quả đã đạt. Nhóm sẽ hiệu chỉnh sau baseline và công khai cấu hình, phiên bản dữ liệu, giới hạn và các nhóm câu còn sai. Kết bài: nhóm xin đăng ký đề tài và xin góp ý về phạm vi cùng thiết kế đánh giá. Không cần hứa khả năng tải lớn trước khi có số đo.

## Slide 15 Phụ lục khảo sát và nguồn đọc

- Lewis et al. (2020): RAG và đối chứng với mô hình chỉ dùng tham số.
- Multilingual E5: embedding đa ngôn ngữ, cách chuẩn bị query và passage.
- Qdrant Query API: hybrid, fusion và cách đánh chỉ mục.
- Mẫu survey: nguồn, bài toán, phương pháp, dữ liệu, metric, hạn chế, cách áp dụng.

**Gợi ý lời nói:** Nguồn đọc chi tiết bên dưới. Survey tuần 1 cần bảng so sánh có dẫn nguồn, không chỉ danh sách tên thư viện. Bổ sung tài liệu chính thức về BM25, cross-encoder và hệ thống RAG có đánh giá. Lưu ngày đọc và phân biệt nhận xét của nhóm với kết quả tác giả công bố.

Nguồn: https://arxiv.org/abs/2005.11401, https://huggingface.co/intfloat/multilingual-e5-small, https://qdrant.tech/documentation/search/hybrid-queries/, https://github.com/ggml-org/llama.cpp/tree/master/tools/server

## Slide 16 Phụ lục hỏi đáp với giảng viên

- “Điểm NLP nằm ở đâu?” Ở retrieval đa ngôn ngữ, chunking và thí nghiệm đối chứng.
- “Sao không chỉ dùng LLM?” Nhóm đo thêm khả năng bám nguồn và kiểm chứng câu trả lời.
- “Dữ liệu đã có chưa?” Đang khảo sát, tuần 1 bàn giao mẫu cùng thông tin nguồn.
- “Có kịp 9 tuần?” Baseline tuần 3, MVP tuần 6, dành 3 tuần cho đánh giá và hoàn thiện.

**Gợi ý lời nói:** Trả lời đúng trạng thái thực tế của nhóm. Không trình bày số mục tiêu như kết quả đã đạt. Nếu trường có mẫu đăng ký, lấy tên đề tài, mục tiêu, phương pháp, đầu ra và phân công từ bộ tài liệu này để điền. Nhóm cần bổ sung họ tên, MSSV, lớp và tên giảng viên trước khi nộp.

