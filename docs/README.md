# Tài liệu Dự án IndexBeast (`docs/`)

Thư mục này chứa toàn bộ tài liệu đặc tả, kiến trúc, kế hoạch sprint, quyết định kỹ thuật và quy ước phát triển của dự án **IndexBeast** (nhóm **4 Hollows**).

| Mã | Thành viên |
|---|---|
| TV1 | Hoanbucon |
| TV2 | UncleThing |
| TV3 | MinhMuc |
| TV4 | QuyVuiVe |

---

## 1. Danh mục tài liệu

| Tập tin | Vai trò & Nội dung chính | Trạng thái / Chỉnh sửa |
|---|---|---|
| [`01_TECHSTACK.md`](01_TECHSTACK.md) | Công nghệ & phiên bản chốt (FastAPI, Qdrant, DeepSeek, e5-small, PostgreSQL, Redis, React, Discord.js). | Soạn thảo thủ công |
| [`02_SRS.md`](02_SRS.md) | Đặc tả yêu cầu phần mềm dạng Living SRS (ID yêu cầu cố định, độ ưu tiên MoSCoW, trạng thái vòng đời). | Cập nhật cuối mỗi Sprint Review |
| [`03_SPRINT_PLAN.md`](03_SPRINT_PLAN.md) | Kế hoạch chi tiết 6 Sprint (19/10/2026 – 29/11/2026), phân vai TV1–TV4 và bảng phân bổ công việc. | **Sinh tự động** từ `planning/sprint_plan.json` (Không sửa tay) |
| [`04_ARCHITECTURE.md`](04_ARCHITECTURE.md) | Kiến trúc thư mục, quy tắc phụ thuộc và luồng pipeline dữ liệu (offline & online). | Soạn thảo thủ công |
| [`rag-diagram.md`](rag-diagram.md) | Sơ đồ RAG online bằng Mermaid `flowchart TD`, bắt đầu từ kho tri thức đã có. | Soạn thảo thủ công |
| [`quy_uoc.md`](quy_uoc.md) | Quy ước Git flow (nhánh `feature/`, `release/`, `hotfix/`), Conventional Commits và quy định Mentor review (`@HoanBuCon`). | Soạn thảo thủ công |
| [`handover/`](handover/) | Tài liệu bàn giao sau mỗi nhóm task: quy tắc, quy ước, cách dùng, sự cố và việc còn lại. Đặt tên `<YYYY-MM-DD>_s<sprint>-tv<n>_<chu-de>.md`. | Người làm task viết, review cùng PR |
| [`adr/`](adr/) | Các bản ghi quyết định kiến trúc (Architecture Decision Records) của nhóm (ví dụ: `004-base-game-scope.md`). | Thêm mới khi có quyết định quan trọng |
| [`export/`](export/) | Chứa các bản Word (`.docx`) được chuyển đổi từ các file Markdown để phục vụ nộp báo cáo hoặc in ấn. | Sinh tự động bởi `export_docx.py` |

---

## 2. Nguyên tắc quan trọng

1. **Ràng buộc phạm vi (Scope):**
   - Dự án **CHỈ** hỏi đáp về lore **Elden Ring Base Game**.
   - Loại trừ hoàn toàn mọi DLC (kể cả *Shadow of the Erdtree*) và game *Elden Ring Nightreign* (xem chi tiết tại [`adr/004-base-game-scope.md`](adr/004-base-game-scope.md)).
2. **Quy tắc chỉnh sửa kế hoạch sprint:**
   - [`03_SPRINT_PLAN.md`](03_SPRINT_PLAN.md) được sinh tự động từ `planning/sprint_plan.json`. Khi cần cập nhật kế hoạch, sửa file JSON đó rồi chạy `python planning/build_docs.py`, không sửa tay vào file Markdown.
3. **Quy trình Git & Review:**
   - Mọi thay đổi tài liệu phải tạo nhánh riêng dạng `feature/<mã-tác-vụ>-<tên-ngắn-gọn>` từ `develop`.
   - Mở PR về `develop` và cần có sự phê duyệt (approve) của Mentor (`@HoanBuCon`) trước khi merge (theo [`quy_uoc.md`](quy_uoc.md)).

---

## 3. Xuất tài liệu sang Word (`.docx`)

Thư mục cung cấp script [`export_docx.py`](export_docx.py) để chuyển đổi toàn bộ tài liệu Markdown sang file Word đẹp mắt tại thư mục [`export/`](export/), tự động nhận diện bảng nhiều cột để xoay khổ ngang và đổ màu theo nhận diện của dự án.

### Cài đặt thư viện:
```bash
pip install -r docs/requirements.txt
```

### Chuyển đổi toàn bộ tài liệu:
```bash
python docs/export_docx.py
# Hoặc nếu đang đứng trong thư mục docs/:
python export_docx.py
```

### Chuyển đổi một file cụ thể:
```bash
python docs/export_docx.py quy_uoc.md
```

### Các tùy chọn nâng cao:
- `--landscape`: Ép tất cả các file xuất ra sang khổ ngang.
- `--no-recurse`: Chỉ quét các file `.md` ở thư mục gốc `docs/` (không quét đệ quy các thư mục con như `adr/`).
