# Đánh giá IndexBeast trên 25 câu golden set theo độ khó

Ngày 09/11/2026 · 4 Hollows · TV3 MinhMuc · Bản được chạy `develop` tại `6dfb6bf`.

**24/25 lượt đạt yêu cầu nội dung hoặc hành vi trong lượt chấm này.** Lượt còn lại trả HTTP 502 trước khi tìm kiếm. Tập thử gồm 8 câu dễ, 9 câu trung bình, 8 câu khó, với 16 câu tiếng Việt và 9 câu tiếng Anh. Đọc câu hỏi nguyên văn, đáp án kỳ vọng, câu trả lời, trích đoạn và trace trong [kết quả gốc](report.json).

## Cách chấm

Đọc từng câu trả lời cùng `expected_answer` và nội dung trích đoạn trong `response.sources`. Chấm theo ý nghĩa, chấp nhận cách diễn đạt tương đương và ghi riêng các chi tiết thừa hoặc câu văn khó hiểu. Đây là đánh giá sơ bộ của Codex trên kết quả đã lưu, còn chờ review chéo của nhóm. [Rubric của dự án](../../evaluation/golden-diagnostic-guide.md#đọc-kết-quả).

| Tiêu chí | 0 | 1 | 2 |
| --- | --- | --- | --- |
| C — Đúng và đủ ý | Sai ý chính hoặc lạc đề | Có ý đúng nhưng thiếu điều kiện hoặc ý bắt buộc | Đúng các ý và điều kiện bắt buộc |
| F — Có căn cứ | Khẳng định chính thiếu hỗ trợ | Ý chính có căn cứ nhưng có khẳng định thêm chưa được đoạn trích hỗ trợ | Các khẳng định thực tế được đoạn trích hỗ trợ |

- Câu ngoài phạm vi, cần hỏi lại hoặc thiếu đầu vào được chấm C theo hành vi kỳ vọng. Cột H ghi kết quả hành vi, F là `—` khi câu trả lời chỉ xử lý hành vi và không khẳng định dữ kiện game.
- Câu 502 không có đáp án để chấm C/F. Câu này vẫn nằm trong mẫu số 25 khi tính tỷ lệ đạt theo lượt. Một câu đạt nếu HTTP thành công, C = 2, F = 2 nếu áp dụng và H đạt nếu áp dụng.
- Điểm F đối chiếu với đúng các đoạn trích trả về trong lượt chạy. Nó đánh giá sự phù hợp với bằng chứng đó. Tính chính xác của wiki hoặc tình trạng patch mới nhất nằm ngoài phạm vi lượt chấm.

## Kết quả theo nhóm

| Độ khó | Số câu | HTTP 200 | C | F | Số lượt đạt | Trung vị |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dễ | 8 | 8/8 | 16/16 | 14/14 | 8/8 | 6,52 giây |
| Trung bình | 9 | 8/9 | 16/16 | 14/14 | 8/9 | 7,35 giây |
| Khó | 8 | 8/8 | 16/16 | 14/14 | 8/8 | 7,89 giây |
| **Tổng** | **25** | **24/25** | **48/48** | **42/42** | **24/25** | **7,24 giây** |

Điểm C tính trên 24 câu có đáp án. Điểm F tính trên 21 câu có khẳng định thực tế cần đối chiếu. Ba ca hành vi đều đạt. Độ trễ lấy từ API trong tiến trình thử nghiệm, gồm cả lượt lỗi. P95 theo nearest rank là 10,31 giây, tổng thời gian của các lượt là 174,85 giây.

## Chấm từng câu

Các số `[n]` trong nhận xét trỏ tới `response.sources[].index` của chính câu đó trong report. Có thể tra theo mã `IB-GS-xxx`.

| ID | Độ khó | HTTP | C | F | H | Đối chiếu |
| --- | --- | ---: | ---: | ---: | --- | --- |
| IB-GS-001 | Dễ | 200 | 2 | 2 | — | Nêu đúng Blaidd là chiến binh nửa sói và shadow của Ranni [1]. Phần bổ sung về Two Fingers, quan hệ với Ranni và lời thề có [2–5]. Có thể rút gọn. |
| IB-GS-025 | Dễ | 200 | 2 | — | Đạt | Từ chối viết Fibonacci ngoài phạm vi và mời hỏi về Elden Ring. |
| IB-GS-031 | Dễ | 200 | 2 | 2 | — | Xác định Shadow Keep và tính bắt buộc của Messmer trong SotE. [1] ghi cả hai, [2] liệt kê boss bắt buộc. |
| IB-GS-041 | Dễ | 200 | 2 | 2 | — | Đủ ý giảm tích tụ, chữa poison và scarlet rot, và bỏng nhẹ [1]. Nhận xét về Lake of Rot có [3]. |
| IB-GS-065 | Dễ | 200 | 2 | 2 | — | Đủ khiên, cung và hai loại tên đúng số lượng. [1] tách armaments khỏi giáp, [2] hỗ trợ nhận xét katana và longbow. Nên dùng từ “trang bị chiến đấu” thay cho “vũ khí” khi gộp cả khiên và đạn. |
| IB-GS-005 | Dễ | 200 | 2 | 2 | — | Tên Hoarah Loux đúng với [1–3]. Mốc Long March và việc rời vương vị có [1][4]. |
| IB-GS-054 | Dễ | 200 | 2 | 2 | — | Nêu đúng bốn chỉ số và bất lợi nhận sát thương [1]. Hai con số bổ sung có trong ghi chú riêng [2]. |
| IB-GS-083 | Dễ | 200 | 2 | 2 | — | Longbow, 20 Arrow, 10 Fire Arrow đúng bảng Armaments [1]. [2] hỗ trợ nhận xét về longbow. |
| IB-GS-007 | Trung bình | 200 | 2 | 2 | — | Đúng Marika đập vỡ và Radagon sửa bất thành. [1–3] hỗ trợ diễn biến và chiếc búa, [2] hỗ trợ phần chung hình phạt. |
| IB-GS-035 | Trung bình | 200 | 2 | 2 | — | Đủ cách dùng tại Sites of Grace, hiệu ứng và giới hạn Realm of Shadow [1–3]. |
| IB-GS-042 | Trung bình | 200 | 2 | 2 | — | Đúng tăng tải trang bị và không cộng dồn với hai biến thể [2–5]. Số bổ sung có [4][5]. Câu cuối về phần trăm bản gốc là chi tiết ngoài yêu cầu. |
| IB-GS-061 | Trung bình | 200 | 2 | 2 | — | Đủ hướng và tầm của hai đòn. [1] cũng có ghi chú về tốc độ, độ rộng và cự ly cận chiến. Câu trả lời dài hơn mức câu hỏi cần. |
| IB-GS-091 | Trung bình | 200 | 2 | 2 | — | Tính đúng tổng 179 và phân biệt được tổng chỉ số với điểm tăng thêm. Quy tắc level + 79 có [1]. |
| IB-GS-093 | Trung bình | 200 | 2 | — | Đạt | Hỏi vị trí hoặc boss vừa hạ và mục tiêu, giữ việc định tuyến đến sau khi có thông tin. Payload có `clarification` để web mở khung phụ. |
| IB-GS-011 | Trung bình | 200 | 2 | 2 | — | Ranni chết thể xác, Godwyn chết linh hồn. Cursemark và búp bê được đối chiếu với [1][3][4][5]. |
| IB-GS-046 | Trung bình | 200 | 2 | 2 | — | Đúng Sacred affinity, tăng attack power và defense cho bản thân và đồng minh gần đó [1][2]. |
| IB-GS-086 | Trung bình | 502 | — | — | — | Bước kiểm quyết định chặn truy vấn vì mất dấu phẩy trong `Leyndell, Ashen Capital`. Không có câu trả lời để chấm. |
| IB-GS-019 | Khó | 200 | 2 | 2 | — | Đúng anh em cùng cha Radagon và mẹ Rennala [1][2]. [4] ghi Radahn là anh, [3–5] hỗ trợ các ý về gia đình và bối cảnh. |
| IB-GS-021 | Khó | 200 | 2 | 2 | — | Nối đúng cái chết linh hồn của Godwyn với nỗ lực thất bại của Fortissax và sự tha hóa [1–4]. |
| IB-GS-036 | Khó | 200 | 2 | 2 | — | Tách đúng người mang, summoned spirits và spectral steed, cùng giới hạn vùng hiệu lực [1–5]. Cách nói “gây và giảm sát thương” có thể viết rõ hơn thành “gây sát thương nhiều hơn, nhận sát thương ít hơn”. |
| IB-GS-075 | Khó | 200 | 2 | 2 | — | Hạ Radahn để vào Nokron và rương ở phía đông bắc Grace khớp [1–3]. Điều kiện phục vụ Ranni có [1]. Cụm “hầm ghế đỡ lấy xác” dịch sát từ [4] nhưng khó hình dung. |
| IB-GS-096 | Khó | 200 | 2 | — | Đạt | Nêu rõ thiếu vũ khí, chỉ số, nâng cấp, affinity và dữ liệu patch. Giữ AR/DPS chưa xác định đúng kỳ vọng. |
| IB-GS-052 | Khó | 200 | 2 | 2 | — | Đủ tên chìa khóa, vị trí rương và điều kiện đánh bại Baleful Shadow [1–3]. Chi tiết về Dark Moon Ring và lift có [1][4]. |
| IB-GS-090 | Khó | 200 | 2 | 2 | — | Giải thích Samurai tối ưu trong điều kiện cụ thể. Ví dụ về pure Dexterity và ngưỡng Strength bám đúng note [1][2]. |
| IB-GS-092 | Khó | 200 | 2 | 2 | — | Tính đúng `40+20+20+12+18+53+8+8 = 179`, rồi `179−79 = 100` theo [1]. Kết luận giới hạn ở phép tính. |

## Lỗi và phạm vi sử dụng số liệu

- **IB-GS-086:** hai lần gọi quyết định đều trả tên thực thể `Leyndell, Ashen Capital` nhưng `search_query` là `Leyndell Ashen Capital` không dấu phẩy. Tái hiện offline bằng `check_decision` cho lỗi provenance ở cả hai bản. Thêm lại dấu phẩy trong bản replay thì qua validator. Lỗi diễn ra trước retrieval và generation.
- **Tìm web:** Tavily Auto ở cả 25 lượt. Chỉ `IB-GS-096` có lượt tìm web thành công, với tổng cộng 2 request Tavily. Có 112 lượt gọi mô hình logic, 576.906 input token và 14.948 output token ghi nhận. Kết quả thuộc một lần chạy Auto nên chưa đo mức cải thiện do web search.
- **Môi trường:** gọi API JSON của backend local bằng runner `scripts.benchmark_agent`. Dùng collection đang cấu hình với 18.383 point và tài nguyên hội thoại thử riêng. Tập chọn thuộc golden set đang dùng để phát triển. Tỷ lệ 24/25 chỉ áp dụng cho mẫu này và cách chấm nêu trên. Chưa có nhãn đoạn liên quan để tính Recall/MRR.
