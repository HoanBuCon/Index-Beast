"""Start API, await health, then start web. Standard library only; no model or application imports."""

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]


def wait_ready(url, api, timeout):
    deadline = time.monotonic() + timeout
    # A local readiness probe must not use HTTP_PROXY/HTTPS_PROXY from the developer's shell.
    opener = build_opener(ProxyHandler({}))
    last_error = "API chưa nhận kết nối"
    print(f"[dev] Đang chờ backend sẵn sàng ({timeout:g}s): {url}", flush=True)
    while True:
        code = api.poll()
        if code is not None:
            raise RuntimeError(f"Backend đã dừng trước khi sẵn sàng (exit {code}). Xem log API phía trên.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"Hết {timeout:g}s chờ backend: {last_error}. Web chưa được khởi động.")
        try:
            request = Request(url, headers={"Accept": "application/json"})
            with opener.open(request, timeout=min(2, remaining)) as response:
                body = json.loads(response.read(65536))
                if response.status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                    if api.poll() is not None:
                        raise RuntimeError("Tiến trình API vừa dừng. Xem log API phía trên.")
                    print("[dev] Backend sẵn sàng; đang khởi động web.", flush=True)
                    return
                last_error = "health chưa trả status=ok"
        except (URLError, OSError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))


def start(command, env):
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    return subprocess.Popen(command, cwd=ROOT, env=env, **options)


def stop(process):
    if os.name == "nt":
        # Kill only the make process tree this launcher created, including uvicorn --reload / Vite.
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    else:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def run(make, api_port, web_host, timeout):
    processes = []
    env = {**os.environ, "API_PORT": str(api_port), "WEB_HOST": web_host}
    # Reuse make api/web recipes; retain environment configuration without rewriting .env.
    command = [make, "--no-print-directory"]
    try:
        api = start([*command, "api", f"API_PORT={api_port}"], env)
        processes.append(("API", api))
        wait_ready(f"http://127.0.0.1:{api_port}/api/v1/health", api, timeout)
        web = start([*command, "web", f"WEB_HOST={web_host}"], env)
        processes.append(("Web", web))
        while True:
            for label, process in processes:
                code = process.poll()
                if code is not None:
                    print(f"[dev] {label} đã dừng (exit {code}); đang dừng tiến trình còn lại.", flush=True)
                    return code if code >= 0 else 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n[dev] Đang dừng API/web; giữ nguyên hạ tầng Docker.", flush=True)
        return 130
    except (OSError, RuntimeError) as exc:
        print(f"[dev] {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        for _, process in reversed(processes):
            stop(process)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--make", default="make")
    parser.add_argument("--api-port", type=int, required=True)
    parser.add_argument("--web-host", default="127.0.0.1")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    if not 1 <= args.api_port <= 65535 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--api-port phải từ 1 đến 65535 và --timeout phải là số hữu hạn > 0")
    return run(args.make, args.api_port, args.web_host, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
