"""Đẩy kế hoạch trong sprint_plan.json lên bảng Trello qua REST API.

Chỉ dùng thư viện chuẩn của Python. Chạy lại nhiều lần an toàn: list/label/thẻ
đã tồn tại (trùng tên) sẽ được bỏ qua.

Chuẩn bị:
  1. Lấy API key:  https://trello.com/power-ups/admin  -> tạo Power-Up -> API key
  2. Lấy token:    bấm link "Token" ngay cạnh API key và cấp quyền cho board
  3. Đặt biến môi trường (KHÔNG commit vào git):
       PowerShell:  $env:TRELLO_KEY="..."; $env:TRELLO_TOKEN="..."
       bash:        export TRELLO_KEY=... TRELLO_TOKEN=...
  4. (Tuỳ chọn) điền "trello_username" cho từng thành viên trong sprint_plan.json
     để script tự gán người vào thẻ.

Cách dùng:
  python planning/trello_import.py --dry-run     # chỉ in ra những gì sẽ tạo
  python planning/trello_import.py               # tạo thật
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

API = "https://api.trello.com/1"
PLAN_PATH = Path(__file__).resolve().parent / "sprint_plan.json"
ENV_FILE = Path(__file__).resolve().parent / ".trello.env"  # đã gitignore, không commit
LOCAL_TZ = timezone(timedelta(hours=7))  # giờ Việt Nam
PRIORITIES = ("Must", "Should", "Could")


class Trello:
    def __init__(self, key: str, token: str, dry_run: bool) -> None:
        self.auth = {"key": key, "token": token}
        self.dry_run = dry_run
        self._fake_id = 0

    def request(self, method: str, path: str, **params) -> dict | list:
        if self.dry_run and method != "GET":
            self._fake_id += 1
            return {"id": f"dry-{self._fake_id}"}
        query = {**self.auth, **{k: v for k, v in params.items() if v is not None}}
        url = f"{API}{path}?{urllib.parse.urlencode(query)}"
        for attempt in range(5):
            req = urllib.request.Request(url, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    time.sleep(0.12)  # giới hạn Trello: 100 request / 10 giây / token
                    return json.loads(resp.read().decode("utf-8") or "{}")
            except urllib.error.HTTPError as err:
                if err.code == 429 and attempt < 4:
                    time.sleep(2 ** attempt)
                    continue
                body = err.read().decode("utf-8", "replace")
                raise RuntimeError(f"{method} {path} -> HTTP {err.code}: {body}") from None
        raise RuntimeError(f"{method} {path}: hết số lần thử lại")


def load_env_file(path: Path) -> None:
    """Đọc KEY=VALUE từ file (nếu có) vào biến môi trường; giá trị trong file được ưu tiên."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, sep, value = line.partition("=")
        if sep and not name.strip().startswith("#") and value.strip():
            os.environ[name.strip()] = value.strip()


def sprint_window(plan: dict, number: int) -> tuple[str, str]:
    start = date.fromisoformat(plan["start_date"]) + timedelta(days=(number - 1) * plan["sprint_length_days"])
    end = start + timedelta(days=plan["sprint_length_days"] - 1)
    start_dt = datetime.combine(start, dtime(9, 0), LOCAL_TZ)
    due_dt = datetime.combine(end, dtime(23, 0), LOCAL_TZ)
    return start_dt.isoformat(), due_dt.isoformat()


def card_description(card: dict, sprint: dict | None) -> str:
    parts = []
    if card.get("desc"):
        parts.append(card["desc"])
    meta = [f"**Phụ trách:** {card.get('owner', '-')}", f"**Story point:** {card.get('points', 0)}"]
    priority = next((p for p in PRIORITIES if p in card.get("labels", [])), None)
    if priority:
        meta.append(f"**Ưu tiên:** {priority}")
    if card.get("srs"):
        meta.append(f"**Yêu cầu SRS:** {', '.join(card['srs'])}")
    if sprint:
        meta.append(f"**Sprint:** {sprint['number']} — {sprint['name']}")
    parts.append("\n".join(meta))
    parts.append("_Definition of Done: xem thẻ ✅ trong cột Thông tin dự án._")
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="không tạo gì, chỉ in kế hoạch")
    parser.add_argument("--board", help="board id/shortLink (mặc định lấy từ sprint_plan.json)")
    args = parser.parse_args()

    load_env_file(ENV_FILE)
    key, token = os.environ.get("TRELLO_KEY"), os.environ.get("TRELLO_TOKEN")
    if not key or not token:
        print(f"Thiếu TRELLO_KEY / TRELLO_TOKEN (biến môi trường hoặc {ENV_FILE.name}).", file=sys.stderr)
        return 1

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    api = Trello(key, token, args.dry_run)
    board = api.request("GET", f"/boards/{args.board or plan['board_id']}", fields="id,name")
    board_id = board["id"]
    print(f"Board: {board['name']} ({board_id}){'  [DRY RUN]' if args.dry_run else ''}")

    # Lists
    existing_lists = {l["name"]: l["id"] for l in api.request("GET", f"/boards/{board_id}/lists", filter="open")}
    list_ids: dict[str, str] = {}
    for name in plan["lists"]:
        if name in existing_lists:
            list_ids[name] = existing_lists[name]
        else:
            list_ids[name] = api.request("POST", "/lists", name=name, idBoard=board_id, pos="bottom")["id"]
            print(f"  + list  {name}")

    # Labels
    existing_labels = {l["name"]: l["id"] for l in api.request("GET", f"/boards/{board_id}/labels", limit=1000) if l.get("name")}
    label_ids: dict[str, str] = {}
    for label in plan["labels"]:
        name = label["name"]
        if name in existing_labels:
            label_ids[name] = existing_labels[name]
            continue
        try:
            created = api.request("POST", f"/boards/{board_id}/labels", name=name, color=label["color"] or "null")
        except RuntimeError:
            created = api.request("POST", f"/boards/{board_id}/labels", name=name, color="black")
        label_ids[name] = created["id"]
        print(f"  + label {name}")

    # Members (tuỳ chọn)
    member_by_username = {m["username"].lower(): m["id"] for m in api.request("GET", f"/boards/{board_id}/members")}
    owner_member: dict[str, str] = {}
    for m in plan["members"]:
        username = (m.get("trello_username") or "").lstrip("@").lower()
        if username:
            if username in member_by_username:
                owner_member[m["id"]] = member_by_username[username]
            else:
                print(f"  ! {m['id']}: không tìm thấy @{username} trong board, bỏ qua gán người")

    existing_cards = {(c["idList"], c["name"]) for c in api.request("GET", f"/boards/{board_id}/cards", fields="name,idList")}

    def create_card(list_name: str, card: dict, title: str, sprint: dict | None) -> None:
        list_id = list_ids[list_name]
        if (list_id, title) in existing_cards:
            print(f"  = card  {title} (đã có)")
            return
        labels = list(card.get("labels", []))
        owner = card.get("owner")
        if owner in label_ids and owner not in labels:
            labels.insert(0, owner)
        if owner == "ALL" and "Team" not in labels:
            labels.insert(0, "Team")
        members = list(owner_member.values()) if owner == "ALL" else [owner_member[owner]] if owner in owner_member else []
        start, due = sprint_window(plan, sprint["number"]) if sprint else (None, None)
        created = api.request(
            "POST", "/cards",
            idList=list_id, name=title, pos="bottom",
            desc=card_description(card, sprint) if "points" in card else card.get("desc", ""),
            idLabels=",".join(label_ids[l] for l in labels if l in label_ids) or None,
            idMembers=",".join(members) or None,
            start=start, due=due,
        )
        if card.get("checklist"):
            checklist = api.request("POST", "/checklists", idCard=created["id"], name="Việc cần làm")
            for item in card["checklist"]:
                api.request("POST", f"/checklists/{checklist['id']}/checkItems", name=item, pos="bottom")
        print(f"  + card  {title} ({len(card.get('checklist', []))} việc)")

    info_list, backlog_list = plan["lists"][0], plan["lists"][1]
    for card in plan["info_cards"]:
        create_card(info_list, card, card["title"], None)
    for card in plan["backlog_cards"]:
        create_card(backlog_list, card, f"[{card['owner']}] {card['title']}", None)

    for sprint in plan["sprints"]:
        list_name = f"Sprint {sprint['number']}"
        goal_card = {
            "desc": f"**Mục tiêu:** {sprint['goal']}\n\nCuối sprint đánh dấu các sản phẩm bàn giao bên dưới.",
            "checklist": sprint["deliverables"],
            "labels": ["Team"],
        }
        create_card(list_name, goal_card, f"🎯 S{sprint['number']} — {sprint['name']}", sprint)
        for card in sprint["cards"]:
            create_card(list_name, card, f"[S{sprint['number']}][{card['owner']}] {card['title']}", sprint)

    print("Xong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
