# TV3 · Reranker chạy trên máy thay API Jina (24/11/2026)

Nhánh `feature/s5-tv3-reranker-cuc-bo` (từ `develop` sau PR #132), **chưa commit**.

## Vì sao

- Key Jina free đã hết token, không nạp thêm được. Trước khi hết, key còn bị giới hạn 100.000 token/phút: đo retrieval liên tục thì 63–82% lần gọi trả 429 và lặng lẽ giữ thứ tự RRF (đã thêm `TokenBudget` ở PR #132).
- Lần thử đầu với `jina-reranker-v2-base-multilingual` chạy trên máy làm **tràn RAM (~18 GB)**. Model không nặng (đo riêng ~2,5 GB), lỗi nằm ở code: khi một lượt quá giờ, luồng suy luận vẫn chạy ngầm nhưng khóa đã nhả, nên các lượt chồng lên nhau; thêm nữa là gửi cả 30 đoạn trong một lô. Bản đó đã bị gỡ khỏi nhánh.

## Đã làm

- `app/rag/reranker.py`: thêm `LocalReranker` (cross-encoder FastEmbed/ONNX, CPU) và `local_reranker(settings)`. Có chung giao diện `rank()` và cùng cách giữ RRF khi lỗi như `JinaReranker`, log cùng sự kiện `jina_reranker_outcome` với `provider="local"`.
  - **Chống chạy chồng:** cờ bận chỉ được trả khi worker thật sự xong (`finally` trong thread), kể cả khi lượt đó đã quá giờ. Lượt đến lúc đang bận thì giữ RRF ngay (`reason_category="busy"`), không xếp hàng.
  - Gửi vào model theo lô nhỏ (`batch_size` 8), mỗi đoạn tối đa 600 ký tự, tối đa 20 ứng viên.
  - Model nạp lười; `app/main.py` gọi `warm()` ở nền lúc khởi động. Chưa nạp xong thì lượt đó quá giờ và giữ RRF.
  - Tách `_document()` dùng chung cho Jina và bản chạy trên máy.
- `core/config.py`, `.env.example`:
  - Chọn kiểu reranker bằng `RAG_RERANKER_PROVIDER=jina|local`. Mặc định là `jina` để không đổi hành vi cũ.
  - `local` không cần key.
  - Các biến cấu hình: `RAG_RERANKER_LOCAL_MODEL` (mặc định `Xenova/ms-marco-MiniLM-L-12-v2`), `_THREADS` 2, `_MAX_CANDIDATES` 20, `_MAX_CHARS` 600, `_BATCH_SIZE` 8.
- `app/context.py`: tạo `LocalReranker` khi provider là `local`.
- `eval/measure_retrieval.py`: `--rerank` dùng được kiểu reranker đang cấu hình, và báo cáo ghi đúng tên model.
- Test: thêm 4 test (xếp theo điểm và cắt đoạn; lỗi model hoặc điểm NaN thì giữ RRF; **regression quá giờ không cho chạy chồng**; `local` không cần key). Unit **952 passed**, 20 skipped; ruff đạt.

## Số đo (24/11, máy Ryzen 7 5800H, chỉ CPU)

Retrieval 183 câu có nguồn, câu hỏi nguyên văn, top 20 ứng viên RRF:

| Cấu hình | Recall@5 | MRR@5 | Thời gian mỗi truy vấn | RAM process |
|---|---:|---:|---:|---:|
| Hybrid RRF | 83,1% | 0,701 | — | ~0,9 GB |
| MiniLM-L6 (80 MB) | 85,3% | 0,733 | 0,40 s (tối đa 0,63 s) | 1,19 GB |
| **MiniLM-L12 (120 MB), mặc định** | **86,6%** | **0,738** | 0,75 s (tối đa 1,18 s) | 1,27 GB |
| API Jina v2, chạy đủ (lượt đo trước) | 90,7% | 0,789 | ~0,35 s mỗi lần gọi | — |

- Tách theo ngôn ngữ (L12): EN 92,8% / 0,825; VI 81,1% / 0,661. Với RRF: EN 92,4% / 0,799; VI 74,7% / 0,613.
- Đã thử trộn hạng RRF với hạng của reranker: L12 lên được 87,4–87,9%. Tuy vậy mức hơn chỉ khoảng 1 điểm, và tham số được dò trên chính golden set nên dễ là ăn may. **Không đưa vào code.**
- Test nhẹ trên app thật: 3 câu (IB-GS-101, 150, 230), web off, DeepSeek thật. 3/3 grounded, reranker chạy được ở cả 6/6 lượt, không lỗi nạp model.
- Lượt đo có canh RAM (tự thoát khi process vượt 3 GB): RAM đỉnh 1,13–1,27 GB.

## Chốt model: MiniLM-L12 (MinhMuc duyệt 24/11)

Đo thêm sau khi viết bản đầu handover này: đủ 183 câu, chạy qua `LocalReranker`, có canh RAM 4 GB. Kết quả lưu ở `docs/testing/2026-11-24_golden-200-ablation/retrieval/hybrid-local-*.json`.

| Model | Recall@5 | MRR@5 | EN | VI | Thời gian mỗi lượt tìm | RAM đỉnh |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid RRF | 83,1% | 0,701 | 92,4% / 0,799 | 74,7% / 0,613 | ~0,05 s | ~0,9 GB |
| `jinaai/jina-reranker-v1-turbo-en` | 82,6% | 0,698 | 90,3% / 0,815 | 75,8% / 0,593 | TB 0,57 s | 1,24 GB |
| **`Xenova/ms-marco-MiniLM-L-12-v2`** | **86,6%** | **0,739** | **92,8% / 0,827** | **81,1% / 0,661** | TB 1,03 s, p95 1,45 s, chậm nhất 2,9 s | 1,20 GB |
| `jina-reranker-v2-base-multilingual` chạy trên máy (chỉ 12 câu) | 91,7% trên 12 câu (= API) | 0,792 | | | TB 3,2 s | 2,52 GB |

- Chọn L12: là model chạy trên máy duy nhất vừa tốt hơn RRF rõ ràng, vừa chạy được trên CPU. turbo-en không hơn RRF; Jina v2 chạy trên máy quá chậm và giấy phép chỉ phi thương mại.
- Số 0,75 s trước đây là thời gian chấm điểm thuần trong script thí nghiệm. Qua app, mỗi lượt tìm trung bình 1,03 s. Lượt chậm nhất 2,9 s, sát giới hạn 3 s; vượt thì giữ thứ tự RRF.
- Đã xóa model không dùng: Jina v2 (2 bản, ~2,2 GB, gồm bản tải nhầm vào `models/fastembed`), turbo-en, MiniLM-L6. Thư mục model thật là `models/notebook-fastembed` (theo `.env`), giờ còn E5, BM25, L12, tổng 610 MB.
- Lưu ý khi đo: lượt 12 câu từng cho thấy turbo-en khá, nhưng đủ 183 câu thì không hơn RRF. Đừng chọn model dựa trên mẫu nhỏ.

## Dọn code chết và cập nhật `.env.example` (24/11, MinhMuc yêu cầu rà cả backend)

Cách rà: script quét AST tìm hàm, lớp và hằng số không được nhắc ở đâu khác (kể cả `docs/`), module không ai import, và import trỏ tới tên đã mất (không còn import hỏng nào). Mục do framework gọi ngầm thì giữ: route FastAPI, validator pydantic, `HTMLParser.handle_data`, method LangChain, lớp Locust.

- **Đã xóa:**
  - `app/services/feedback_service.py`: file chỉ có docstring, việc thật nằm ở `MemoryRepository.save_feedback`.
  - `ingest/index/embedder.py`: file chỉ có docstring.
  - `ingest/indexing.rejection_reason`: "compatibility entry point" không còn ai gọi.
  - `scripts/extend_golden_s3.py`: script chạy một lần để nối dữ liệu S3, đã chạy xong. Chạy lại sẽ nối trùng vào `golden_set_s3.jsonl`; lịch sử vẫn còn trong git.
- **Reranker:**
  - Đổi sự kiện log `jina_reranker_outcome` thành **`reranker_outcome`** (msg `Reranker outcome`), vì giờ dùng chung cho cả Jina và model chạy trên máy. Đã sửa nơi đọc: `eval/measure_retrieval.py`, `scripts/run_live_manifest.py`, test. Sự kiện `jina_reranker_attempt` giữ nguyên vì chỉ API Jina phát ra.
  - `_BudgetRefused` đổi thành `_SkipRerank`, vì dùng cho cả hai trường hợp: hết hạn mức Jina và model chạy trên máy đang bận.
- **Giữ đường API Jina** (MinhMuc chọn): `JinaReranker`, `TokenBudget`, `--throttle`, `JINA_API_KEY`, để còn dùng lại khi có key mới và tái lập được số đo.
- **`.env.example`:**
  - Gom phần reranker thành 3 khối: chung, chạy trên máy, API Jina.
  - **Bật mặc định `RAG_RERANKER_ENABLED=true`, `RAG_RERANKER_PROVIDER=local`** (MiniLM-L12).
  - Ghi chú dùng số đo qua app: ~1 s mỗi lượt tìm, RAM ~1,2 GB.
  - Code vẫn mặc định `enabled=false` / `provider=jina` khi không có `.env`.
- **Để thành viên khác duyệt, không tự xóa** (thuộc pipeline TV1/TV2, như quy ước GĐ2):
  - Trong `core/db/repositories.py`, các hàm `create_conversation`, `add_message`, `recent_messages`, `message_exists`, `add_feedback` chỉ có test gọi.
  - Model `core/db/models.Entity` không ai dùng.
  - Script `ingest/debug/*`, `scripts/audit_images.py`, `scripts/llm_smoke.py` vẫn được handover hướng dẫn chạy, nên giữ.
- Unit 952 passed, ruff và pre-commit đạt. Hook end-of-file từng tự sửa 2 handover TV4 (14/11); mình đã hoàn tác để không đụng file người khác.

## Chưa làm

- Chưa chạy lại 9 cấu hình trọn luồng với reranker chạy trên máy, chưa chấm judge.
- Các lượt trọn luồng cũ còn thiếu:
  - Hybrid ± Jina với web always, E5-only tối thiểu, E5 + Jina, BM25 + Jina: đã xóa vì DeepSeek trả 402.
  - Judge của `hybrid-jina-off` còn 129 câu lỗi.
- Kết quả trọn luồng hợp lệ hiện có (web auto):

  | Cấu hình | Đúng hoàn toàn |
  |---|---:|
  | Hybrid + Jina | 97,8% |
  | Hybrid RRF | 95,6% |

- Chưa viết báo cáo `docs/testing/2026-11-24_golden-200-ablation/README.md`.
- ~~Bật thật trong `.env`~~: đã làm 24/11 theo yêu cầu MinhMuc. Thêm `RAG_RERANKER_PROVIDER=local` và khối `RAG_RERANKER_LOCAL_*`; `RAG_RERANKER_ENABLED=true` có sẵn. Trước đó `.env` bật reranker nhưng provider vẫn là `jina` với key đã hết token, nên mỗi lần tìm đều gọi API vô ích. Bản sao `.env` cũ nằm trong scratchpad của phiên.
- Test hệ thống 24/11, 3 câu thật, web auto, Postgres, L12 chạy trên máy:
  - IB-GS-235 (VI, gõ sai, hard): đúng, grounded, 15,5 s.
  - IB-GS-228 (EN, multi-hop, hard): đúng ý chính, grounded, 8,2 s. Thiếu chi tiết "đỉnh tháp sau Commander Niall"; bước 3 diễn đạt đường đi hơi lẫn.
  - IB-GS-267 (ngoài phạm vi): từ chối đúng, 1,4 s.
  - Reranker ok 4/4 lượt, không lỗi ERROR trong log.
- `models/fastembed` còn bản `jina-reranker-v2-base-multilingual` (~1,1 GB) từ lần thử đầu, nay không dùng. Có thể xóa tay để lấy lại dung lượng.
