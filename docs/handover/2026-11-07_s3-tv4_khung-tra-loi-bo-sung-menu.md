# TV4 · Khung trả lời bổ sung theo thông báo Elden Ring

Ngày: 07/11/2026 (Asia/Saigon). Nhánh: `feature/s3-tv4-hoan-thien-web-bot`. Chưa commit/push.

## Yêu cầu và phạm vi

Người dùng muốn ô chat phụ “Trả lời bổ sung” giống bảng thông báo nhận vật phẩm trong ảnh mẫu; lấy ảnh từ `../item/hi_01_common-tpf-dcx_split/` sang `web/item_`, bỏ ô phím E, giữ chữ OK và dùng Enter để gửi.

Chỉ chỉnh giao diện frontend được yêu cầu và tài liệu bàn giao. Không sửa backend, bot, agent/pipeline, hợp đồng clarification hoặc logic xác định thông tin còn thiếu của TV3. Giữ các thay đổi `.env.example` và tài liệu Tavily đã có từ lượt trước, không gộp hoặc hoàn tác chúng.

## Tài nguyên và file thay đổi

- Chép nguyên bản `MENU_FL_Itemlog_1.png`, `MENU_FL_Itemlog_2.png`, `MENU_FL_Itemlog_3.png` từ hi_01 sang `web/item_`. Đối chiếu SHA-256 nguồn/đích của cả ba file giống nhau; không sửa bitmap hoặc chép toàn bộ bộ ảnh.
- `web/src/components/chat/ClarificationForm.tsx`: bỏ dùng class composer chung, bố trí nhãn/ô nhập trong bảng riêng và nút OK ở giữa thanh dưới. Giữ text tự do, ID yêu cầu, Enter gửi/Shift+Enter xuống dòng, bảo vệ composition/không gửi lặp, hủy và hết hạn. Ô nhập tự tăng chiều cao tối đa 224 px; không đặt nút vào cột hẹp cạnh textarea. Trạng thái xử lý/hết hạn có dòng aria-live riêng, không thay chữ OK bằng thông báo dài.
- `web/src/styles/clarification.css`: CSS chỉ scope clarification; nền xanh đen dùng Itemlog_2, thanh xác nhận dùng Itemlog_1, hover/focus OK dùng Itemlog_3. Tận dụng RuneLine đã có cho đường phân cách. Giữ font và màu theme sẵn có; trạng thái focus bàn phím rõ; bố cục từ 360 px không tràn ngang.
- `web/tests/clarification.test.ts`: cập nhật kỳ vọng OK, không có E badge/composer cũ; giữ kiểm tra request/retry/expiration và source/feedback đã gỡ ở lượt trước.
- Không thay sidebar, background, favicon, ô chat chính hoặc nút gửi của ô chính. Không thêm ảnh vật phẩm/ngôi sao minh họa sai ngữ cảnh chỉ để trang trí ô phụ.

Ảnh từ bộ tài nguyên người dùng cung cấp, không tự xác nhận quyền phát hành hoặc thay thông tin giấy phép của dự án.

## Kiểm tra thực tế

- `npm.cmd test`: **41/41 đạt**. Có cảnh báo tranh cổng HMR 24678 trong các SSR server của suite, nhưng không có test lỗi; không sửa các test/component khác ngoài phạm vi để che cảnh báo.
- `npm.cmd run build`: TypeScript và Vite production đạt; ba ảnh mới và RuneLine được đóng gói đúng.
- `npm.cmd run format:check`: đạt.
- Trình duyệt Chrome/CDP với fixture local tách riêng: màn trống disable OK, nhập tự do, Enter gửi đúng text/ID, Shift+Enter thêm dòng không gửi, Enter trên nút OK, xử lý khóa điều khiển, lỗi giữ draft, thành công xóa draft, hủy đúng nội dung cũ, hết hạn khóa input/OK đều đạt.
- Đã chụp và xem desktop/mobile; thử 1440/768/360 px không tràn ngang, OK nằm dưới textarea, văn bản dài tự giãn đến ngưỡng và cuộn trong ô. Browser không có lỗi JavaScript và không phát sinh request `/api`.
- Những lần đầu script CDP gửi Enter thiếu ký tự CR nên kiểm tra xuống dòng/kích hoạt nút chưa đúng; đã sửa thao tác script và chạy lại đạt, không đổi logic ứng dụng để né kiểm tra. Server Vite fixture gặp `ECONNRESET` khi đóng trình duyệt; phiên fixture đã dừng, không phải kết quả kiểm thử backend hoặc lỗi console của form.
- Dữ liệu minh họa, script QA và screenshot ở `web/.taste-skill/clarification-*` được Git bỏ qua. Chỉ dùng để kiểm tra, không thêm route thử vào ứng dụng production.
- Kiểm tra hash asset, UTF-8, liên kết handover và `git diff --check` đạt. Không gọi LLM/Tavily/API thật, không cài dependency hoặc nạp/index dữ liệu.

## Cách xem

Chạy web như thường lệ và tải lại trang. Khi backend đặt câu hỏi bổ sung, khung mới xuất hiện dưới câu trả lời. Người dùng nhập nội dung rồi nhấn Enter hoặc bấm OK; Shift+Enter xuống dòng. Không cần đăng ký lại bot hoặc tạo lại index. Chưa kiểm thử tích hợp agent trả lời thật trong lượt chỉnh UI này.

## Cập nhật kích thước theo yêu cầu tiếp theo

Người dùng yêu cầu khung nhập phụ bằng kích thước khung chat chính phía dưới. Đã đo composer thật bằng fixture chứa cả `MessageInput` và `ClarificationForm`, rồi sửa riêng form/CSS của ô phụ:

- Chiều rộng dùng cùng `--ui-chat-width` (tối đa 760 px), không còn giới hạn 680 px.
- Nhãn và đường phân cách chuyển ra phía trên vùng nhập; giữ thanh OK bên dưới. Chỉ vùng khung nhập có kích thước bằng composer; nhãn, thanh OK và ghi chú vẫn là các phần bên ngoài.
- Chiều cao vùng nhập ban đầu đồng bộ composer theo breakpoint hiện tại; textarea một dòng thay vì ba dòng ban đầu. Đọc min/max-height từ CSS, xử lý làm tròn `scrollHeight`, và đo lại khi thay đổi chiều rộng bằng ResizeObserver. Nội dung dài vẫn tự giãn đến giới hạn cũ, không khóa chiều cao cố định.
- Chrome/CDP xác nhận cả chiều rộng, chiều cao và mép trái hai khung trùng nhau: viewport 1440 → 760 × 114,296875 px; viewport 768 → 704 × 114,296875 px; viewport 360 → 328 × 107,5 px. Không tràn ngang, nhập dài vẫn giãn, OK giữ nguyên; đã xem ảnh desktop/mobile.
- Chạy lại 41/41 test, TypeScript/Vite build và format đều đạt; suite vẫn có cảnh báo HMR 24678 đã ghi ở trên. Fixture server chạy cổng tạm, đã đóng sau QA; không gọi API thật/LLM, không sửa ô chat chính hoặc code thành viên khác.
- Ảnh so sánh/script QA nằm trong `.taste-skill/clarification-matched-*` và `compare-clarification-size.mjs`, được Git bỏ qua. Không thêm route hoặc dependency vào ứng dụng.

## Cập nhật thanh Hủy yêu cầu

Theo yêu cầu tiếp theo, chuyển Hủy yêu cầu từ liên kết nhỏ cạnh hướng dẫn thành thanh riêng ngay dưới OK. Hai thanh dùng cùng texture Itemlog_1 và cùng class nút, font, kích thước, hover/focus Itemlog_3; bỏ CSS riêng từng làm nút Hủy nhỏ và khác hiệu ứng. Hai nút cùng rộng tối đa 240 px bên trong thanh; thanh vẫn theo chiều rộng khung nhập.

Giữ `type="button"` và nội dung hủy gửi tới callback như cũ; không biến nút hủy thành submit câu trả lời. Đang xử lý/hết hạn vẫn khóa cả hai nút; Enter trong textarea vẫn xác nhận OK, Enter khi focus nút Hủy vẫn kích hoạt hủy.

Đã chạy lại 41/41 test, build và format đạt. Chrome/CDP trên 1440/768/360 px xác nhận hai nút cùng kích thước, thẳng mép, xếp thành hai thanh; gửi hủy bằng bàn phím đúng payload cũ và khóa điều khiển khi đang xử lý. Kích thước khung phụ/chính vẫn khớp, không tràn ngang; đã xem ảnh desktop. Không gọi API/LLM, không thay đổi phần của thành viên khác hoặc commit/push.

## Cập nhật khung bao toàn bộ cụm

Người dùng làm rõ muốn một khung ngoài bao toàn bộ phần trả lời bổ sung và chỉ yêu cầu chiều ngang bằng khung chat chính. Đã dùng chính phần tử form làm khung ngoài, thêm nền tối, viền vàng trầm 1 px, góc vuông và padding responsive. Khung bao cả tiêu đề, ô nhập, hai thanh OK/Hủy, trạng thái và hướng dẫn. Đây là yêu cầu hiện hành thay cho việc so chiều cao toàn bộ cụm với composer: chiều cao khung ngoài tăng tự nhiên theo nội dung, chiều ngang/mép trái vẫn trùng composer; vùng nhập bên trong thu hẹp theo padding khung ngoài.

Chỉ cập nhật `web/src/styles/clarification.css`, không đổi logic hoặc contract. Chrome/CDP kiểm tra mọi phần tử con nằm trong khung, hai nút vẫn bằng nhau, bàn phím hủy hoạt động và nội dung dài tự giãn. Kích thước đo khung ngoài/composer: 760/760 px tại viewport 1440, 704/704 px tại 768, 328/328 px tại 360; mép trái tương ứng trùng nhau. Đã xem screenshot desktop và mobile, không tràn ngang, không lỗi console. Test 41/41, build và format đạt; cảnh báo HMR của suite như đã nêu. Không gọi API/LLM hoặc sửa thành viên khác, không commit/push.

## Đưa hướng dẫn phím ra ngoài khung

Theo yêu cầu mới nhất, dòng Enter/Shift+Enter được chuyển ra ngay dưới khung, không còn nằm trong form có viền. Thêm wrapper `clarification-group` để giữ cùng chiều ngang và khoảng cách; khung vẫn bao tiêu đề, ô nhập, OK, Hủy và trạng thái. Chỉ thay JSX/CSS frontend, không đổi hành vi gửi/hủy.

Đã chạy lại 41/41 test, build và format đạt. Chrome/CDP trên 1440/768/360 px xác nhận hướng dẫn không có tổ tiên form, nằm dưới mép khung; khung vẫn trùng chiều ngang/mép trái composer, không tràn ngang, thao tác hủy bằng bàn phím và tự giãn vẫn đạt. Đã xem ảnh desktop; không gọi API/LLM, không commit/push.

## Đổi viền ngoài theo ảnh bảng nhận vật phẩm

Người dùng yêu cầu viền khung ngoài giống ảnh tham chiếu nhận Small Golden Effigy, và chỉ thêm ảnh nếu chưa có trong item_. Đã kiểm tra `MENU_FL_Itemlog_2.png` có sẵn trong `web/item_` và SHA-256 trùng bản hi_01; không chép lại hoặc tạo bản sao mới.

Trong `clarification.css`, bỏ viền vàng 1 px/nền CSS của form, chuyển texture Itemlog_2 từ vùng nhập nhỏ sang pseudo-element phủ toàn bộ form, tạo mép loang tối/xanh đen theo ảnh gốc. Bỏ pseudo-element nền ở panel bên trong để tránh lồng hai khung; giữ nền hai thanh OK/Hủy. Lớp ảnh nằm sau nội dung, pointer-events none, không chặn nhập hoặc bấm nút. Hướng dẫn Enter vẫn ngoài khung, chiều ngang/mép trái của khung vẫn bằng composer chính.

Test 41/41, build và format đạt. Chrome/CDP kiểm tra không còn viền cứng, lớp trang trí dùng đúng ảnh đã có, mọi control bên trong form, hướng dẫn ngoài form; các chiều ngang vẫn 760/704/328 px tương ứng desktop/tablet/mobile. Đã xem screenshot desktop/mobile; không tràn ngang hoặc lỗi console; hủy bằng bàn phím, khóa khi đang xử lý và nhập dài vẫn đạt. Không đổi contract, gọi API/LLM, cài dependency hoặc commit/push.

## Làm rõ hai mép trên/dưới và bỏ ánh tím

Người dùng làm rõ cần giữ viền trên ngay trước tiêu đề và viền dưới sau Hủy, nhìn được nhưng hơi mờ; đồng thời bỏ vùng ánh tím. Đã đổi nền form sang `MENU_FL_Itemlog_1.png` đen trung tính có sẵn trong item_, không còn dùng Itemlog_2 cho khung đang hiển thị. Giữ asset Itemlog_2 nguyên bản, không xóa tài nguyên người dùng.

Thêm lớp trang trí riêng tạo hai nét 1 px màu xám vàng nhạt ở mép trên/dưới, tâm rõ và giảm dần về hai đầu; không có viền hộp vàng quanh bốn cạnh hoặc glow tím. Hai lớp trang trí đều không nhận pointer events. Chiều ngang, dòng hướng dẫn bên ngoài, OK/Hủy và chức năng nhập/gửi giữ nguyên.

Đã chạy 41/41 test và build đạt; sửa định dạng CSS theo Prettier rồi chạy lại format đạt. Chrome/CDP xác nhận nền dùng Itemlog_1, hai nét trên/dưới có đủ hai lớp gradient 1 px, không dùng Itemlog_2; desktop/tablet/mobile giữ chiều ngang bằng composer, không tràn ngang, hủy bằng bàn phím và tự giãn vẫn đạt. Đã xem screenshot desktop/mobile. Lần kiểm tra CDP đầu so sánh background-size theo một lớp thay vì hai nên assertion sai; đã sửa script QA để kiểm cả hai lớp và chạy lại đạt. Không sửa API, gọi LLM/Tavily hoặc commit/push.

## Bỏ đường gạch dưới khi nhập

Theo ảnh và yêu cầu mới, bỏ `box-shadow: inset ...` ở trạng thái focus-visible của textarea phụ. Đây là đường gạch xuất hiện trong vùng nhập khi chọn/gõ; giữ nguyên lớp viền trên/dưới bao cả form.

Chỉ sửa CSS clarification. Đã chạy 4/4 test clarification, build TypeScript/Vite và format đạt. Chrome/CDP xác nhận textarea đang focus có box-shadow none và border-bottom 0 px, hai mép khung ngoài vẫn tồn tại, chiều ngang desktop/tablet/mobile không đổi và thao tác hủy vẫn hoạt động. Không gọi API/LLM, không sửa các phần khác hoặc commit/push.

## Bỏ hiệu ứng OK và Hủy

Theo phản hồi về mảng sáng vàng khi rê chuột, bỏ texture Itemlog_3 ở hover/focus của cả hai nút, giữ màu chữ/nền giống trạng thái bình thường; tắt transition và text-shadow. Vẫn giữ outline tĩnh cho focus bàn phím, trạng thái disabled và chức năng gửi/hủy. Không xóa ảnh gốc trong item_.

Đã chạy 4/4 test clarification, build và format đạt. Kiểm tra Chrome/CDP rê chuột trên từng nút đang bật: background-image none, nền transparent, text-shadow none và transition 0s; chiều ngang khung, tự giãn và hủy bằng bàn phím vẫn đạt. Không gọi API/LLM, không đổi logic hoặc commit/push.

## Phủ nền tối cả vùng nhập bên trái

Người dùng nhận thấy nền tối của texture chưa bao đến chữ placeholder ở bên trái. Do vùng alpha lớn của ảnh Itemlog_1, đã bổ sung màu nền đen trung tính ngay trong cùng lớp trang trí của form; mask chỉ làm mờ 3% ở mỗi mép thay vì để vùng đầu ô nhập trong suốt. Nền phủ cả tiêu đề, textarea/placeholder và OK/Hủy; viền trên/dưới, chiều ngang và hướng dẫn bên ngoài giữ nguyên. Không đổi hoặc sửa ảnh bitmap.

Chỉ sửa CSS; 4/4 test clarification, build và format đạt. Chrome/CDP xác nhận lớp nền có màu đen và mask mép hẹp, khung vẫn cùng chiều ngang composer tại 1440/768/360, không tràn ngang; nhập dài, focus không gạch dưới, hai nút không sáng vàng và thao tác hủy vẫn đạt. Đã xem screenshot desktop. Không gọi API/LLM, sửa code thành viên khác hoặc commit/push.

## Cân khoảng cách chữ với hai viền

Theo yêu cầu mới, kéo viền dưới lên gần Hủy để cân với khoảng cách từ tiêu đề đến viền trên. Đã ẩn dòng trạng thái khi rỗng bằng `:empty` và giảm padding dưới của form; trạng thái xử lý/hết hạn có nội dung vẫn hiện như cũ.

Chrome/CDP đo bằng Range của chữ: tại viewport 1440/768, khoảng cách viền trên → chữ tiêu đề và chữ Hủy → viền dưới đều 23 px; tại 360 đều 19 px. Chiều ngang vẫn bằng composer, không tràn ngang, nền tối và hướng dẫn bên ngoài giữ nguyên. Đã xem screenshot desktop. 4/4 test clarification, build và format đạt. Script QA được cập nhật để bỏ qua phần tử trạng thái đang display:none khi kiểm tra bounding box; không sửa ứng dụng để né assertion. Không đổi logic, gọi API/LLM hoặc commit/push.
