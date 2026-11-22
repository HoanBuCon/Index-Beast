# Golden 200 · Ablation retrieval, reranker, web (24/11/2026)

> **Đã xong.** Đủ 9 cấu hình đổi từng trục với reranker L12 chạy trên máy, cộng 2 lượt API Jina làm số tham khảo. Không lượt nào bị bỏ vì thiếu ngân sách.

## Kết luận nhanh

- **Mọi cấu hình đều ở mức 95–98% câu đúng hoàn toàn.** Mỗi câu factual bằng khoảng 0,55 điểm phần trăm. Cấu hình tốt nhất và kém nhất chỉ cách nhau 5 câu trên 183, nên **phần lớn khác biệt nằm trong nhiễu**.
- **Reranker L12 giúp retrieval rõ hơn cả.**
  - Hybrid RRF + L12 tăng Recall@5 từ 83,1% lên 86,6% và MRR từ 0,706 lên 0,739.
  - Mức này đạt khoảng một nửa mức tăng của API Jina (Recall@5 90,7%, MRR 0,789), mà không tốn tiền API.
  - Ở trọn luồng, L12 tăng độ đúng 1–2 điểm so với RRF, ở cả web off lẫn web auto. Đổi lại p50 chậm thêm khoảng 1,5 s.
- **Web always không đáng bật mặc định.**
  - Độ đúng không tăng.
  - p50 tăng gấp đôi, từ khoảng 6 s lên 12–15 s.
  - Chi phí và token tăng khoảng 50%.
  - Mỗi câu gọi Tavily khoảng 1 lần, tức khoảng 190 lần mỗi lượt.
  - Có 1 câu bị lỗi 502; xem mục "Lỗi phát hiện khi chấm".
  - Faithfulness không tụt, vẫn ở mức 98–99%.
- **Faithfulness 2 của mọi lượt nằm trong khoảng 96–99,5%.** Bản báo cáo trước ghi 80–92% là do lỗi chấm; xem mục "Đính chính".
- **Cấu hình mặc định giữ nguyên là Hybrid RRF + L12 + web auto.** Cấu hình này có độ đúng cao nhất (97,8%) và độ trễ chấp nhận được.

## Mục tiêu

Đổi từng trục một trên golden 200 câu (`manifest.json`) để biết mỗi thành phần đóng góp bao nhiêu:

- **Retrieval:** dense E5, BM25, hybrid RRF.
- **Reranker:** không dùng, MiniLM-L12 chạy trên máy, API Jina v2 (số tham khảo).
- **Web:** off, auto, always.

Key API Jina đã hết token, nên bộ đo dùng reranker `Xenova/ms-marco-MiniLM-L-12-v2` chạy trên máy, chỉ CPU. Lý do chọn model này nằm trong `docs/handover/2026-11-24_s5-tv3_reranker-cuc-bo.md`.

## Cách đo

- **App:** `deepseek-flash`.
  - `.env`: `RAG_THINKING_ENABLED=true`, agent thinking `false`.
  - `CHAT_PERSISTENCE=memory`, `RATE_LIMIT_PER_MINUTE=1000`.
- **Chạy tuần tự từng lượt.** Mỗi lượt 200 câu bằng `scripts.run_live_manifest --resume`, và mỗi lượt gửi lần lượt từng câu.
  - Không chạy song song vì các bản L12 sẽ tranh CPU, vượt giới hạn 3 s rồi rơi về RRF, làm sai số đo.
- **Người chấm là Claude (Claude Code), không gọi DeepSeek.** Chấm theo rubric S4:
  - Correctness và faithfulness, mỗi mục 0/1/2.
  - Behavior pass/fail cho câu ngoài phạm vi và câu thiếu dữ kiện.
  - Followup 0/1/2.
  - Quy ước chi tiết ở `judge/quy-uoc-cham.md`. Cả 4 lượt cũ cũng được chấm lại để dùng chung một thước đo.
- **Độ tin của người chấm:** trên `hybrid-norerank-auto`, Claude và judge v4-pro cũ khớp correctness 181/183 câu, và cùng ra độ đúng 95,6%. Điểm v4-pro cũ lưu ở `judge/*.v4pro.jsonl`.

### Chi phí DeepSeek

Chi phí lấy từ số dư `GET /user/balance` trước và sau mỗi lượt.

| Lượt | Số dư sau lượt | Chi phí |
|---|---:|---:|
| (đầu) | 4,96 USD | |
| `hybrid-l12-auto` | 4,72 | 0,24 |
| `hybrid-l12-off` | 4,48 | 0,24 |
| `dense-norerank-off` | 4,20 | 0,28 |
| `dense-l12-auto` | 3,98 | 0,22 |
| `bm25-l12-auto` | 3,74 | 0,24 |
| `hybrid-l12-always` | 3,39 | 0,35 |
| `hybrid-norerank-always` | 3,05 | 0,34 |

- Tổng chi cho 7 lượt mới là 1,91 USD.
- Các lượt web always tốn thêm khoảng 0,1 USD vì mỗi câu dùng nhiều token hơn (khoảng 34,5 nghìn so với 22 nghìn).
- Ở `dense-norerank-off`, khoản 0,28 USD có thể gồm cả lần chạy dở trước khi phiên bị ngắt, nên số này có thể cao hơn chi phí thật của lượt.

## Retrieval (183 câu có nguồn, câu hỏi nguyên văn)

Số đo nằm trong `retrieval/*.json`. Mỗi câu lấy 5 trang khác nhau đứng đầu và so với các trang nguồn đã gắn nhãn (gold).

- **Precision@5:** số trang gold trong top 5, chia cho 5. Phần lớn câu chỉ có 1–2 trang gold, nên trần thực tế của P@5 là khoảng 0,2–0,4. Chỉ nên dùng P@5 để so các cấu hình với nhau, không đọc như một tỉ lệ tuyệt đối.
- **Recall@5:** tỉ lệ trang gold nằm trong top 5.
- **Hit@5:** có ít nhất một trang gold trong top 5.
- **MRR@5:** trung bình của 1/hạng của trang gold đầu tiên.

| Retrieval | Reranker | P@5 | Recall@5 | Hit@5 | MRR@5 | Thời gian mỗi truy vấn |
|---|---|---:|---:|---:|---:|---:|
| Dense E5 | — | 0,189 | 81,1% | 85,2% | 0,714 | 38 ms |
| Dense E5 | MiniLM-L12 | 0,201 | 85,5% | 90,2% | 0,733 | 0,74 s |
| Dense E5 | API Jina v2 (tham khảo) | 0,208 | 87,7% | 91,8% | 0,769 | 2,0 s |
| BM25 | — | 0,183 | 78,6% | 82,5% | 0,584 | 37 ms |
| BM25 | MiniLM-L12 | 0,192 | 82,5% | 88,0% | 0,718 | 0,75 s |
| BM25 | API Jina v2 (tham khảo) | 0,210 | 88,3% | 91,8% | 0,763 | 2,3 s |
| Hybrid RRF | — | 0,195 | 83,1% | 87,4% | 0,706 | 67 ms |
| **Hybrid RRF** | **MiniLM-L12 (mặc định)** | **0,203** | **86,6%** | **90,7%** | **0,739** | 1,0 s |
| Hybrid RRF | `jina-reranker-v1-turbo-en` chạy trên máy (đã loại) | 0,192 | 82,6% | 87,4% | 0,698 | 0,57 s |
| Hybrid RRF | API Jina v2 (tham khảo) | 0,215 | 90,7% | 94,0% | 0,789 | 2,0 s |

Nhận xét:

- L12 giúp mọi kiểu retrieval. Mức tăng lớn nhất là ở BM25: MRR tăng từ 0,584 lên 0,718, vì BM25 xếp hạng kém nhưng vẫn kéo được đúng trang vào top 30.
- Hybrid + L12 vẫn là tổ hợp tốt nhất trong các tổ hợp không gọi API.
- Thời gian của các lượt API Jina có cả thời gian chờ hạn mức (`--throttle`), nên không phản ánh độ trễ thật. Mỗi lần gọi API thật mất khoảng 0,35 s.
- Precision@5 của các file cũ được tính lại từ `rows` có sẵn trong từng file sau khi bổ sung chỉ số này vào `eval/measure_retrieval.py`; không đo lại. Recall và MRR giữ nguyên, có kiểm bằng assert.
- Ở BM25 + L12, có 3 câu (IB-GS-105, 167, 251) mà BM25 chỉ trả về 1 trang, nên không cần gọi rerank. Vì vậy `rerank_outcomes` ghi 180/183.

## Trọn luồng (200 câu)

- **Đúng hoàn toàn (accuracy):** tỉ lệ câu factual (183 câu) được correctness 2.
- **Faithfulness 2:** câu trả lời bám sát nguồn đã trích.
- **Behavior pass:** chỉ tính 17 câu ngoài phạm vi và câu thiếu dữ kiện, nên mỗi câu bằng khoảng 5,9 điểm.
- **Trích đúng nguồn gold:** câu trả lời có trích ít nhất một trang gold.
- **Reranker ok:** trước đây tên trường trong `summary.json` là `jina_ok_pct`. Nay đổi thành `reranker_ok_pct` vì dùng chung cho mọi loại reranker.

| Cấu hình | Đúng hoàn toàn | Faithfulness 2 | Behavior pass | Trích đúng nguồn gold | p50 / p95 câu đầu | Reranker ok |
|---|---:|---:|---:|---:|---:|---:|
| Dense E5, không rerank, web off (mốc tối thiểu) | 95,6% | 96,7% | 70,6% | 95,1% | 4,5 / 10,7 s | — |
| Dense E5 + L12, web auto | 97,3% | 97,8% | 76,5% | 95,6% | 7,3 / 18,7 s | 100% |
| BM25 + L12, web auto | 96,2% | 98,4% | 70,6% | 94,5% | 7,8 / 19,6 s | 100% |
| Hybrid RRF, web off | 95,1% | 97,8% | 70,6% | 95,1% | 5,0 / 12,8 s | — |
| Hybrid RRF, web auto | 95,6% | 97,8% | 70,6% | 92,9% | 5,2 / 10,9 s | — |
| Hybrid RRF, web always | 96,7% | 99,5% | 70,6% | 94,5% | 11,7 / 18,7 s | — |
| Hybrid + L12, web off | 96,7% | 98,4% | 70,6% | 96,7% | 6,6 / 15,0 s | 100% |
| **Hybrid + L12, web auto (mặc định)** | **97,8%** | 96,2% | 70,6% | 95,1% | 6,6 / 15,1 s | 99,8% |
| Hybrid + L12, web always | 96,7% | 98,4% | 70,6% | 95,1% | 14,6 / 25,7 s | 100% |
| Hybrid + API Jina, web off (tham khảo) | 96,2% | 98,4% | 76,5% | 95,1% | 5,9 / 14,0 s | 100% |
| Hybrid + API Jina, web auto (tham khảo) | 96,7% | 97,3% | 70,6% | 95,6% | 6,0 / 13,1 s | 100% |

- Mọi lượt đều có 200/200 câu trả về, và không có lỗi 402.
- Riêng hai lượt web always có 1 câu lỗi HTTP 502, đều là **IB-GS-300**:
  - Cả lần sinh đầu và lần thử lại đều không qua bước kiểm trích dẫn, nên ứng dụng trả về `upstream_error`. Chi tiết ở mục "Lỗi phát hiện khi chấm".
  - Câu này được chấm 0/0, nên `ok_pct` của hai lượt là 99,5%.
  - Lỗi lặp lại ở đúng câu này trên cả hai lượt, nên đây là lỗi có thể tái hiện chứ không phải lỗi mạng ngẫu nhiên.
- Hai lượt web always kết thúc vòng lặp agent sớm (`forced_finish`) nhiều hơn hẳn: 18 câu ở Hybrid + L12 và 22 câu ở Hybrid RRF. Ở các lượt khác, con số này là 0–1 câu.

### Theo độ khó và theo câu gõ sai (đúng hoàn toàn)

Bảng dưới có 55 câu dễ, 83 câu vừa, 45 câu khó, 49 câu gõ sai và 134 câu gõ đúng, chỉ tính câu factual.

| Cấu hình | Dễ | Vừa | Khó | Gõ sai | Gõ đúng |
|---|---:|---:|---:|---:|---:|
| `dense-norerank-off` | 94,5% | 98,8% | 91,1% | 98,0% | 94,8% |
| `dense-l12-auto` | 96,4% | 98,8% | 95,6% | 98,0% | 97,0% |
| `bm25-l12-auto` | 96,4% | 97,6% | 93,3% | 95,9% | 96,3% |
| `hybrid-norerank-off` | 92,7% | 98,8% | 91,1% | 95,9% | 94,8% |
| `hybrid-norerank-auto` | 94,5% | 98,8% | 91,1% | 98,0% | 94,8% |
| `hybrid-norerank-always` | 98,2% | 98,8% | 91,1% | 98,0% | 96,3% |
| `hybrid-l12-off` | 94,5% | 100,0% | 93,3% | 98,0% | 96,3% |
| `hybrid-l12-auto` | 96,4% | 98,8% | **97,8%** | 98,0% | 97,8% |
| `hybrid-l12-always` | 98,2% | 98,8% | 91,1% | 98,0% | 96,3% |
| `hybrid-jina-off` | 94,5% | 98,8% | 93,3% | 93,9% | 97,0% |
| `hybrid-jina-auto` | 96,4% | 98,8% | 93,3% | 95,9% | 97,0% |

- **Câu khó là nơi reranker có tác dụng rõ nhất.** Mọi lượt không reranker đều đúng 91,1%. Các lượt có reranker ở web off và web auto đạt 93,3–97,8%. Riêng Hybrid + L12 + web always tụt lại 91,1%.
- **Câu gõ sai không còn là điểm yếu.** Hầu hết cấu hình đạt khoảng 96–98% ở nhóm này.
- **Ở câu dễ, web always cao nhất (98,2%).** Mức chênh chỉ 1–2 câu trên 55, nên chưa đủ để kết luận.

### Mức dùng công cụ và token

| Cấu hình | Web/câu | Corpus/câu | Token/câu | forced_finish | >45 s |
|---|---:|---:|---:|---:|---:|
| `dense-norerank-off` | 0 | 2,08 | 19.394 | 1 | 0 |
| `dense-l12-auto` | 0,01 | 2,20 | 21.683 | 0 | 0 |
| `bm25-l12-auto` | 0,02 | 2,25 | 21.558 | 0 | 0 |
| `hybrid-norerank-off` | 0 | 2,06 | 19.724 | 0 | 0 |
| `hybrid-norerank-auto` | 0,01 | 2,23 | 22.275 | 0 | 0 |
| `hybrid-norerank-always` | 0,96 | 2,06 | 34.935 | 22 | 0 |
| `hybrid-l12-off` | 0 | 2,06 | 19.210 | 0 | 0 |
| `hybrid-l12-auto` | 0,01 | 2,23 | 22.074 | 1 | 0 |
| `hybrid-l12-always` | 0,96 | 2,02 | 34.361 | 18 | 0 |
| `hybrid-jina-off` | 0 | 2,03 | 19.088 | 0 | 0 |
| `hybrid-jina-auto` | 0 | 2,13 | 21.131 | 0 | 0 |

Ở chế độ web auto, agent gần như không gọi web: khoảng 1 lần trên 100 câu. Corpus đã đủ cho golden 200, nên kết quả web auto rất gần web off.

## Lỗi phát hiện khi chấm

### Đính chính: "trích số nguồn không tồn tại" là lỗi của script chấm, không phải lỗi app

- **App làm đúng.**
  - `validate_answer` (`app/rag/generator.py`) chỉ trả về các nguồn được trích, và mỗi nguồn giữ số gốc trong `source.index`.
  - Ví dụ ở IB-GS-203, nguồn trả về có index 1, 2 và 4, và câu trả lời trích `[4]` đúng nguồn Twin Axes.
  - Web (`MessageList.tsx`, `SourceList.tsx`) và bot (`format.ts`) đều ghép `[n]` theo `source.index`.
  - Đếm lại trên cả 11 lượt bằng `source.index`: **0 câu trích số không có thật**.
- **Script chấm làm sai.**
  - Gói chấm (`packets.py`, script trong scratchpad, không nằm trong repo) đánh số lại nguồn theo vị trí 1, 2, 3.
  - Vì vậy những câu có danh sách nguồn bị hở số trông như trích `[4]` khi chỉ có 3 nguồn.
  - Mỗi lượt có 11–37 câu như vậy. Lượt web always có nhiều hơn vì có nhiều nguồn hơn nên dễ hở số.
- **Đã sửa điểm.**
  - Trả 175 câu về faithfulness 2. 5 câu vẫn giữ faithfulness 1 vì còn lỗi bám nguồn khác.
  - Correctness không đổi, nên độ đúng hoàn toàn không đổi.
  - Bản sao lưu điểm trước khi sửa nằm ở scratchpad phiên. Quy ước mới ghi ở `judge/quy-uoc-cham.md`.
- **Hệ quả: kết luận cũ "web always làm tụt faithfulness" là sai.** Sau khi sửa, faithfulness của hai lượt web always là 98,4% và 99,5%.
- Số trích hở (ví dụ 1, 2, 4) chỉ là chuyện hiển thị, không làm sai nội dung. Có thể cân nhắc đánh lại số liền mạch, nhưng không bắt buộc.

### IB-GS-300 trả HTTP 502 khi bật web always

- **Câu hỏi:** Samurai có dùng được Carian Slicer mà không tăng Intelligence không, và mở khóa phép thế nào?
- Với web off và web auto, câu này trả lời đúng.
- Với web always, cả hai lượt (L12 và RRF) đều trả 502 `upstream_error`, kèm thông báo "Câu trả lời RAG thiếu bằng chứng hoặc trích dẫn không hợp lệ".
- **Diễn biến trong log:**
  - `hybrid-l12-always`: lần đầu lỗi `unknown_evidence_index`, thử lại 1 lần vẫn `unknown_evidence_index`, rồi dừng.
  - `hybrid-norerank-always`: lần đầu lỗi `insufficient_with_citations`, nghĩa là model vừa báo thiếu dữ kiện vừa gắn trích dẫn. Lần thử lại lỗi `unknown_evidence_index`.
- **Nghĩa của `unknown_evidence_index`:** model đưa một mục `evidence` có `index` lớn hơn số đoạn context đã chọn (`len(prepared.hits)`). Validator từ chối, và chỉ được thử lại 1 lần (`format_retries` chỉ nhận 0 hoặc 1).
- **Chưa rõ nguyên nhân gốc.**
  - Có lẽ khi bật web always, context có thêm các đoạn web, và model đánh số evidence theo một danh sách khác với danh sách server đã chọn.
  - Cần lấy prompt và context của câu này để kiểm. Code không log nội dung model, nên không thể xem lại từ log.
- **Tác động:** người dùng nhận lỗi thay vì câu trả lời. Ở golden 200, lỗi chỉ gặp ở 1/200 câu và chỉ khi bật web always. Web always không phải chế độ mặc định.
- **Hướng sửa** (nhánh riêng):
  1. Tái hiện câu này với web always và ghi lại context đã đánh số.
  2. Nếu lỗi do lệch số giữa web và corpus, sửa cách đánh số hoặc ghi rõ phạm vi số trong prompt.
  3. Cân nhắc khi hết lượt thử lại thì trả câu "thiếu dữ kiện" thay vì 502.

### Câu thiếu dữ kiện

- Tỉ lệ pass dao động 70,6–76,5%, tức chỉ khác nhau 1 câu trên 17.
- Gần như lượt nào cũng fail cùng một nhóm câu. Bảng dưới đếm số lượt fail trên 11 lượt, và ví dụ lấy từ `hybrid-norerank-always`.
- Lúc đầu IB-GS-278 ở lượt này bị chấm pass, lệch với 10 lượt còn lại. Đã sửa thành fail cho thống nhất.

| Câu | Câu hỏi (rút gọn) | Số lượt fail | Model làm gì |
|---|---|---:|---|
| IB-GS-299 | "Vừa có remembrance đầu tiên, bước tiếp của quest NPC đó?" | 11/11 | Mặc định là Remembrance of the Grafted, bảo tới gặp Enia |
| IB-GS-278 | "Talisman rồng bản cộng đó tăng bao nhiêu kháng?" | 11/11 | Tự cho là dòng Dragoncrest (kháng vật lý), rồi liệt kê các bậc +1, +2. Không hỏi là dòng drake nào (lửa, sét, phép, thánh...) |
| IB-GS-279 | "Hiệp sĩ ở Roundtable Hold, quest dẫn đi đâu?" | 10/11 | Mặc định là Gideon Ofnir |
| IB-GS-294 | "Rìu của kỵ sĩ chết và viên crystal tear xanh?" | 10/11 | Liệt kê đủ hai cây rìu, nhưng tự chọn Greenspill cho viên tear |
| IB-GS-277 | "Sau tiếng báo Great Rune vỡ trong DLC, gặp lại hiệp sĩ ở chỗ thánh giá?" | 9/11 | Mặc định là Ansbach ở Main Gate Cross |
| IB-GS-292 | "Vừa đánh xong một boss DLC, đi màn sương phía bắc?" | 2/11 | Thường hỏi lại đúng |

- **Kiểu lỗi chung:** câu hỏi có một tham chiếu mơ hồ ("hiệp sĩ đó", "bản cộng đó", "remembrance đầu tiên"). Retrieval tìm được một ứng viên có vẻ hợp, và model trả lời luôn, có trích dẫn, thay vì hỏi lại hoặc nêu các khả năng có điều kiện.
- Theo quy ước chấm, chỉ đưa một khả năng là fail, còn liệt kê có điều kiện từ 2 khả năng trở lên là pass.
- Đổi retrieval, reranker hay web không giúp được. Đây là việc của prompt hoặc agent: cần nhận ra tham chiếu mơ hồ và hỏi lại, hoặc liệt kê các khả năng.
- Câu trả lời của model không bịa. Nội dung đúng với giả thuyết nó chọn, nên correctness và faithfulness không bị ảnh hưởng. Lỗi nằm ở hành vi.

## Tái lập

Chạy từ `backend/`:

```
CHAT_PERSISTENCE=memory RATE_LIMIT_PER_MINUTE=1000 RAG_RETRIEVAL_MODE=<hybrid|dense|bm25> RAG_RERANKER_ENABLED=<true|false> RAG_RERANKER_PROVIDER=local .venv/Scripts/python.exe -X utf8 -m scripts.run_live_manifest ../docs/testing/2026-11-24_golden-200-ablation/manifest.json data/research_runs/2026-11-24-ablation/<tên> --web <off|auto|always> --resume
RAG_RERANKER_PROVIDER=local .venv/Scripts/python.exe -X utf8 -m eval.measure_retrieval --manifest ../docs/testing/2026-11-24_golden-200-ablation/manifest.json --output <file mới>.json --mode <hybrid|dense|bm25> --rerank
.venv/Scripts/python.exe -X utf8 -m eval.summarize_ablation --manifest ../docs/testing/2026-11-24_golden-200-ablation/manifest.json --runs data/research_runs/2026-11-24-ablation --output ../docs/testing/2026-11-24_golden-200-ablation/summary.json
```

- Kết quả thô của từng lượt (`results.json`, khoảng 1,4 MB mỗi lượt) nằm trong `backend/data/research_runs/2026-11-24-ablation/`. Thư mục này bị gitignore.
- Điểm chấm được chép sang `judge/<lượt>.jsonl`.
- Để `eval.summarize_ablation` ra đúng số, mỗi thư mục lượt cần có `judge.jsonl` cạnh `results.json`. Có thể chép ngược từ `judge/` vào.
