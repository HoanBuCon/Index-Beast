# TV3 — Gỡ conflict rebase với develop

05/11/2026 · MinhMuc · nhánh `feature/s3-tv3-gameplay-clarification`.

## Trạng thái và phạm vi

Người dùng đã chạy rebase lên `origin/develop`, nền `b13f7b4618d864583012e93828e0c60e2baeb112`.
Git dừng khi replay commit `4d7c97d` (Add gameplay diagnostic review and offline guard testing),
không còn commit khác trong todo. Hai unmerged path: `docs/handover/README.md` và
`web/src/components/chat/MessageList.tsx`.

Giải quyết trên rebase đang có; không reset/stash/skip/abort hoặc thay đổi dữ liệu, cấu hình thật, backend hay report.
Các file đã stage bởi rebase được giữ nguyên. Thao tác kết thúc là `git rebase --continue`, giữ message/author
của commit người dùng; Git tạo hash mới khi replay. Không tạo commit tác vụ riêng, không push/force-push/merge.

## Quyết định gộp

- Giữ thay đổi TV4 từ `ce2379e` và `54ee25f`: không render SourceList hoặc FeedbackButtons dưới câu trả lời.
  “Bỏ câu hỏi” trong tên commit TV4 là bỏ câu hỏi đánh giá “Câu trả lời có hữu ích?”, không phải bỏ clarification.
- Giữ ClarificationForm, callback onClarification và các điều kiện chỉ hiển thị cho message cuối đã hoàn tất.
  Citation/popover, ảnh và Markdown an toàn giữ nguyên. Không khôi phục các import component TV4 đã bỏ.
- README handover được gộp đủ liên kết TV3/TV4. File làm việc lúc kiểm tra không còn marker nhưng đã mất
  các mục ở đầu; đã đối chiếu toàn bộ tập link với cả stage 2 và stage 3 của Git để tránh mất tài liệu.
- Bổ sung assertion vào test SSR clarification: MessageList có form và citation, không có panel nguồn/câu hỏi đánh giá.
  Giữ nguyên assertion cũ của cả hai phía.

## Kiểm tra thực tế trước khi tiếp tục rebase

- Web: **37/37 test đạt**, chạy `node --test --test-concurrency=1 --test-timeout=30000 tests/*.test.ts`.
- `npm run build`: TypeScript/Vite đạt; Prettier check cho hai file code/test chỉnh trong tác vụ đạt.
- Backend: **709 passed**, 1 Qdrant-memory warning, **22,01 giây**;
  `.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q` từ backend.
- `python -m scripts.export_openapi --check` dùng venv backend: đạt.
- Không còn conflict marker trong MessageList/handover; tập liên kết của cả hai stage được giữ.
  UTF-8 và diff được kiểm trước stage/continue.
- Không gọi DeepSeek/Tavily, embedding/index hoặc test server thật trong tác vụ Git này.

## Cách dùng sau gộp

Web giữ cách trình bày TV4 và có card hỏi thông tin bổ sung khi backend trả clarification.
Không cần index hoặc thay `.env`. Trạng thái nhánh sau rebase phải được xác minh bằng `git status` và
`git merge-base --is-ancestor origin/develop HEAD`; chỉ push khi người dùng yêu cầu.
Nếu nhánh đã từng push trước rebase, cần đối chiếu remote/upstream rồi mới chọn cách push phù hợp;
không tự force-push hoặc dùng Sync Changes trong tác vụ xử lý conflict.
