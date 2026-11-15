# Rà soát phần việc TV2 · Golden set S4

Ngày 16/11/2026 (Asia/Saigon), Codex thực hiện thay phần việc TV2 — UncleThing theo yêu cầu của TV3. TV3 cho biết TV2 giao AI thực hiện và nhận trách nhiệm. Phiếu ghi vai trò chịu trách nhiệm tại `reviewer=TV2 - UncleThing`, đồng thời ghi `delegated_review.performed_by=Codex`, `method=delegated_ai_local_review` và `human_direct_review=false`. Đây là kết quả duyệt theo ủy quyền được TV3 cung cấp, không phải bằng chứng TV2 tự kiểm tra trực tiếp hoặc lượt chấm độc lập của con người.

## Phạm vi và phương pháp

- Đọc đủ 200 câu IB-GS-101–300, đáp án, nhãn và quote tham chiếu: 183 ca dữ kiện, 17 ca hành vi, 11 lượt bổ sung. Đọc riêng nhận xét cũ và đối chiếu lại 26 ca có `assistant_review.outcome=revised`.
- Đối chiếu corpus S4 local: chunk ID, số dòng, URL, vị trí quote và SHA-256. Đọc nội dung để kiểm chủ thể, con số, điều kiện, thứ tự nhiệm vụ và tính đầy đủ của bằng chứng; kiểm phép trừ 20−15=5 điểm phần trăm và 14−9=5 Intelligence.
- Kiểm câu hành vi theo phạm vi Elden Ring base + Shadow of the Erdtree, sự mơ hồ thực sự và yêu cầu đã thay đổi ở lượt sau. Câu gõ sai nhưng có tên rõ không bị chuyển thành ca phải hỏi lại.
- Kiểm độ khó theo nhãn biên soạn: easy cho nhận diện/tra đơn; medium cho ngữ cảnh, alias và điều kiện; hard cho kết hợp, so sánh, hội thoại hoặc thiếu nhiều thông tin. Giữ nhãn đã khóa; chưa hiệu chuẩn độ khó trên người chơi. `scope=pass` là kiểm phạm vi dự án/hành vi, không có nghĩa mọi `release_scope=unknown` đã được phân loại base/SotE.
- `source_urls=pass` chỉ xác nhận provenance trên artifact local; không xác nhận URL còn truy cập được hay nội dung web hiện tại. Ca hành vi không có URL ở lượt đầu ghi `not_applicable`; lượt bổ sung có bằng chứng vẫn được kiểm đầy đủ.

[Meta-prompt đã thực hiện](../prompts/2026-11-16_tv2-s4-golden-review-local.md) · [Rubric](s4-rubric.md) · [Phiếu từng ca](../../backend/eval/reviews/s4-golden-set-review.jsonl) · [Số liệu và hash](2026-11-16_s4-tv2-local-review.json)

## Kết quả

| Hạng mục | Kết quả |
| --- | --- |
| Tổng số câu đã rà | 200/200 |
| Đạt theo hình thức duyệt thay TV2 | 198 |
| Cần chỉnh | 2: IB-GS-265, IB-GS-279 |
| Còn `pending` | 0 |
| Kiểm lại 26 ca từng sửa | 25 đạt, 1 cần chỉnh (IB-GS-279) |
| Ca dữ kiện có quote khớp corpus | 183/183 |
| Lượt bổ sung có quote khớp corpus | 11/11 |
| Tổng số lượt quote đối chiếu, kể cả bằng chứng bổ sung | 256 |
| Test `tests/unit/test_golden_set.py` | 9 đạt |
| Gate `--require-reviewed` | Chưa đạt; `accepted=false`, do còn 2 ca cần chỉnh |

Số 256 là lượt xuất hiện quote trong các hồ sơ, không phải số chunk độc lập hoặc số câu hỏi. Không có phép đo Accuracy mới.

## Hai ca cần chỉnh

### IB-GS-265 — “tim riêng” chưa định danh Heart of Bayle

Đáp án Ancient Dragon-Man → Dragon-Hunter's Great Katana và Bayle → Heart of Bayle có nguồn. Tuy nhiên, câu Việt chỉ nói boss ở Jagged Peak cho “tim riêng”. Corpus còn ghi Jagged Peak Drake tại chân/gần đỉnh núi rơi Dragon Heart. Vì vậy chưa đủ để bắt buộc một cách hiểu duy nhất về phần tim.

Đề xuất phiên bản tiếp theo: “Ở Dragon's Pit, boss nào rơi Dragon-Hunter's Great Katana; tại Jagged Peak, boss nào rơi Heart of Bayle?” Bản EN IB-GS-266 đã nêu Bayle trực tiếp nên không có cùng vấn đề. Lưu hai quote đối chứng về Jagged Peak Drake trong `delegated_review.supplemental_evidence`, không thêm chúng vào nguồn vàng của benchmark.

### IB-GS-279 — Chưa khóa lần gặp Diallos tại Roundtable Hold

Quote progression có hai lần Diallos ở Roundtable Hold: lần đầu nhờ tìm Lanya, tiếp theo ở Liurnia phía bắc Academy Gate Town; sau khi trở lại Roundtable, ông nói về Volcano Manor. Câu đầu và followup hiện chỉ nêu vừa gặp Diallos ở Roundtable nên chưa phân biệt được chặng. Đáp án Liurnia đúng khi giả định lần gặp đầu.

Đề xuất followup phiên bản tiếp theo: “Đó là Diallos, mình vừa gặp ông lần đầu tại Roundtable Hold và nghe ông nhờ tìm Lanya. Chỗ gặp tiếp theo ở đâu?” Giữ nguyên câu và điểm hồi quy đã công bố; chưa duyệt vô điều kiện phiên bản hiện tại.

## Bằng chứng bổ sung và tính ổn định của benchmark

Lưu thêm bằng chứng kiểm tra trong `delegated_review.supplemental_evidence` cho 6 ca:

- IB-GS-247/248: Notes của Sacrificial Twig xác nhận cần equip; mô tả Twiggy Cracked Tear xác nhận mix trong Flask of Wondrous Physick. Quote Effect cũ chỉ chứng minh tác dụng, thời gian và ngoại lệ Death Blight.
- IB-GS-251/252: mô tả Sacred Tear xác nhận restorative effects, làm rõ “lượng hồi” thay vì chỉ số lần nâng cấp.
- IB-GS-265: hai biến thể Jagged Peak Drake có Dragon Heart, làm bằng chứng cho vấn đề diễn đạt.
- IB-GS-284: acquisition Greatsword xác nhận Caelid, đối chiếu cả tiền đề cùng weight 23 và Colossal Sword trong infobox.

Giữ nguyên golden set, `author_evidence`, `followup`, `assistant_review`, nhãn phạm vi và nhóm biến thể. Harness ma trận vẫn lấy `gold_chunks` từ `author_evidence`, nên tập nguồn và đáp án dùng cho các lượt đo lịch sử không đổi. Hash review đổi vì kết luận và metadata duyệt mới; hash trước/sau, golden set và corpus nằm trong JSON tổng hợp. Đã so sánh từng trường với Git HEAD trước khi cập nhật.

## Kiểm tra và tái lập

Từ `backend/`, chỉ thực hiện kiểm tra offline:

```powershell
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --corpus data/chunk_runs/s4-wiki-release/chunks.jsonl
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --corpus data/chunk_runs/s4-wiki-release/chunks.jsonl --require-reviewed
.venv/Scripts/python.exe -X utf8 -m pytest tests/unit/test_golden_set.py -q
```

Lệnh đầu kiểm schema/provenance; lệnh thứ hai trả `schema_valid=true`, `review_gate_passed=false`, `accepted=false` và cố ý không thành công khi hai ca còn cần chỉnh. Test đơn vị đạt 9/9. Bộ dựng kết quả và kiểm 256 quote lưu local tại `backend/data/research_runs/2026-11-16-s4-tv2-local-review/review.py`; thư mục data bị Git bỏ qua. Phiếu đã lưu là hồ sơ quyết định, validator không tự chấm ngữ nghĩa thay người đọc.

Không gọi DeepSeek/Tavily, HTTP hoặc model; không embedding, re-index, cập nhật DB hay thử giao diện public. Dùng lại dữ liệu do Codex từng rà ngày 14/11; đây là lượt rà lại local cùng công cụ. Các số Accuracy/Recall/MRR ngày 14/11 và yêu cầu kiểm website sau publish vẫn giữ nguyên ý nghĩa ban đầu.
