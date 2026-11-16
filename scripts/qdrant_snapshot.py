"""Gọi API snapshot của Qdrant bằng thư viện chuẩn. Chạy BÊN TRONG container api (nằm cùng mạng Docker với qdrant),
vì production không công khai cổng Qdrant và image qdrant không có curl. backup.sh/restore.sh gọi:

    docker compose exec -T api python -c "$(cat scripts/qdrant_snapshot.py)" <lệnh> <collection> [...]

Lệnh (chỉ in tên snapshot hoặc dữ liệu snapshot ra stdout; không in biến môi trường):
    create   <collection>              tạo snapshot, in tên
    download <collection> <tên>        ghi nội dung snapshot ra stdout (nhị phân)
    upload   <collection> <kích-thước> đọc snapshot từ stdin (đúng <kích-thước> byte), khôi phục đè lên collection
    delete   <collection> <tên>        xóa snapshot phía server
    list     <collection>              in tên các snapshot, mỗi dòng một tên
"""

import http.client
import json
import os
import re
import sys
import urllib.parse

HOST = os.environ.get("QDRANT_HOST", "qdrant")
PORT = int(os.environ.get("QDRANT_PORT", "6333"))
TIMEOUT = 3600  # snapshot lớn có thể mất vài phút
NAME = re.compile(r"^[A-Za-z0-9_.-]+$")  # tên collection/snapshot đi vào đường dẫn URL: chỉ cho ký tự an toàn


def call(method, path, body=None, headers=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=TIMEOUT)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    if resp.status >= 400:
        sys.stderr.write(f"Qdrant {method} {path} -> HTTP {resp.status}: {resp.read(500).decode(errors='replace')}\n")
        sys.exit(1)
    return resp


def check(*names):
    for n in names:
        if not NAME.match(n):
            sys.exit(f"Tên không hợp lệ: {n!r}")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd, collection = argv[0], argv[1]
    check(collection)
    base = f"/collections/{collection}/snapshots"
    if cmd == "create":
        print(json.load(call("POST", base + "?wait=true"))["result"]["name"])
    elif cmd == "list":
        for item in json.load(call("GET", base))["result"]:
            print(item["name"])
    elif cmd == "delete":
        check(argv[2])
        call("DELETE", f"{base}/{argv[2]}?wait=true").read()
    elif cmd == "download":
        check(argv[2])
        resp = call("GET", f"{base}/{argv[2]}")
        while chunk := resp.read(1 << 20):
            sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
    elif cmd == "upload":
        size = int(argv[2])
        boundary = "----indexbeast-snapshot"
        head = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="snapshot"; filename="restore.snapshot"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        tail = f"\r\n--{boundary}--\r\n".encode()
        query = urllib.parse.urlencode({"priority": "snapshot", "wait": "true"})
        conn = http.client.HTTPConnection(HOST, PORT, timeout=TIMEOUT)
        conn.putrequest("POST", f"{base}/upload?{query}")
        conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        conn.putheader("Content-Length", str(len(head) + size + len(tail)))
        conn.endheaders()
        conn.send(head)
        sent = 0
        while sent < size:
            chunk = sys.stdin.buffer.read(min(1 << 20, size - sent))
            if not chunk:
                sys.exit(f"stdin hết sau {sent}/{size} byte")
            conn.send(chunk)
            sent += len(chunk)
        conn.send(tail)
        resp = conn.getresponse()
        data = resp.read(500).decode(errors="replace")
        if resp.status >= 400:
            sys.exit(f"Qdrant upload -> HTTP {resp.status}: {data}")
        print("OK")
    else:
        sys.exit(__doc__)


main(sys.argv[1:])
