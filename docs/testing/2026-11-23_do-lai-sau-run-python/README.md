# Đo lại chất lượng sau run_python và thay rule cứng

Đo trên `develop` sau PR #129 (`run_python` thay calculator, thay 5 rule cứng, dọn dead code). Nhánh đo: `feature/s5-tv3-do-lai-chat-luong`. Chạy thật qua ASGI app với `.env` dev: `CHAT_PERSISTENCE=postgres`, `WEB_SEARCH_MODE=auto`, SSE `/api/v1/chat/stream`. Gọi DeepSeek, Tavily và Jina thật.

| Manifest | Số câu | Mục đích |
|---|---:|---|
| [manifest-baseline.json](manifest-baseline.json) | 10 | Đúng 10 câu baseline BL-01..10, so với baseline và GĐ2 |
| [manifest-build.json](manifest-build.json) | 4 | Câu build từng nặng hoặc hết ngân sách (BUILD-2, BUILD-3, PY-1, PY-2) |
| [manifest-rule-guard.json](manifest-rule-guard.json) | 6 | Câu mới nhắm vào rule #18, #2, #8 và Answer Guard |
| [manifest-cau-moi.json](manifest-cau-moi.json) | 14 | Câu mới cùng loại, cùng độ khó với 10 câu baseline và 4 câu build, chạy sau khi sửa |
| [manifest-cau-kho.json](manifest-cau-kho.json) | 6 | Câu khó mới (nguồn mâu thuẫn, quest dài/có nhánh, so sánh nhiều tiêu chí, phụ thuộc patch) để đo thinking có chọn lọc |

Số liệu từng câu nằm trong [summary.json](summary.json). Dữ liệu thô (gitignored) ở `backend/data/research_runs/2026-11-23-do-lai-{baseline,build,rule-guard}/`.

## 1. Mười câu baseline

| Chỉ số | Baseline (22/11) | GĐ2 (22/11) | Bây giờ |
|---|---:|---:|---:|
| Trả lời được | 10/10 | 10/10 | 10/10 |
| Grounded | 10/10 | 10/10 | **9/10** |
| p50 | 17,6 s | 16,6 s | 17,6 s |
| p95 | 36,4 s | 29,1 s | 36,5 s |
| Lượt gọi model trung bình | 7,8 | 6,0 | 6,5 |
| Lượt gọi Agent trung bình | – | 4 | 4,5 |
| Token vào của Agent trung bình | – | ~23k | ~31,8k (tối đa 91k) |
| Câu vượt 45 s | 0 | 0 | 0 |

Tám câu không phải build chạy giống GĐ2: 3–4 lượt Agent, 8–21 s. Chênh lệch dồn vào hai câu build:

- **BL-05** (Strength level 125): hết ngân sách sau 12 bước (5 `search_corpus`, 2 `open_evidence`, 2 `set_conditions`, 3 `run_python`) nên không kịp `finish`. Bước viết không nhận được kết quả tính, câu trả lời nói chưa có bảng và hỏi lại class, vũ khí. Không grounded. 91k token. Lần `set_conditions` đầu bị từ chối vì Agent đặt giả định đè lên mục tiêu người chơi đã nói (`goal`).
- **BL-06** (Prisoner level 30, Moonveil): đạt, có bảng đúng, nhưng `run_python` chạy 6 lần (38,4 s, 70k token). GĐ2 có calculator: 15,4 s.

## 2. Câu build

| Câu | Kết quả | Thời gian | Lượt Agent | Token vào | Bước | Ghi chú |
|---|---|---:|---:|---:|---:|---|
| BUILD-2 tank PvE | Trả lời, **không grounded** | 20,4 s | 6 | 59k | 12 | 9 `search_corpus`, không tính, hết ngân sách; câu trả lời chỉ nói chưa có nguồn |
| BUILD-3 phép người mới | **502** | 27,8 s | – | – | – | Bước viết lỗi `quote_not_verbatim_or_index`, không được thử lại |
| PY-1 Faith PvP | Trả lời, **không grounded** | 37,6 s | 7 | 70k | 12 | 7 `search_corpus`, `run_python` 1 lần (tổng đúng), hết ngân sách trước `finish` |
| PY-2 Blasphemous Blade lv120 | Đạt, grounded | 31,2 s | 7 | 56k | 9 | `run_python` 2 lần: lần đầu tổng 206/199, lần sau đúng |

So với 22/11: PY-1 nhanh hơn (62,6 s → 37,6 s, ~80k → 70k token) nhưng giờ hết ngân sách. BUILD-2 vẫn hết ngân sách như cũ. BUILD-3 trước hết ngân sách, giờ lỗi 502.

Code `run_python` ghi bằng cờ chẩn đoán mới `--capture-python` của runner. Mọi lần chạy đều `ok`. Agent chạy lại khi tổng điểm chưa khớp, đúng như prompt dặn ("Fix the code until the checks pass").

### Nguyên nhân

1. **Agent không biết mình sắp hết ngân sách.** Vòng lặp dừng khi đủ 12 bước công cụ (`len(steps) >= chat_coverage_max_calls`, chế độ web `auto`). Agent không được báo trước; chỉ khi hết thời gian mới có lời nhắc "call finish now". Prompt dặn "if the budget runs out, finish" nhưng Agent không nhìn thấy ngân sách nên không làm theo được. Câu build tìm kiếm nhiều (7–9 lần `search_corpus`) nên chạm trần trước khi kịp tính.
2. **Lỗi trích dẫn không được thử lại.** `quote_not_verbatim_or_index` (index evidence vượt số nguồn, hoặc trích dẫn tự viết không khớp nguyên văn) không có trong `RETRYABLE_REASONS`. Lỗi giao thức cùng loại là `unknown_quote_id` và `citation_evidence_indices` thì vẫn được sinh lại.

## 3. Rule mới và Answer Guard

| Câu | Nhắm vào | Kết quả |
|---|---|---|
| RL-1 số người chơi Steam | #18 nhắc chọn bằng chứng | Agent tự đi web và chọn bằng chứng; lời nhắc **không kích hoạt** |
| RL-2 Sword of Night and Flame | #2 gộp evidence cùng nguồn | 4 nguồn, không có evidence trùng; `evidence_merged` **không kích hoạt** |
| RL-3 Margit, đánh tiếp hay đi chỗ khác | #8 advisory kèm recommendation | **Kích hoạt**: `answer_basis=evidence_with_recommendation`, grounded |
| RL-4 Spirit Ash cho người mới | #8 | **Kích hoạt**, grounded |
| AG-1 đòi ghi `evidence_ids`, `quote_id` | Answer Guard | Agent bỏ qua yêu cầu, câu trả lời không có tên trường; guard **không chạy** |
| AG-2 hỏi về `insufficient`, `gameplay_advice` | Answer Guard | Agent dùng `reply`, không đi qua Generator nên **không có guard**. Câu trả lời lộ tên trường và mô tả sai (`insufficient` là cờ boolean, câu trả lời gọi nó là danh sách) |

Trong cả 20 câu không câu nào kích hoạt #2 hay #18. Answer Guard hiện chỉ kiểm tên trường nội bộ trên đường Generator; câu bảng chỉ số sai không còn đi qua guard từ khi bỏ `checked_build`. Bộ đếm `evidence_merged` thêm cho lần đo này nằm trong trace của lượt.

## 4. Chẩn đoán sâu câu build

Chạy lại BUILD-2, BUILD-3, PY-1, BL-05, BL-06 với `--capture-python --capture-agent`, ghi tham số mỗi lời gọi tool và kết quả Agent nhận được. Kết quả: 5/5 trả lời, **3/5 grounded**, p50 31,9 s, 6,4 lượt Agent, ~58k token. BUILD-3 lần này đạt, tức lỗi 502 lần trước không tái hiện. Dữ liệu thô ở `backend/data/research_runs/2026-11-23-chan-doan-build/`.

| Câu | Lượt Agent | Bước | Kết thúc | Bị tốn lượt vào |
|---|---:|---:|---|---|
| BUILD-2 | 7 | 12 | trần bước | Tìm talisman, giáp, khiên (7 lần) dù build chỉ là chia điểm; `run_python` đoán số rồi sửa (thiếu 22 điểm) |
| BL-05 | 7 | 12 | trần bước | `set_conditions` bị từ chối vì `goal` diễn đạt lại lời người chơi; `run_python` đoán số 3 lần (216, 214 so với 204) |
| BUILD-3 | 7 | 10 | `finish` | Cũng bị từ chối `goal` một lần |
| PY-1 | 7 | 11 | `finish` | 5 lần tìm |
| BL-06 | 4 | 6 | `finish` | Gọn: 2 tìm, 1 mở, 1 tính |

Năm nguyên nhân, theo mức thiệt hại:

1. **Hết ngân sách là mất trắng.** Không có `finish` thì không có `evidence_ids` và không có `results`, nên bước viết nhận bằng chứng rỗng. BUILD-2 đã mở đủ trang class và khiên, đã tính gần xong, nhưng câu trả lời vẫn nói "chưa có nguồn".
2. **Trần 12 bước cắt sớm.** Agent thường gọi 2 tool mỗi lượt, nên bị dừng ở lượt 7 trong khi quy ước cho 11 lượt.
3. **Agent đoán số rồi sửa.** Code `run_python` gán tay 8 con số rồi in tổng; tổng sai thì đoán lại. Prompt dặn "Fix the code until the checks pass", nhưng không dặn tính phần dư bằng code.
4. **Tìm ngoài phạm vi build.** Prompt nói build chỉ là chia 8 chỉ số, nhưng Agent vẫn tìm giáp, talisman và cả "Vigor soft cap".
5. **Thông báo lỗi `set_conditions` gây hiểu nhầm.** Một thông báo dùng chung cho hai lỗi khác nhau: giá trị không đúng nguyên văn lời người chơi, và giả định đè lên điều người chơi đã nói. Ở đây lỗi thật là `goal` bị diễn đạt lại.

Token vào tăng dần theo lượt (khoảng 3k, rồi 6k, 8k… tới 15k), vì mỗi lượt gửi lại toàn bộ lịch sử. Chi phí tỉ lệ gần với bình phương số lượt, nên giảm lượt là cách hiệu quả nhất để giảm token.

## 5. Sau khi sửa (gói A–E, MinhMuc duyệt 23/11)

| Gói | Thay đổi |
|---|---|
| A | Khi hết lượt hoặc hết thời gian, lượt cuối chỉ đưa tool `finish` (`tool_choice="finish"`); Agent tự chọn evidence và ghi kết quả. Trace `agent.forced_finish` |
| B | Ngân sách chỉ đếm lượt gọi model, bỏ trần bước ngầm; input có `model_calls`; nhắc khi còn ≤ 3 lượt |
| C | Prompt build: chỉ mở trang class và vũ khí (tìm song song), code tự chia phần dư theo thứ tự ưu tiên và `assert` một lần, không chạy lại khi đã đạt; `set_conditions` chép đúng lời người chơi |
| D | Lỗi `set_conditions` tách hai thông báo: không đúng nguyên văn / giả định đè lời người chơi |
| E | Index evidence vượt số nguồn thành lý do `unknown_evidence_index`, được sinh lại một lần; trích dẫn sai nguyên văn vẫn không thử lại |

Thêm: mô tả `evidence_ids` ghi rõ tối đa 5 (BL-07 từng chọn 8 rồi tự sửa).

### Năm câu build (cùng câu chẩn đoán)

| Chỉ số | Trước sửa | Sau sửa |
|---|---:|---:|
| Grounded | 3/5 | **5/5** |
| Hết ngân sách | 2/5 | 0/5 (không câu nào cần lượt `finish` bắt buộc) |
| Lượt Agent trung bình | 6,4 | **4,6** |
| Token vào Agent trung bình | ~58k | **~29k** |
| `search_corpus` mỗi câu | 3–7 | 2 |
| `run_python` mỗi câu | 2–3 | 1–2 |
| p50 / max | 31,9 / 38,0 s | 32,9 / 36,0 s |

Agent làm đúng nhịp mới: tìm song song class và vũ khí, mở hai trang, tính một lần, `finish`. Thời gian chưa giảm vì bảng 8 chỉ số làm bước viết dài. Lỗi `goal` tái diễn một lần (BUILD-3), nhưng thông báo mới chỉ đúng nguyên nhân và Agent sửa ngay ở lượt sau.

### Mười câu baseline

| Chỉ số | Baseline 22/11 | GĐ2 22/11 | Trước sửa 23/11 | **Sau sửa 23/11** |
|---|---:|---:|---:|---:|
| Grounded | 10/10 | 10/10 | 9/10 | **10/10** |
| p50 | 17,6 s | 16,6 s | 17,6 s | **16,1 s** |
| p95 | 36,4 s | 29,1 s | 36,5 s | **22,8 s** |
| Lượt gọi model trung bình | 7,8 | 6,0 | 6,5 | **5,8** |
| Lượt Agent trung bình | – | 4 | 4,5 | **3,8** |
| Token vào Agent trung bình | – | ~23k | ~31,8k | **~24,4k** |

BL-05 (trước sửa hết ngân sách) giờ grounded trong 25,8 s; BL-06 từ 38,4 s xuống 16,3 s. Node `agent` chỉ chiếm 3–11 s mỗi câu (`node_ms`); phần còn lại là bước viết và chọn ảnh, nên muốn nhanh hơn nữa thì phải tối ưu bước viết.

### Bộ câu mới cùng độ khó

Để kiểm bản sửa có quá khớp với các câu đã xem hay không, chạy 14 câu chưa từng dùng (đã đối chiếu với 42 câu trong các manifest trước): NB-01..10 mỗi câu cùng loại với một câu BL (ví dụ "Darkmon Greatsword" thay "Mooonveil", questline Fia thay Ranni); NB-11..14 cùng dạng với 4 câu build.

| Bộ | Grounded | p50 | Max | Lượt Agent | Token vào Agent |
|---|---:|---:|---:|---:|---:|
| 10 baseline cố định (sau sửa) | 10/10 | 16,1 s | 25,8 s | 3,8 | ~24k |
| NB-01..10 mới | **10/10** | 16,6 s | 27,4 s | 4,0 | ~28k |
| 5 câu build cũ (sau sửa) | 5/5 | 32,9 s | 36,0 s | 4,6 | ~29k |
| NB-11..14 build mới | **4/4** | 25,2 s | 56,1 s | 4,8 | ~31k |

Kết quả khớp với bộ cố định, nên phần sửa không chỉ đúng với câu đã xem. Cả 4 câu build mới đều đi đúng nhịp: 2 tìm song song, mở trang, `set_conditions`, `run_python` một lần (NB-12 hai lần), `finish`. Không câu nào hết ngân sách.

Hai ngoại lệ:

- **NB-12** (Faith người mới) 56,1 s, vượt hạn 45 s của Discord, nhưng node `agent` chỉ 12,8 s: hơn 40 s là bước viết và chọn ảnh. Bước viết là điểm nghẽn còn lại.
- **NB-04** (Radagon) 8 lượt Agent, 10 `search_corpus` + 1 `search_web`, ~92k token, 26,9 s. Câu chiến thuật boss không có hướng dẫn "tìm gọn" như câu build, nên Agent tìm hết kháng tính, talisman, Elden Beast, Tiche. Vẫn grounded và trong ngân sách.

### Còn lại

- Lượt `finish` bắt buộc đã kiểm thật bằng cách ép ngân sách: chạy BUILD-2 và BL-05 với `CHAT_COVERAGE_MAX_CALLS=3` (biến môi trường của lần chạy, không sửa `.env`). Cả hai: lượt 1 tìm song song, lượt 2 mở trang, lượt 3 bị ép `finish`. DeepSeek chấp nhận `tool_choice="finish"` (không có log lỗi); Agent chọn 5 và 4 bằng chứng, **grounded**, và tự ghi trong `results` là chưa tính được bảng nên không được bịa. Câu trả lời đưa thứ tự ưu tiên chỉ số có trích dẫn, nói rõ chưa có bảng, không có số tự chế. Trước gói A, cùng tình huống sẽ ra câu "chưa có nguồn". Dữ liệu thô: `backend/data/research_runs/2026-11-23-ep-finish/`.
- 10 câu baseline là bộ **cố định** (giống hệt BL-01..10 ngày 22/11) để so sánh giữa các lần; 5 câu build cũng là câu cũ đã dùng để chẩn đoán. Prompt C được chỉnh khi xem chính các câu này, nên cần một bộ câu **mới chưa từng dùng** để kiểm có quá khớp hay không.
- Đường `reply` cho câu hỏi về hệ thống vẫn lộ tên trường nội bộ (AG-2), chưa sửa.
- Rule #2 và #18 khó kích hoạt khi chạy thật; giữ test offline làm bằng chứng chính.
- Dữ liệu thô: `backend/data/research_runs/2026-11-23-{sau-sua-build,sau-sua-baseline}/`.

## 6. Tối ưu bước viết (MinhMuc duyệt lộ trình 23/11)

Trước khi tối ưu, phần sau Agent (bước viết + chọn ảnh) chiếm 58% thời gian, trung vị 9,5 s, tỉ lệ thuận với độ dài câu trả lời; chọn ảnh chạy sau khi viết xong.

| Bước | Thay đổi |
|---|---|
| 0. Đo | Trace `writer[]` mỗi lần sinh: `first_chunk_ms`, `generation_ms`, `output_chars`, `prompt_tokens`, `completion_tokens`, `reasoning_tokens`; `images.ms`. Đường stream trước đây không ghi token bước viết, nay ghi vào `usage` như đường JSON |
| 1. Ảnh song song | Ngay khi Agent `finish`, chọn ảnh trên evidence Agent đã chọn, song song với bước viết; viết xong chỉ giữ ảnh của nguồn được trích dẫn. Lọc xong mà không còn ảnh nào thì chọn lại một lần trên nguồn được trích dẫn (`images.parallel = "fallback"`) |
| 2. Câu trả lời gọn | `answer.md`: độ dài mục tiêu (60–120 từ cho một dữ kiện, 150–250 từ cho route/chiến thuật/so sánh/build), không nhắc lại câu hỏi, không lặp, không tóm tắt cuối; bảng build còn 2 cột (Attribute, Points), lý do viết 2–3 câu dưới bảng |

### Kết quả trên 14 câu mới (thinking bước viết bật, như `.env` dev)

| Chỉ số | Trước | Sau bước 0–2 |
|---|---:|---:|
| Grounded | 14/14 | 14/14 |
| Tổng thời gian trung bình / trung vị | 20,9 / 18,9 s | **17,4 / 17,6 s** |
| Phần sau Agent trung bình | 12,2 s | **8,0 s** |
| Độ dài câu trả lời trung bình | 1.018 ký tự | **662 ký tự** |
| Câu chậm nhất | 56,1 s (NB-12) | **31,5 s** (NB-04, do Agent) |

Thời gian chọn ảnh (0,7–3,4 s) giờ nằm hoàn toàn trong lúc viết. Lượt đầu chưa có dự phòng: ảnh giảm từ 22 xuống 15 (NB-08, NB-10, NB-12 về 0) vì ảnh được chọn thuộc nguồn không được trích dẫn. Sau khi thêm dự phòng, chạy lại 4 câu: NB-10 có 3 ảnh, NB-12 có 1, NB-01 có 2; NB-08 đi đường dự phòng nhưng model chọn ảnh không chọn ảnh nào trong 3 ứng viên của nguồn được trích dẫn.

### Thinking ở bước viết

Số đo mới cho thấy `RAG_THINKING_ENABLED=true` trong `.env` dev: bước viết chạy thinking, reasoning chiếm 43–84% token đầu ra (ví dụ NB-10: 1.274/1.520), và chunk đầu chỉ tới ở ~85% thời gian sinh. Vì vậy bỏ "giữ câu" gần như không giúp khi thinking bật. So sánh cùng 14 câu, cùng code, chỉ đổi biến môi trường của lần chạy:

| Chỉ số | Thinking bật | Thinking tắt |
|---|---:|---:|
| Grounded | 14/14 | 14/14 |
| Lần sinh lại | 0 | 0 |
| Bảng build đúng tổng level + 79 | 6/6 | 6/6 |
| Thời gian sinh trung bình | 7,9 s | **2,5 s** |
| Tổng thời gian trung bình / trung vị | 17,4 / 17,6 s | **12,1 / 12,6 s** |
| Nguồn được trích dẫn trung bình | 2 | 3 |
| Đoạn không trích dẫn (tổng) | 12 | 19 |

Trên bộ câu này thinking không cải thiện grounded, số lần sinh lại hay độ đúng của bảng build; chênh lệch duy nhất có lợi cho thinking là ít đoạn không trích dẫn hơn. Đọc so NB-07 (so sánh Moonveil và Dark Moon Greatsword): hai bản tương đương về nội dung, bản tắt thinking thiếu trích dẫn ở câu mở đầu. Chưa đổi `.env`; giữ hay tắt thinking chờ MinhMuc quyết.

Dữ liệu thô: `backend/data/research_runs/2026-11-23-{toi-uu-viet,anh-du-phong,viet-khong-thinking}/`.

## 7. Thinking có chọn lọc (MinhMuc duyệt 23/11)

Yêu cầu: "chỗ nào cần bật mới bật, chỗ nào không cần thiết hãy để tắt". Meta-prompt và 3 câu làm rõ ghi trong TrueBrain (`meta-prompt-thinking-co-chon-loc`): Agent quyết câu nào cần nghĩ; thử cả thinking cho Agent; kiểm bằng 14 câu mới + 6 câu khó mới.

| Lần gọi model | Trước | Sau |
|---|---|---|
| Bước viết, lần sinh đầu | Nghĩ ở mọi câu khi `RAG_THINKING_ENABLED=true` | Chỉ nghĩ khi `RAG_THINKING_ENABLED=true` **và** Agent khai báo `finish.needs_reasoning=true` (nguồn mâu thuẫn hoặc phụ thuộc điều kiện, so sánh nhiều tiêu chí, quest/route nhiều bước). Trace `writer_thinking` |
| Agent | Luôn tắt | Mặc định tắt; cờ thử nghiệm `CHAT_AGENT_THINKING`. Adapter gửi lại `reasoning_content` (DeepSeek bắt buộc khi có tool, thiếu thì 400; `langchain_deepseek` 1.1.1 không tự làm). Lượt `finish` bắt buộc luôn tắt |
| Lần sinh lại, Answer Guard, chọn ảnh, rewrite ảnh | Tắt | Tắt |

Bộ câu khó mới [manifest-cau-kho.json](manifest-cau-kho.json) (HR-01..06, đã đối chiếu không trùng các manifest trước): Malenia có kháng bleed không (nguồn trái ngược), cầm hai tay tính Strength thế nào (phụ thuộc điều kiện), questline Millicent theo thứ tự, các nhánh questline Sellen, so sánh Nagakiba/Uchigatana/Wing of Astel theo 3 tiêu chí, Mimic Tear qua các patch.

Hai lần chạy, cùng code, `.env` dev (`RAG_THINKING_ENABLED=true`); chỉ đổi biến môi trường của lần chạy:

- **(a)** bước viết theo Agent, Agent tắt thinking (cấu hình mặc định mới).
- **(b)** như (a), thêm `CHAT_AGENT_THINKING=true`, `CHAT_AGENT_TIMEOUT_SECONDS=30` (hạn mỗi lượt 12 s không đủ khi Agent nghĩ).

### 14 câu mới NB-01..14

| Chỉ số | Bật mọi câu (trước) | Tắt hẳn | **(a) theo Agent** | (b) + Agent thinking |
|---|---:|---:|---:|---:|
| Grounded | 14/14 | 14/14 | **14/14** | 14/14 |
| Câu bước viết nghĩ | 14 | 0 | **4** (NB-03, 07, 08, 09) | 4 (NB-03, 04, 07, 09) |
| Tổng thời gian trung bình / trung vị | 17,4 / 17,6 s | 12,1 / 12,6 s | **13,7 / 12,7 s** | 19,8 / 17,7 s |
| Câu chậm nhất | 31,5 s | 20,1 s | **21,3 s** | 41,9 s |
| Thời gian sinh trung bình | 7,9 s | 2,5 s | **3,8 s** | 4,3 s |
| Đoạn không trích dẫn (tổng) | 12 | 19 | **16** | 12 |
| Lượt `finish` bắt buộc | 0 | 0 | **0** | 1 |
| Token ra của Agent trung bình | 867 | 1.022 | **997** | 1.817 |

### 6 câu khó HR-01..06

| Chỉ số | **(a) theo Agent** | (b) + Agent thinking |
|---|---:|---:|
| Grounded | **6/6** | 6/6 |
| Agent yêu cầu nghĩ | **6/6** | 6/6 |
| Tổng thời gian trung bình / max | **19,9 / 26,7 s** | 33,6 / 45,2 s |
| Đoạn không trích dẫn | **0** | 0 |
| Lượt `finish` bắt buộc | **0** | 2 (HR-01, HR-02, chạm hạn thời gian chuẩn bị) |
| Token vào / ra của Agent trung bình | **35,6k / 610** | 45,2k / 1.872 |

Nhận xét:

- Agent khai báo đúng nhóm: 6/6 câu khó và các câu so sánh, quest, chiến thuật boss; không câu build nào xin nghĩ (build đã tính bằng `run_python`). NB-03 (tìm vị trí vật phẩm, tên gõ sai) xin nghĩ dù không cần, tốn thêm khoảng 4 s.
- 16 đoạn không trích dẫn ở (a) đều nằm ở câu không nghĩ, phần lớn là câu build (NB-05, 11, 13: mỗi câu 3). Ở mọi câu được nghĩ, số đoạn không trích dẫn là 0.
- Agent thinking (b) không tăng grounded, làm chậm khoảng 6 s ở câu thường và 14 s ở câu khó, gấp đôi token ra, gây 3 lượt `finish` bắt buộc vì chạm hạn, và HR-02 45,2 s vượt hạn 45 s của Discord. Đọc so HR-01 và HR-04: nội dung tương đương; HR-04 bản (b) thêm một chi tiết (Shard Spiral), HR-01 bản (b) có một câu cuối không trích dẫn.
- Không có lỗi 400 ở (b), tức adapter gửi lại `reasoning_content` đúng; `tool_choice="auto"` chạy được khi thinking bật.

Đề xuất: giữ (a) làm mặc định (`RAG_THINKING_ENABLED=true`, `CHAT_AGENT_THINKING=false`). Đoạn không trích dẫn của câu build xử lý bằng prompt nếu cần, không bật thinking cho build.

Dữ liệu thô: `backend/data/research_runs/2026-11-23-thinking-{a,b}-{cau-moi,cau-kho}/`.
