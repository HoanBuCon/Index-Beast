"""Dev startup ordering and cleanup; local stub HTTP/processes only, no app/model/server services."""

import json
import os
import socket
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from scripts import dev


@contextmanager
def health_server(responses):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            code, body = responses[min(len(calls) - 1, len(responses) - 1)]
            self.send_response(code)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v1/health", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_waits_for_successful_health_not_just_any_http_response(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://invalid-proxy.test:1")
    with health_server([(503, {"status": "degraded"}), (200, {"status": "loading"}), (200, {"status": "ok"})]) as (
        url,
        calls,
    ):
        dev.wait_ready(url, SimpleNamespace(poll=lambda: None), 3)
        assert calls == ["/api/v1/health"] * 3


def test_failed_health_times_out_and_exited_api_does_not_wait():
    with health_server([(503, {"status": "degraded"})]) as (url, calls):
        with pytest.raises(RuntimeError, match="Web chưa được khởi động"):
            dev.wait_ready(url, SimpleNamespace(poll=lambda: None), 0.05)
        before = len(calls)
        with pytest.raises(RuntimeError, match="exit 7"):
            dev.wait_ready(url, SimpleNamespace(poll=lambda: 7), 30)
        assert len(calls) == before


def test_supervisor_opens_web_only_after_health_and_shares_port(monkeypatch):
    events, stopped = [], []

    def start(command, env):
        label = command[2]
        events.append(label)
        assert env["API_PORT"] == "18001" and env["WEB_HOST"] == "0.0.0.0"
        return SimpleNamespace(label=label, poll=lambda: 0 if label == "web" else None)

    def ready(url, api, timeout):
        assert url == "http://127.0.0.1:18001/api/v1/health" and api.label == "api"
        events.append("ready")

    monkeypatch.setattr(dev, "start", start)
    monkeypatch.setattr(dev, "wait_ready", ready)
    monkeypatch.setattr(dev, "stop", lambda process: stopped.append(process.label))
    assert dev.run("make", 18001, "0.0.0.0", 30) == 0
    assert events == ["api", "ready", "web"]
    assert stopped == ["web", "api"]


@pytest.mark.parametrize("error,exit_code", [(RuntimeError("health timeout"), 1), (KeyboardInterrupt(), 130)])
def test_timeout_or_interrupt_cleans_api_without_starting_web(monkeypatch, error, exit_code):
    started, stopped = [], []
    api = SimpleNamespace()

    def start(command, env):
        started.append(command[2])
        return api

    def fail(*args):
        raise error

    monkeypatch.setattr(dev, "start", start)
    monkeypatch.setattr(dev, "wait_ready", fail)
    monkeypatch.setattr(dev, "stop", lambda process: stopped.append(process))
    assert dev.run("make", 18001, "127.0.0.1", 0.05) == exit_code
    assert started == ["api"] and stopped == [api]


def test_cleanup_stops_real_owned_process_tree(tmp_path):
    port_file = tmp_path / "port.txt"
    child = (
        "import socket,time,pathlib; s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(); "
        f"pathlib.Path({str(port_file)!r}).write_text(str(s.getsockname()[1])); time.sleep(60)"
    )
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(60)"
    process = dev.start([sys.executable, "-c", parent], dict(os.environ))
    try:
        deadline = time.monotonic() + 5
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert port_file.exists(), "stub child did not start"
        port = int(port_file.read_text())
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    finally:
        dev.stop(process)
    assert process.poll() is not None
    with pytest.raises(OSError), socket.create_connection(("127.0.0.1", port), timeout=1):
        pass


@pytest.mark.parametrize("value", ["0", "nan", "inf", "-1"])
def test_cli_rejects_unbounded_or_invalid_timeout(value):
    with pytest.raises(SystemExit) as exc:
        dev.main(["--api-port", "18001", "--timeout", value])
    assert exc.value.code == 2
