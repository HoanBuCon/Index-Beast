# TV2 · Bổ sung 11 trang Origins/Attributes vào corpus (TV3 làm thay)

Ngày 20/11/2026 · Nhánh `fix/s4-tv3-tach-han-thoi-gian` (đang làm của TV3), chưa commit. Agent của TV3 (MinhMuc) làm thay phần việc dữ liệu của TV2 theo yêu cầu của TV3: Agent cần tự tra chỉ số khởi đầu của class trong corpus (hướng True Agent).

## Vấn đề

Corpus đang phục vụ (`indexbeast_s4_wiki_ca98c06b`, bản `s4-wiki-release`) không có trang class nào ngoài Samurai. Đã kiểm ở mọi tầng: `crawl_runs/s2-full-20261028/inventory.json`, `raw/wikigg/snapshots`, `chunk_runs/s4-wiki-release/documents.jsonl` và Qdrant. Nguyên nhân: phạm vi crawl theo category trong `ingest/config/sources.toml` (`NPC, Bosses, Locations, Lore, Items, Characters`, độ sâu 1) không gồm các trang Origins. Samurai lọt vào qua một category khác (giả thuyết, chưa xem tiêu chí cụ thể).

## Đã làm

- Dựng riêng 11 trang wiki.gg bằng `PipelineBuilder` (`ingest/update_builder.py`), tức đúng các bước production `transform.full --gameplay --structured-tables` và `chunk.full --wiki-quality`, tokenizer E5 local (`models/notebook-fastembed`), **tắt media** (không tải ảnh).
  - Vagabond, Warrior, Hero, Bandit, Astrologer, Prophet, Prisoner, Confessor, Wretch, Origins, Attributes. Samurai đã có nên bỏ qua.
  - Kết quả 68 chunk, tiếng Anh, `release_scope=unknown`, `cleaning_version=s3-full-clean-2.0`, `chunking_version=s4-full-chunk-1.1`.
  - Infobox của 9 class có đủ level và 8 chỉ số khởi đầu; tổng mỗi class đều bằng level + 79 (đã đối chiếu).
- `ingest index --dry-run`: 68/68 nhận, 0 bị loại, policy `pilot`, ngôn ngữ `en`.
- Chụp snapshot Qdrant trước khi ghi: `indexbeast_s4_wiki_ca98c06b-8961258703884535-2026-11-20-10-35-39.snapshot` (201 MB, trong volume Qdrant local).
- `ingest index` thật: `indexed: 68`; collection **34.070 → 34.138 điểm**. Point id ổn định theo chunk; các tài liệu cũ không bị đụng.
- Sửa lỗi trong `backend/ingest/transform/full.py`: một lô không có ảnh nào (ví dụ `update` khi tắt media) làm `images.csv` lỗi `IndexError` vì lấy cột từ dòng đầu tiên. Giờ không có dòng thì không có cột.

## File và artifact

| Loại | Vị trí |
|---|---|
| Script dựng (gitignored) | `backend/data/update_runs/s5-origins-addon/build_addon.py` (bản sao trong thư mục chunk) |
| Kiểm truy xuất (gitignored) | `backend/data/update_runs/s5-origins-addon/check_retrieval.py` |
| Chunk/document | `backend/data/chunk_runs/s5-origins-addon/{chunks,documents}.jsonl`, `report.json` |
| Raw snapshot | `backend/data/raw/wikigg/snapshots/<pageid>/<rev>-<hash>.json` |
| Run trung gian | `backend/data/update_runs/update-76624445eca5/` (thành công), `update-790a5d840b69/` (lần chạy đầu lỗi `images.csv`, giữ để đối chiếu) |
| Code | `backend/ingest/transform/full.py` (một dòng) |

Tài liệu mới (pageid, doc_id, revision):

| Trang | pageid | document_id | rev |
|---|---|---|---|
| Bandit | 1130 | 1a2b414c-e419-5ed3-b091-3d24c751bf03 | 102588 |
| Wretch | 1157 | b37af17c-38da-5ff7-b634-0d8563fe9296 | 102594 |
| Confessor | 4109 | 6f1fd54f-fd9c-58b0-b77a-5ece7c5f329b | 102593 |
| Attributes | 5214 | a85e9d16-9361-5113-a137-208a071cea09 | 65256 |
| Vagabond | 5255 | 6eaabf18-cd4b-5a43-838b-f5d9e0bea5d0 | 102585 |
| Astrologer | 6685 | cf551f1c-cb8a-5760-a534-b18b0bc041ee | 102589 |
| Warrior | 8156 | 30a5a622-1d71-5057-bd86-e52184c7b1fa | 102586 |
| Hero | 9851 | bf955cb9-8a5a-5761-acba-2a5a2e0328b1 | 102587 |
| Origins | 11560 | 9c3dccca-39c3-51b6-93bc-c9cb9032d286 | 101463 |
| Prophet | 12617 | f19a19ef-8e97-5f5d-8b7f-2c8adfd90e79 | 102590 |
| Prisoner | 13824 | 888512be-28fd-5459-9279-5f702fe31152 | 102592 |

## Cách chạy lại / hoàn tác

Từ `backend/`:

```powershell
.venv/Scripts/python.exe -X utf8 data/update_runs/s5-origins-addon/build_addon.py   # từ chối nếu thư mục kết quả đã có
.venv/Scripts/python.exe -X utf8 -m ingest index --input data/chunk_runs/s5-origins-addon/chunks.jsonl --policy pilot --languages en --collection indexbeast_s4_wiki_ca98c06b --dry-run
.venv/Scripts/python.exe -X utf8 -m ingest index --input data/chunk_runs/s5-origins-addon/chunks.jsonl --policy pilot --languages en --collection indexbeast_s4_wiki_ca98c06b
```

- Crawl cần `INGEST_CONTACT_EMAIL` trong `.env` gốc (đưa vào User-Agent). Không ghi giá trị vào tài liệu.
- Hoàn tác: xoá point theo bộ lọc payload `document_id` thuộc bảng trên, hoặc khôi phục snapshot ở trên.

## Kiểm tra

- Truy xuất hybrid local (không gọi LLM): "Vagabond starting attributes level" → `Vagabond | Infobox` đứng đầu; "Wretch starting stats" có `Wretch | Infobox` trong top 5; "Confessor base stats Vigor Mind" → `Confessor | Infobox` đầu, kèm Prisoner, Bandit.
- Câu tiếng Việt "chỉ số khởi đầu của class Astrologer" ra các trang bộ giáp Astrologer, không ra trang class. Agent viết lại câu hỏi sang tiếng Anh trước khi tìm nên đường chính không bị chặn, nhưng retrieval tiếng Việt thô còn yếu.
- Backend unit: 1.137 passed, 20 skipped; Ruff đạt (kèm thay đổi calculator của TV3).

## Hạn chế / việc còn lại cho TV2

1. **PostgreSQL chưa ghi** (container tắt): bảng `documents`/`chunks` chưa có 11 tài liệu này. Khi bật PG cần nạp `documents.jsonl`/`chunks.jsonl` theo cách đã dùng cho `s4-wiki-release`, nếu không `--bootstrap-from-db` của `ingest update` sẽ thiếu chúng.
2. **Phạm vi crawl chưa đổi**: lần dựng toàn bộ sau sẽ lại thiếu các trang này. Đề xuất thêm category `Origins` (hoặc danh sách trang) vào `[sources.wikigg]`; đổi phạm vi = đổi chính sách, nên dựng toàn bộ vào collection mới.
3. **Không có ảnh** cho 11 trang (media tắt).
4. `transform.full` sửa dòng `images.csv` chưa có unit test riêng; đã kiểm chứng bằng lượt dựng thật 11 trang.
5. State `ingest update` (`data/state/wikigg-update.json`) chưa tồn tại; lần này không dùng `update` nên không bootstrap.

## Liên quan (TV3)

Cùng nhánh, TV3 bỏ snapshot class khỏi `knowledge/gameplay.json`; calculator nhận chỉ số khởi đầu do Agent trích từ Infobox của trang class trong corpus (`build_data.starting_class`). Quy tắc tổng điểm (+79) vẫn nằm trong gói tri thức.
