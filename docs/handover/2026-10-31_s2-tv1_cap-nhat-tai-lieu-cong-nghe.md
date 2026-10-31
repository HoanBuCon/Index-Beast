# Sprint 2 TV1: cập nhật tài liệu công nghệ theo code sau Sprint 2

| | |
|---|---|
| Ngày | 31/10/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `docs/s2-tv1-cap-nhat-cong-nghe` (từ `origin/develop` tại `9c2a8dc`, sau PR #48, #49) |

## Phạm vi

Đối chiếu `backend/requirements*.txt`, `constraints.txt`, `web/package.json`, `bot/package.json` và code đang chạy với tài liệu. Chỉ sửa tài liệu, không đổi code hay phiên bản.

## Đã cập nhật

- [`docs/01_TECHSTACK.md`](../01_TECHSTACK.md) lên v1.4:
  - **Thêm:** LangChain (`langchain-core` 1.7.1, `langchain-deepseek` 1.1.1) làm lớp điều phối LLM/RAG. Bản v1.3 ghi "Không dùng LangChain"; nay bỏ khỏi danh sách không dùng. LangSmith đi kèm nhưng luôn tắt tracing.
  - **Thêm:** Pillow 12.3.0, tokenizers 0.23.3, pre-commit 4.7.0, test JS bằng `node --test`.
  - **Thêm:** ba chế độ `CHAT_MODE`, bảo vệ API (rate-limit, service token, timeout), endpoint ảnh `/images/{id}`.
  - **Đánh dấu chưa triển khai:** reranker (`NoReranker`), web fallback DuckDuckGo (S4), cache Redis.
  - **Sửa theo thực tế:** prefetch 30 + 30 → RRF → tối đa 5 đoạn; chỉ index chunk tiếng Anh, rewrite/dịch truy vấn tắt mặc định.
  - Phạm vi base + Shadow of the Erdtree theo ngoại lệ ADR-004; ADR-003 đã dùng cho corpus S2.
  - Danh sách `requirements*.txt` khớp file thật; lệnh cài dùng `requirements-dev.txt`.
  - Ghi chú chạy 1 worker khi demo chế độ live vì hội thoại còn trong RAM.
- [`docs/04_ARCHITECTURE.md`](../04_ARCHITECTURE.md): phạm vi; cây thư mục thêm `core/corpus.py`, `api/errors.py`, `api/guard.py`, `services/{chat,mock_chat,factory,images}.py`, `rag/evidence.py`, `backend/scripts/`, các file mới của `eval/`; sửa tên `services/chat_service.py` thành `services/chat.py`.

## Không sửa

- `README.md` và `backend/app/rag/README.md`: TV3 đã cập nhật LangChain và phạm vi trong S2.
- `docs/02_SRS.md`, `docs/03_SPRINT_PLAN.md`: SRS đã có ghi chú ngoại lệ phạm vi; sprint plan sinh từ `planning/sprint_plan.json`.
- Bản Word trong `docs/export/` vẫn là snapshot cũ; cần sinh lại khi team xuất tài liệu.
- Hai thay đổi phạm vi (SotE, trợ lý gameplay/build) vẫn chờ chốt bằng CHANGE-REQ như báo cáo Sprint 2.

## Kiểm tra

- Mọi phiên bản trong tài liệu đã đối chiếu với `requirements*.txt`, `constraints.txt` và `package.json` trên `9c2a8dc`.
- Đã kiểm liên kết local trong handover này.
