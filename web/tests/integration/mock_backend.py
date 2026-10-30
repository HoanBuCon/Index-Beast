"""TV4: chạy API mock nguyên bản của TV1 cho kiểm thử web, không cần DB/LLM.

Chỉ là bộ gá kiểm thử phía frontend; không thay route, service hay schema backend.
"""

import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

from app.main import create_app
from core.config import Settings

app = create_app(
    settings=Settings(_env_file=None, environment="test", log_level="WARNING"),
    context=SimpleNamespace(health_checks={}),
)
# Cổng do hệ điều hành cấp cho test; không chiếm hoặc đổi API_PORT/WEB_PORT của người dùng.
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    print("WEB_TEST_READY " + json.dumps({"port": listener.getsockname()[1]}), flush=True)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    server.run(sockets=[listener])
