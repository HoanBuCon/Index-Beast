# planning/ (FOLDER PLANNING CHỈ DÙNG ĐỂ LẬP KẾ HOẠCH)

`sprint_plan.json` là nguồn duy nhất của kế hoạch sprint. Sửa file này, sau đó:

```bash
pip install -r planning/requirements.txt
python planning/build_docs.py          # sinh docs/03_SPRINT_PLAN.md + docs/export/*.docx
python planning/trello_import.py --dry-run
python planning/trello_import.py       # cần TRELLO_KEY, TRELLO_TOKEN (xem đầu file script)
```

Script Trello chạy lại an toàn: list, label và thẻ trùng tên sẽ được bỏ qua.
