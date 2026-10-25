# Bàn giao RAG baseline armor và golden set v0

Ngày: **26/10/2026**, múi giờ Asia/Saigon. Phụ trách: **TV3 — MinhMuc**. Tài liệu được trợ lý bổ sung theo yêu cầu người dùng; không thay thế xác nhận đóng góp/review của các thành viên.

## 1. Phạm vi và trạng thái Git

Hai thẻ S1 trong [kế hoạch sprint](../../planning/sprint_plan.json): **Notebook RAG baseline** và **Golden set v0 (30 câu)**. Liên quan FR-RET-02, FR-GEN-01, FR-EVAL-01. Phạm vi theo [ADR-004](../adr/004-base-game-scope.md): lore Elden Ring base game.

Lịch sử được đối chiếu bằng Git local sau fetch ngày 26/10/2026:

| Phần việc | Commit/PR | Trạng thái đã quan sát |
|---|---|---|
| Baseline 240 armor và nhận xét | `280ed6e`, [PR #20](https://github.com/HoanBuCon/Index-Beast/pull/20), merge `47530cb` | Đã có trong lịch sử `develop` |
| Golden set ban đầu | `410fbc0` | Bị push nhầm trực tiếp lên `develop` |
| Revert golden set | `586a90e`, [PR #21](https://github.com/HoanBuCon/Index-Beast/pull/21), merge `a0c168f` | Đã đảo thay đổi ban đầu |
| Đưa lại JSONL qua nhánh riêng | `c54825b`, [PR #22](https://github.com/HoanBuCon/Index-Beast/pull/22), merge `dd7f033` | Golden set đã trở lại `develop` |
| Chỉnh sửa JSONL tiếp theo | `f5be460`, `dbd9221` | Sau hai commit này, file hiện có đủ 30 câu |

Nhánh bổ sung bàn giao: `docs/s1-tv3-handover-rag-va-golden-set`, tách từ `origin/develop` tại `dbd9221`. Chưa tạo commit/PR cho nhánh tài liệu tại thời điểm viết. Không suy ra CI hoặc Mentor đã approve chỉ từ việc có merge commit.

## 2. File và điểm tiếp nhận

- [Notebook baseline](../../backend/notebooks/01_rag_baseline_e5_bm25.ipynb): cấu hình, đọc CSV, embedding/index, retrieval, prompt, gọi DeepSeek, chấm 10 câu và tổng hợp.
- [Hướng dẫn chạy notebook](../../backend/notebooks/README.md) và [requirements riêng](../../backend/notebooks/requirements.txt).
- [Bảng nhận xét lượt chạy 25/10](../evaluation/2026-10-25-armor-baseline-review.md): bằng chứng đánh giá được lưu trong Git.
- [Golden set](../../backend/eval/golden_set.jsonl): đầu vào bộ đánh giá toàn dự án.
- [Khung retrieval eval](../../backend/eval/retrieval.py) và [khung answer eval](../../backend/eval/answer.py): hiện còn là skeleton, chưa phải runner hoàn chỉnh.
- [`AGENTS.md`](../../AGENTS.md) và [README handover](README.md): ghi yêu cầu luôn bàn giao trước khi báo hoàn tất.

`backend/eval/README.md` của bản golden set ban đầu đã bị revert và **chưa được khôi phục** trong phiên bản đang bàn giao. Quy tắc sử dụng hiện được ghi ở mục 5 dưới đây. Đường dẫn `eval/golden_set.jsonl` trong checklist được hiểu từ thư mục `backend/`, tương ứng `backend/eval/golden_set.jsonl` tại gốc repo.

## 3. Baseline: dữ liệu, retrieval và DeepSeek

Theo yêu cầu kiểm thử của người dùng, notebook thay đầu vào 200 trang mẫu trong kế hoạch bằng **240 bản ghi dữ liệu đầu tiên** của `elden-ring-data/armors.csv`, không tính header. Đây là phép thử trên subset, chưa hoàn thành mục dùng corpus mẫu của TV2. Dataset không nằm trong Git.

- Mỗi dòng armor là một tài liệu/point. Text retrieval dùng tên, category, weight và description; không có toàn bộ thông số chiến đấu.
- Embedding `intfloat/multilingual-e5-small` qua FastEmbed ONNX, 384 chiều; thêm đúng một lần `passage:` cho tài liệu, `query:` cho câu hỏi. Đầu vào dense giới hạn 512 token, payload giữ mô tả đầy đủ.
- Qdrant named vectors `dense` và `bm25`; BM25 tiếng Anh, sparse có IDF. Hybrid RRF lấy **top-5** cho generation.
- Mặc định dùng Qdrant memory; có thể chọn server theo hướng dẫn notebook. Collection baseline riêng có fingerprint, không dùng chung collection ứng dụng.
- Nguồn CSV dùng định danh `elden-ring-data/armors.csv#data-row=<n>`, là số bản ghi không tính header. Không dùng URL ảnh làm URL bài nguồn hoặc tự tạo URL wiki.
- DeepSeek lấy key và `LLM_MODEL` từ `.env` qua adapter hiện có. Cấu hình baseline non-thinking, output tối đa 512 token/lượt. Không ghi key vào notebook, output hoặc tài liệu.
- Prompt Index-Beasts yêu cầu trả lời thẳng, thường 1–3 câu, đúng ngôn ngữ, giữ tên riêng tiếng Anh, dẫn `[n]` theo top-5; phân biệt bản altered và giữ sắc thái như “rumored”. Không gửi đáp án chuẩn cho LLM.

**Trạng thái notebook hiện tại:** đã lưu output và 14 code cell có execution count; cell cấu hình đang để **`RUN_LLM=True`**. Đầu README notebook còn mô tả giai đoạn trước khi người dùng chạy, nên không dùng đoạn trạng thái đó để khẳng định notebook hiện không có output. Người nhận cần đọc cell cấu hình trước khi chạy.

Các lệnh dưới đây chỉ là hướng dẫn cho người dùng, **không được chạy tự động**:

```powershell
# Từ gốc repository; chỉ cài nếu môi trường còn thiếu thư viện.
cd backend
.\.venv\Scripts\python.exe -X utf8 -m pip install -r notebooks/requirements.txt
.\.venv\Scripts\python.exe -X utf8 -m jupyterlab notebooks/01_rag_baseline_e5_bm25.ipynb
```

Chọn kernel `backend/.venv`. Để chỉ kiểm tra retrieval, đổi `RUN_LLM=False` trước khi chạy các cell; khi muốn gọi DeepSeek thật, người dùng chủ động bật lại. Chạy lại cell đánh giá có thể phát sinh thêm lượt API. Chi tiết thứ tự cell và Qdrant server nằm trong README notebook.

## 4. Kết quả baseline đã có và giới hạn

Người dùng đã tự chạy DeepSeek. Trợ lý chỉ đọc câu trả lời và top-5 nguồn đã lưu để chấm, không gọi lại API.

- Run được chấm: **`20261025T144625694379Z`**, model ghi trong báo cáo là `deepseek-flash`.
- 10 câu: 5 Việt, 5 Anh; Hit@5 = **10/10**. MRR@5: Việt **0,700**, Anh **0,900**, chung **0,800**.
- Correctness **20/20**, faithfulness **20/20** theo thang 0–2, đối chiếu chính các đoạn CSV đã truy xuất. Đây là nhận xét có trợ lý hỗ trợ, không phải kết quả một lượt judge LLM độc lập hoặc xác minh sự thật trong game.
- VI02, VI05, EN03, EN05 thêm chi tiết không được hỏi nhưng có nguồn. VI03 cần dịch tự nhiên hơn. Một số nguồn đúng nằm hạng 2 do hạng 1 là biến thể hoặc món khác.

Xem [bảng chấm từng câu](../evaluation/2026-10-25-armor-baseline-review.md). JSON đầy đủ nằm trong thư mục local bị ignore `backend/data/notebook-baseline/`; máy clone mới cần nhận artifact từ người chạy hoặc tự chạy khi được yêu cầu. Model cache cũng không nằm trong Git.

`MANUAL_REVIEW` được gắn `REVIEWED_RUN_ID = "20261025T144625694379Z"`. Không áp dụng các điểm này cho lượt khác. Để cập nhật hiển thị của đúng lượt đã chấm, người dùng chỉ cần chạy cell lưu review và cell tổng hợp theo tài liệu đánh giá.

Không suy rộng điểm trên 10 câu demo thành chất lượng toàn chatbot: câu được chọn từ armor đã biết có trong subset, nguồn CSV chưa xác minh độc lập và notebook chưa pin revision model để tái lập nghiêm ngặt.

## 5. Golden set v0: hợp đồng và cách đánh giá

Tại `dbd9221`, JSONL có **30 câu, 20 Việt/10 Anh**, ID ổn định `IB-GS-001` đến `IB-GS-030`. Mỗi dòng đúng bảy trường:

```text
id, question, lang, expected_answer, source_urls, category, difficulty
```

`source_urls` là array URL, các trường còn lại là string; `lang` dùng `vi`/`en`. UTF-8, một JSON object mỗi dòng, không bao ngoài bằng array.

| Category | ID | Số câu |
|---|---|---:|
| `character` — nhân vật | 001–006 | 6 |
| `event` — sự kiện | 007–012 | 6 |
| `location` — địa điểm | 013–018 | 6 |
| `multi_hop` — kết hợp quan hệ/nhân quả | 019–024 | 6 |
| `out_of_scope` — yêu cầu ngoài phạm vi lore | 025–030 | 6 |

Độ khó thiết kế: **12 easy, 12 medium, 6 hard**; chưa được hiệu chỉnh bằng kết quả chạy. Sáu câu đa bước có ít nhất hai URL tham chiếu. Nhiều URL không chứng minh pipeline bắt buộc phải lấy nhiều chunk nếu một chunk đã chứa đủ ý.

Quy tắc tiếp nhận:

1. Chỉ gửi `question` cho hệ thống RAG. Không index đáp án chuẩn và không đưa `expected_answer` vào prompt trả lời.
2. Với 24 câu lore, chấm theo ý nghĩa và độ đủ ý, không bắt khớp từng chữ. Correctness đối chiếu đáp án chuẩn; faithfulness phải đối chiếu ngữ cảnh **thực sự được truy xuất**.
3. Sáu câu ngoài phạm vi có `source_urls: []`: chấm tỉ lệ từ chối đúng riêng, loại khỏi Recall/MRR. Không bịa nguồn để điền array hoặc phạt vì không có trang lore cho yêu cầu ngoài phạm vi.
4. Chuẩn hóa redirect/canonical URL theo cùng quy tắc với crawler trước khi tính retrieval. Phân biệt Hit@k, recall theo nguồn và độ phủ bằng chứng đa bước; không coi mọi URL tham khảo của câu đơn là đồng thời bắt buộc.
5. **Không dùng golden set toàn dự án để kết luận chất lượng index chỉ có 240 armor.** Trước khi eval cần kiểm coverage nguồn trong corpus.
6. Khi đổi nội dung, lưu phiên bản/hash golden set cùng cấu hình, corpus và Git SHA của lượt eval. Không dùng bộ đã tinh chỉnh prompt làm test độc lập.

Nguồn ban đầu được đối chiếu qua nội dung wiki.gg do công cụ tìm kiếm lập chỉ mục; mở trực tiếp trang mẫu gặp 403. Chưa xác minh toàn văn, toàn bộ URL/revision hoặc trực tiếp trong game. TV2 cần review nguồn và scope ở cấp section; không index toàn bài chỉ vì URL có trong golden set. Nội dung người dùng thay đổi sau bản nháp cũng cần review lại, không kế thừa nhãn đã kiểm chứng một cách tự động.

Phân công review **đề xuất**, chưa ghi nhận đóng góp thay thành viên: Hoanbucon 001–008, UncleThing 009–016, MinhMuc 017–023, QuyVuiVe 024–030. Mỗi người tự kiểm tra/sửa/bổ sung ít nhất năm câu và xác nhận qua review. Chưa có bằng chứng để đóng checklist “Mỗi người đóng góp ≥ 5 câu”.

## 6. Sự cố Git và cách tránh lặp lại

- Golden set từng bị push trực tiếp lên `develop`. Đã xử lý bằng commit revert trên nhánh riêng và PR #21; sau đó JSONL được đưa lại qua PR #22. Không reset/force-push lịch sử chung.
- Khi đã merge một commit rồi revert, Git vẫn ghi nhận commit gốc trong ancestry. Muốn đưa lại nội dung cần commit khôi phục mới, không chỉ mở lại PR từ commit gốc.
- Nhánh tạo từ `origin/develop` từng có upstream trỏ về `develop`. Từ nay tạo nhánh bằng `git switch --no-track -c <nhanh-moi> origin/develop`, push đầu bằng `git push -u origin <nhanh-moi>`, kiểm tra `git branch -vv`.
- Lỗi VS Code “Please clean your repository working tree before checkout” trong lượt đã xử lý chỉ do một dấu cách cuối dòng cuối JSONL. Đã bỏ đúng dấu cách sau khi xem diff. Với lần khác phải kiểm tra lại `git status`/`git diff`; không mặc định discard mọi thay đổi người dùng.
- Kết nối GitHub plugin từng trả 403 khi tạo PR; PR #21 được tạo bằng tài khoản Git đang có quyền. Không lưu token hoặc output credential vào repository.

## 7. Kiểm tra khi bổ sung handover

Chỉ đọc file/lịch sử và kiểm tra tĩnh; không thực thi notebook, tải model, tạo index hoặc gọi API LLM. Đã kiểm tra JSONL: 30 bản ghi, đúng schema/ID, phân bố ngôn ngữ/category/difficulty và quy tắc nguồn; kiểm tra UTF-8, liên kết local của các tài liệu mới/cập nhật và whitespace diff. Không coi các kiểm tra này là chạy eval hoặc CI toàn dự án.

Thay đổi bổ sung lần này chỉ gồm `AGENTS.md`, `docs/handover/README.md` và tài liệu bàn giao này; không sửa notebook, output hoặc nội dung golden set.

## 8. Việc còn lại

- TV2/TV3 review chéo đáp án, bằng chứng và canonical URL; cả nhóm xác nhận đóng góp trước khi đóng thẻ golden set.
- Đồng bộ trạng thái đầu README notebook với output đã lưu, khôi phục hướng dẫn golden set nếu cần một entry point riêng.
- Tách test độc lập, bổ sung câu không có đáp án/câu dễ nhầm biến thể và giữ bộ đo phù hợp phạm vi corpus.
- Hoàn thiện runner retrieval/answer eval và lưu cấu hình, coverage, metrics đúng từng lượt.
- Chạy lại baseline trên corpus đã xử lý của TV2 khi người dùng yêu cầu; không thay kết quả hiện có bằng giả định.
- Với mỗi nhóm task mới, cập nhật handover cùng thay đổi trước khi báo hoàn tất, theo `AGENTS.md`.
