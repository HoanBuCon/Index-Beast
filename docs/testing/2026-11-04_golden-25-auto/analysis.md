# Chẩn đoán thật 25 câu IndexBeast — 04/11/2026

**Đã hoàn tất 25/25 câu, không dừng giữa chừng.** Đây là development diagnostic ở mode auto;
không phải đánh giá cuối hoặc điểm Accuracy của đồ án. Không sửa pipeline/prompt trong khi chạy.

## Artifact để đọc và review

- [Report gốc có checkpoint, query/context/output thật](report.json).
- [Phiếu đọc từng câu và context](review.md).
- [Mẫu điểm còn để trống](manual_review.jsonl).
- [25 nhận xét hỗ trợ bởi Codex, chưa review chéo](observations.json).
- [Manifest 25 câu](../../../backend/eval/diagnostic_25.json).

## Cấu hình và phương pháp

25 ID nguyên bản từ golden set 60 câu: **18 VI, 7 EN**. Category: 2 character, 1 event, 3 location,
4 multi_hop, 6 mechanics, 4 equipment, 3 quest, 1 insufficient_evidence, 1 out_of_scope.
Tất cả 60 nhãn review nguồn/đáp án vẫn pending; validation xác nhận 24 author-evidence case của bộ 60
khớp quote/hash artifact, không tự coi là TV2 approved.

Pipeline ở HEAD `dfc0286`, collection `indexbeast_tv3_integration_20261029_c1871afc`, **18.368 point**.
DeepSeek `deepseek-flash`, temperature 0.2, max output 4096, thinking false, rewrite true, query mode rewrite,
top-5, context 12000 ký tự, timeout mỗi case 45 giây. Dùng cache `models/notebook-fastembed` và HF offline.
Không có index/upsert/crawl/ghi PostgreSQL hoặc sửa .env. Transport retry SDK đặt **0 trong runner** để
giới hạn chi phí; đây là khác biệt có ghi nhận với app nếu app cấu hình retry khác 0.

Chạy trực tiếp pipeline, không POST HTTP chat endpoint; 502 bên dưới là status tương đương của
exception trong code, không tuyên bố đã đo API/UI. Không gọi image resolver, không đo ảnh web.
Mỗi câu độc lập history rỗng: chưa đo follow-up. Không có câu starting class hoặc chia điểm hợp lệ chi tiết
trong golden hiện tại, nên không suy rằng đã kiểm đủ các năng lực đó.

Lệnh **đã chạy** từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_golden --execute --allow-llm --allow-web --mode auto --output-dir ../docs/testing/2026-11-04_golden-25-auto
```

## Kết quả vận hành

| Chỉ số | Thực tế |
|---|---:|
| Case hoàn tất thử | 25/25 |
| Phản hồi hợp lệ | 24/25 (96%) |
| Grounded theo validator | 23 |
| Static đúng chặn injection | 1 |
| Case lỗi generation | 1 (IB-GS-027) |
| Query web thực hiện | 24/25 |
| Assessment lỗi contract | 23/24 |
| Rewrite được chấp nhận | 16/24 |
| Rewrite fallback | 8/24 |
| Generation retry | 2 case |
| Median latency, tính cả case lỗi/static | 8,324 giây |
| p95 latency, nearest rank | 12,354 giây |
| Tổng thời gian các case, không tính setup | 213,274 giây |
| Logical LLM call | 74 (24 rewrite + 24 assessment + 26 generation) |
| Tavily request theo đường thực thi adapter | 48 (24 Search + 24 Extract, không retry) |
| Prompt/completion token được provider báo | 201.813 / 12.565 |
| Có ít nhất một trang target trong context | 20/23 câu factual (86,96%) |

96% là tỷ lệ nhận output hợp lệ, **không phải Accuracy**. 20/23 là match URL trang draft,
không phải Recall@5 evidence hay correctness. Các miss 003/013/023 có thể dùng trang khác vẫn chứa đáp án.
Không có nhãn chunk-relevance đầy đủ nên Precision/Recall/MRR chưa tính. Token không quy thành tiền
vì chưa đối chiếu bảng giá/cache billing; không tự suy chi phí từ số call.

## Các lỗi có bằng chứng

### 1. Auto đang gần như tìm web mọi câu vì contract assessor lệch

23 assessor output là JSON hợp lệ, nhiều câu ghi sufficient, nhưng evidence có dạng
`{"1":["q0"]}`. Backend yêu cầu `dict[str,str]`, tương đương `{"1":"q0"}`.
Do validation thất bại, trace ghi assessment_failed và fallback search. Đây không phải
bằng chứng 23 câu thiếu local. Một case còn lại assessor chấp nhận insufficient; injection bỏ qua cả hai.

Ưu tiên sửa schema/prompt/example cùng nhau, giữ reference validation và test dạng output thật.
Không đơn giản đổi mọi assessment_failed thành sufficient.

### 2. Guard rewrite từ chối bản dịch đúng ý

6 case proper_name_lost: 007/031/045/048/049/050; 2 case entity_lost: 035/036.
Các output thật cho thấy ý định vẫn đúng: từ mở đầu Ai/Trong/Theo/Sau/According có thể bị coi là tên,
và Fragment/Fragments, Ash/Ashes bị coi là mất entity. Cần sửa guard theo ngữ cảnh và biến thể xác minh,
không bỏ bảo vệ entity/number/goal. Case 048 bằng EN cũng bị ảnh hưởng, không quy hết lỗi cho tiếng Việt/E5.

### 3. Build 027 vẫn tái hiện được validation 502

Lượt đầu thêm field `type=json_object` ngoài schema → schema_invalid. Lượt recovery dùng hết budget
rồi trả insufficient=true nhưng vẫn có citation/evidence → insufficient_with_citations.
Case không được lưu như answer thành công. Cần kiểm contract cho bài toán build/thiếu điều kiện;
không nới validator hoặc coi lỗi đó là một lần từ chối an toàn thành công.

### 4. Retrieval/context thiếu độ phủ câu nhiều phần

Case 044 cần cả hai loại đá: Ancient Dragon Smithing Stone thường đã xuất hiện ở rank 6 local,
nhưng top-5 cuối không chứa evidence mức +25. Web và context tập trung Somber nên chỉ trả được +10.
Đây là lỗi coverage/selection, không đủ căn cứ kết luận corpus không có thông tin thường.

Case 050 có 3 web point cùng text hash `27511bdbf5b9...`, URL alias/current/oldid khác nhau.
Chúng chiếm 3/5 context. Cần dedup khi xác nhận nội dung tương đương, giữ tất cả provenance và không
gộp hai release/patch khác nhau chỉ vì cùng tên. Có thể cần lấy bổ sung đoạn local Questline Progression.

### 5. Grounded=true vẫn có thể sai ngữ nghĩa

Case 050 trả đúng phần thưởng, nhưng suy Carian Inverted Statue là vật cần cho bước kế tiếp quest Ranni;
đáp án draft và đoạn quest local liên quan phân biệt vật này cần cho Fia, không cần hoàn thành Ranni.
Đoạn phủ định đó không có trong context case 050. Không được suy “có công dụng/được thưởng” thành “bắt buộc”.

Case 041 thêm stamina/HP/frostbite từ phần đầu context web 1, nhưng quote_id chọn cho nguồn 1 lại
trỏ đoạn gallery/class không chứng minh số liệu. Validator hiện chỉ xác nhận quote tồn tại và index hợp lệ,
không đánh giá từng claim. Nội dung có thể nằm trong source body nhưng quote trả cho người dùng vẫn sai mục.

### 6. Văn phong và scope câu trả lời còn thừa

001/003/007 mở rộng tiểu sử sau khi đã trả lời câu đơn. 034 gọi hai cách mô tả vị trí là “hơi lệch”
mà chưa chứng minh có mâu thuẫn. 041 còn nói wiki chưa kiểm duyệt và lặp disclaimer; 042/044 lặp thiếu dữ liệu.
Ưu tiên câu trả lời ngắn đúng phần hỏi, tách recommendation khỏi claim và limitation chỉ một lần.

## Điểm đang làm được trong tập nhỏ này

Các mô tả cụ thể như Mimic Tear HP/will (043), Sacred affinity/đối tượng buff (046),
Flame Cleanse Me 14 FP/10 stamina/1 slot (048), bước Church of Elleh (049),
Discarded Palace Key/chest/acquisition (052) bám được các đoạn local đã cấp.
Đây là nhận xét sơ bộ sau đọc evidence, chưa là review chéo hoặc bảo đảm mọi câu tương tự.

## Thứ tự nên sửa sau baseline

1. Contract assessor và guard rewrite, vì đây là lỗi code/prompt đã quan sát thật.
2. Coverage từng phần và dedup web aliases trước khi tăng số nguồn/top-K.
3. Build/insufficient output contract và kiểm claim–quote / suy luận điều kiện bắt buộc.
4. Sau đó mới mở rộng bảng stat/class/progression và test các câu mới.

Không thay runtime code trong tác vụ baseline. Muốn chứng minh sửa có hiệu quả, chạy lại cùng 25 ID
với cấu hình snapshot tương đương và lưu thư mục mới; không ghi đè dữ liệu baseline này.
