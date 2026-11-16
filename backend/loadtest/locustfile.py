"""Kịch bản Locust cho IndexBeast (thẻ 5.7, NFR-PERF-01, NFR-CAP-01). Chạy: xem backend/loadtest/README.md.

Mỗi người dùng ảo: hỏi câu lấy từ golden set, nghỉ (think time), giữ nguyên hội thoại qua nhiều lượt như người thật.
- POST /api/v1/chat/stream (SSE): ghi 2 số đo: "TTFT" (tới token đầu tiên) và "total" (tới khung done).
- POST /api/v1/chat (JSON, kiểu bot) và GET /api/v1/health.
Cấu hình bằng biến môi trường (host dùng --host của Locust). CẢNH BÁO: chạy với CHAT_MODE=llm_only/rag là gọi LLM thật,
tốn tiền và cần TV1 duyệt; thử trước với CHAT_MODE=mock.

Phụ trách: TV3 (do TV1 dựng hộ) · [S5] Load test
"""

import json
import os
import random
import time

from locust import HttpUser, between, events, task

from loadtest.helpers import (
    env_float,
    env_int,
    golden_paths_from_env,
    load_questions,
    ok_codes,
    parse_sse,
    pick,
)

API = "/api/v1"
QUESTIONS = load_questions(golden_paths_from_env(os.environ.get("LOADTEST_GOLDEN")))
SERVICE_TOKEN = os.environ.get("LOADTEST_SERVICE_TOKEN", "").strip()  # có token = giả lập bot Discord
TURNS_PER_CONVERSATION = max(1, env_int("LOADTEST_TURNS_PER_CONVERSATION", 4))
THINK_MIN = env_float("LOADTEST_THINK_MIN", 5.0)
THINK_MAX = max(THINK_MIN, env_float("LOADTEST_THINK_MAX", 20.0))
WEB_SEARCH = os.environ.get("LOADTEST_WEB_SEARCH", "").strip()  # off|auto|always; trống = để server quyết định
HEALTH_OK = ok_codes(os.environ.get("LOADTEST_HEALTH_OK"))  # mock không có Postgres/Redis: đặt "200,503"
REQUEST_TIMEOUT = env_float("LOADTEST_TIMEOUT", 60.0)
TTFT_NAME = "POST /chat/stream [TTFT]"
STREAM_NAME = "POST /chat/stream [total]"


class ChatUser(HttpUser):
    wait_time = between(THINK_MIN, THINK_MAX)

    def on_start(self):
        self.rng = random.Random()
        self.headers = {"X-Service-Token": SERVICE_TOKEN} if SERVICE_TOKEN else {}
        self._new_conversation()

    def _new_conversation(self):
        self.conversation_id = None
        self.conversation_token = None
        self.turns = 0
        # Bot dùng external_ref ổn định cho mỗi hội thoại; web thì server cấp conversation_id/token
        self.external_ref = f"loadtest:{os.getpid()}:{id(self)}:{time.time_ns()}" if SERVICE_TOKEN else None

    def _body(self):
        if self.turns >= TURNS_PER_CONVERSATION:
            self._new_conversation()
        body = {"message": pick(QUESTIONS, self.rng), "channel": "discord" if SERVICE_TOKEN else "web"}
        if self.conversation_id:
            body["conversation_id"] = self.conversation_id
        if self.conversation_token:
            body["conversation_token"] = self.conversation_token
        if self.external_ref:
            body["external_ref"] = self.external_ref
        if WEB_SEARCH:
            body["options"] = {"web_search": WEB_SEARCH}
        return body

    def _remember(self, data: dict):
        self.conversation_id = data.get("conversation_id") or self.conversation_id
        self.conversation_token = data.get("conversation_token") or self.conversation_token
        self.turns += 1

    @task(3)
    def chat_json(self):
        with self.client.post(
            f"{API}/chat",
            json=self._body(),
            headers=self.headers,
            name="POST /chat",
            catch_response=True,
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            try:
                self._remember(resp.json())
            except ValueError:
                resp.failure("body không phải JSON")

    @task(6)
    def chat_stream(self):
        started = time.perf_counter()
        ttft_ms, done, error = None, None, None
        with self.client.post(
            f"{API}/chat/stream",
            json=self._body(),
            headers=self.headers,
            name=STREAM_NAME,
            stream=True,
            catch_response=True,
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            try:
                for event, data in parse_sse(resp.iter_lines(decode_unicode=True)):
                    if event == "token" and ttft_ms is None:
                        ttft_ms = (time.perf_counter() - started) * 1000
                    elif event == "done":
                        done = json.loads(data)
                    elif event == "error":
                        error = data[:120]
            except Exception as exc:  # đứt kết nối giữa chừng, timeout đọc…
                error = repr(exc)[:120]
            # Số đo của request = tổng thời gian tới hết luồng (mặc định Locust chỉ tính tới khi có header)
            resp.request_meta["response_time"] = (time.perf_counter() - started) * 1000
            if error or done is None:
                resp.failure(error or "luồng SSE kết thúc mà không có event done")
                return
            self._remember(done)
        if ttft_ms is not None:  # câu không có bằng chứng có thể không stream token nào: không tính vào TTFT
            events.request.fire(
                request_type="SSE",
                name=TTFT_NAME,
                response_time=ttft_ms,
                response_length=0,
                exception=None,
                context={},
            )

    @task(1)
    def health(self):
        with self.client.get(f"{API}/health", name="GET /health", catch_response=True) as resp:
            if resp.status_code in HEALTH_OK:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")
