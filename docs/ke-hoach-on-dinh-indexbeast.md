# Kế hoạch ổn định IndexBeast trước khi phát triển tiếp

Ngày 07/11/2026 · TV3 MinhMuc · nhóm 4 Hollows.
Đây là **kế hoạch**, chưa thực thi các thay đổi hoặc lượt API mới bên dưới.
Mục tiêu: tiếp tục được khi phiên hiện tại bị giới hạn, sửa đúng điểm nghẽn và tránh tốn quota cho test lặp.

## 1. Điểm bàn giao hiện tại

- Nhánh `feature/s3-tv3-evidence-media-build`; các thay đổi vẫn chưa commit/push/merge.
- Backend915 tests, web41 tests; lint/format/dependency/OpenAPI đã đạt trong tác vụ trước.
- Run thật đã hoàn tất10 lượt: 7 HTTP200, 3 HTTP502; không còn ngân sách của run đó.
- Ảnh local có kết quả đúng chủ thể nhưng run có ảnh trùng/text phủ nhận gửi ảnh.
- Chưa có generic checked_build hoặc ảnh web thành công trong run thật.
- Sửa sau run mới kiểm offline: bounded decision repair, prompt, dedup ảnh, feedback calculator, điều kiện dữ liệu.

Đọc [handover](handover/2026-11-07_s3-tv3_evidence-anh-va-build-tong-quat.md),
[run report](testing/2026-11-07_evidence-media-build-10/README.md),
[contract](api/evidence-media-build.md) trước khi tiếp tục. Không đọc lại cả lịch sử chat hoặc toàn bộ repository.
Không ghi đè run cũ; report.complete không phải lời mời replay các lượt lỗi.

## 2. Thứ tự thực hiện

| Ưu tiên | Công việc | Điều kiện kết thúc | Phụ trách |
|---|---|---|---|
| P0 | Kiểm tra3 decision lỗi và clarification/resume | Các case hồi quy giữ entity/phủ định, constraint đúng nguồn, tối đa2 field; repair có giới hạn | TV3 |
| P1 | Hoàn thiện đầu vào factual cho build tổng quát | Ít nhất2 build khác class/weapon có đầy đủ source data và checked artifact đúng | TV3; TV2 review dữ liệu |
| P2 | Ảnh web có association thực | Provider trả ảnh theo trang, cache/GET/decode/hash đạt, ảnh phù hợp thực thể | TV3; TV4 kiểm giao diện |
| P3 | Tối ưu token và chốt demo | Đo token/call/latency trước-sau trên cùng case; demo đủ tính năng đã xác minh | TV3 + TV4 |

Thực hiện từng gói nhỏ; không đồng thời thêm VLM, AR/DPS, agent tool mới hoặc thay framework.
Chỉ tăng phạm vi sau khi đầu ra của gói trước có bằng chứng. Không tăng đồng loạt budget/temperature.

## 3. Phiên tiếp theo: P0 — ổn định decision

1. Kiểm lại Git, giữ nguyên modified/untracked và làm tiếp trên nhánh hiện có.
2. Đọc `agent.py`, `prompts/agent.md`, fixture3 decision và `test_agent_media_regressions.py`.
3. Replay offline cả decision sai và bản sửa: constraint phải trích đúng substring user, query giữ tên/phủ định,
   clarification tối đa2 field. Kiểm thêm hết budget, repair thất bại, correction và ID clarification.
4. Xác minh repair tối đa1 lần, trong deadline/global6 calls, vẫn giữ1 call cho generation.
   Không biến lỗi thật thành HTTP200 giả, không bỏ assertion provenance/schema để qua test.
5. Sau offline đạt, chuẩn bị manifest4 lượt R1–R4 bên dưới. Chỉ execute khi được người dùng cấp ngân sách mới.
6. Nếu các lượt này vẫn lỗi, dừng test thật và sửa offline; không test lại cả golden set.

**Gate:** resume giữ đúng build/task, không lấy constraint superseded; lỗi có khả năng sửa được có recovery,
output không thể xác thực vẫn báo lỗi đúng contract. Offline pass chưa đủ để khẳng định live đã ổn.

## 4. P1 — build: giải quyết dữ liệu trước

Nguyên nhân EMB06: model dùng source snapshot mới chỉ thấy title, chưa fetch nội dung; sau đó đổi sai schema.
EMB08 không thu thập đủ class/rules/requirements. Đây không phải lỗi phép cộng đơn thuần.

- Cho planner nhìn rõ những nhóm dữ liệu còn thiếu: starting level +8 stats, level/respec/cap,
  weapon requirements và điều kiện một tay/không bonus.
- Agent tự chọn tìm local/web/snapshot để bổ sung; backend trả validation feedback rõ ràng và giữ số học.
  Không thêm rule phân luồng theo tên class/vũ khí, không cho calculator bịa factual data.
- Chuẩn hóa từng bảng nguồn thành dữ liệu versioned, có URL/quote/header/thời điểm/release/patch/uncertainty.
  Có thể bắt đầu bằng2–3 cặp làm mẫu kiểm thử, nhưng schema/algorithm phải nhận dữ liệu mở rộng,
  không đóng danh sách class/weapon trong code. Không tự gán human approval.
- TV2 review nguồn và bảng trích; TV3 kiểm completeness/provenance/số học. Cache chỉ chứa factual inputs.
- Kiểm artifact qua tool→context→generator→JSON/SSE. Generator không được thay8 giá trị; kiểm phép tính độc lập.

**Gate:** ít nhất2 class/weapon ngoài cặp cũ trả allocation khả thi có checked artifact và nguồn đầy đủ.
Chưa gọi là build tối ưu, chưa hứa AR/DPS/soft caps hoặc bonus hai tay.
Nếu chỉ có hướng dẫn định tính thì đánh dấu partial, không coi task build đã đạt.

## 5. P2 — ảnh web: bổ sung Extract thay vì đoán ảnh global

Adapter hiện có Search.include_images=true nhưng Extract.include_images=false.
Run chưa có candidate ảnh web đủ liên kết; chưa có bằng chứng để kết luận Tavily không hỗ trợ ảnh.

Kế hoạch:

1. Bổ sung diagnostics số ảnh trong Search global, Search từng result, Extract từng result,
   số candidate hợp lệ/bị loại và lý do; không log key hoặc toàn bộ payload nhạy cảm.
2. Tận dụng request Extract đang có với `include_images=true`, chuẩn hóa ảnh theo chính `results[i].url`.
   Không thêm Search/LLM call chỉ để lấy ảnh; kiểm schema thực tế bằng fake response trước.
3. Model chọn ID bằng tên/alt/caption/page metadata; ảnh thiếu mô tả hoặc liên kết thực thể phải abstain.
   Không suy ra caption đúng chỉ vì ảnh ở trang được cite.
4. Giữ allowlist, public-IP/TLS, byte/pixel/decode/hash, license unknown và timeout optional.
5. Test offline trước; khi được duyệt lượt thật mới kiểm provider, GET ảnh, mở ảnh và nhờ TV4 kiểm UI.

Tavily Extract có tham số include_images và danh sách images theo result trong
[tài liệu chính thức](https://docs.tavily.com/documentation/api-reference/endpoint/extract), đã kiểm ngày07/11/2026.
Đây là hướng triển khai đã có cơ sở contract, **chưa phải code được bổ sung hoặc ảnh thật đã test thành công**.
Provider có thể không trả ảnh; khi đó trả text bình thường và ghi lý do, không tạo association giả.

## 6. Ngân sách test mới đề xuất: tối đa8 user turns

**Chưa được cấp hoặc chạy trong tác vụ lập kế hoạch này.** Tách ba đợt có gate, không chạy cả8 nếu đợt trước lỗi.
Mọi clarification reply/retest đều tính lượt. Tối đa6 logical model calls/turn như hiện tại, không retry SDK ẩn.

| Lượt | Case | Cần kiểm |
|---|---|---|
| R1 | Hero80 / Great Stars / PvE một tay / không bonus | Constraint VI không bị dịch thành nguồn giả, query giữ điều kiện |
| R2 | Xin build nhưng chưa có class/level/weapon | Hỏi thêm tự nhiên, tối đa2 field, tạo pending ID |
| R3 | Trả lời bằng chat: Bandit50, Reduvia, PvE | Resume đúng task/ID, không lặp hỏi đã biết; không bắt key=value |
| R4 | Astrologer25, Moonveilll-X mod chưa có nguồn | Giữ tên/phủ định; không bịa requirements hoặc8 stats |
| B1 | Vagabond60 / Zweihander | Dữ liệu đầy đủ, checked allocation, nguồn/quote, phép tính độc lập |
| B2 | Bandit50 / Reduvia | Class/weapon khác, không hardcode; artifact nguyên vẹn |
| I1 | Arsenal Charm, web off | Ảnh local không trùng hash, text không phủ nhận khả năng gửi ảnh |
| I2 | Reduvia, web always | Ảnh web có association thực, tải/cache/GET và đúng thực thể |

Mỗi đợt dùng manifest/output mới và checkpoint từng lượt; không sửa manifest của run đã chạy.
Giữ test DB/memory riêng, corpus chỉ đọc, không reindex/tải model, không sửa .env thật khi chưa được yêu cầu.
Dùng CLI benchmark hiện có theo [hướng dẫn](api/evidence-media-build.md#tự-kiểm-thử).

## 7. P3 — giảm phụ thuộc API và chi phí

Run trước dùng220.307 prompt tokens cho39 calls; cần đo vị trí trùng text giữa candidate preview và top5 evidence.
Đây là dữ liệu đo của run cũ, chưa phải kết quả tối ưu.

- Loại phần preview trùng với full evidence đã cung cấp; giữ ID, nguồn và metadata điều kiện.
- Gửi bảng/schema đầy đủ khi cần trích số; không lặp toàn bộ artifact vào mọi observation.
- Cache/reuse factual build inputs đã có nguồn; giữ TTL/version/unknown, không dùng memory user làm game facts.
- Bước chọn ảnh dùng ngân sách còn lại, text không chờ ảnh quá deadline.
- Trước sửa lớn dùng fixture từ lỗi thật và test targeted; khi code ổn chạy full unit một lần.
- Benchmark thật theo các gate nhỏ; chưa chạy200 câu/ablation hay lặp toàn golden set để thử may rủi.

**Gate:** so sánh cùng case, tính số calls/tokens/latency và chất lượng evidence; không giảm token bằng cách làm mất
nguồn/điều kiện hoặc giảm validation. Không cam kết mức tiết kiệm khi chưa đo.

## 8. Điểm dừng và bàn giao sang phiên mới

- Lưu trạng thái, report và kế hoạch này trên nhánh hiện có. Không cần lặp lại915 tests chỉ vì thêm tài liệu.
- Người dùng review rồi quyết định commit/push/PR; trợ lý không tự làm. Không merge develop khi còn lỗi chặn demo.
- Phiên mới đọc các tài liệu được dẫn, kiểm Git rồi xử lý riêng P0; không đọc raw report lớn trừ đúng case cần chẩn đoán.
- Không cần tóm lại toàn bộ lịch sử chat hoặc khởi tạo lại dự án.

Prompt tiếp tục:

```text
Tiếp tục IndexBeast tại D:\Index-Beast, nhánh feature/s3-tv3-evidence-media-build.
Đọc docs/ke-hoach-on-dinh-indexbeast.md và handover được dẫn trong đó.
Giữ nguyên modified/untracked, không stash/reset/rebase, commit/push/merge.
Chỉ triển khai P0 và kiểm offline trước; chưa làm P1/P2/P3 cùng lúc.
Baseline gần nhất915 backend tests,41 web tests. Run10 lượt thật đã hết ngân sách,
có7 HTTP200 và3 HTTP502; các sửa sau run chưa retest API thật.
Không gọi DeepSeek/Tavily thật, không tải model/reindex hoặc sửa .env khi chưa có
ngân sách mới được tôi xác nhận. Không đổi assertion/approval để che lỗi.
Cập nhật trạng thái và handover bằng kết quả thực tế.
```
