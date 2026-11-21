"""Chạy đoạn code tính toán nhỏ do Agent viết (22/11/2026: thay calculator build viết cứng).

Model đọc text web và corpus không tin cậy, nên code của nó được coi là có hại:
1. Kiểm tĩnh: chỉ nhận một tập con Python dùng để tính toán (literal, tên, số học, so sánh,
   if/for/while, comprehension, hàm, list/dict/set/tuple, f-string, gọi method trên giá trị). Không import,
   không thuộc tính hay tên bắt đầu bằng "_", không exec/eval/open/compile/globals/getattr và tương tự, không class,
   with, try, global hay async.
2. Chạy trong một tiến trình Python riêng, cô lập (`-I`, không site, môi trường rỗng) với builtins bị giới hạn,
   timeout theo thời gian thực và output có giới hạn.

Đây là sandbox ở mức ngôn ngữ, không phải mức hệ điều hành: production nên chạy worker trong
container không có mạng và filesystem không ghi được (xem docs/adr/006-true-agent.md).
"""

import ast
import json
import os
import subprocess
import sys

MAX_CODE_CHARS = 4000
MAX_OUTPUT_CHARS = 4000
TIMEOUT_SECONDS = 3.0

SAFE_BUILTINS = (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "int", "isinstance", "len",
    "list", "map", "max", "min", "print", "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple",
    "zip", "ValueError", "Exception",
)  # fmt: skip
ALLOWED_NODES = (
    ast.Module, ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Name, ast.Load, ast.Store, ast.Del,
    ast.Constant, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.If, ast.For, ast.While,
    ast.Break, ast.Continue, ast.Pass, ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Subscript, ast.Slice,
    ast.Call, ast.keyword, ast.Attribute, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
    ast.comprehension, ast.JoinedStr, ast.FormattedValue, ast.FunctionDef, ast.Return, ast.arguments, ast.arg,
    ast.Lambda, ast.Starred, ast.Assert, ast.Raise, ast.operator, ast.unaryop, ast.boolop, ast.cmpop,
    ast.expr_context,
)  # fmt: skip
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "globals", "locals", "vars", "getattr", "setattr", "delattr", "dir",
    "input", "breakpoint", "help", "memoryview", "object", "type", "super", "classmethod", "staticmethod",
    "property",
    # str.format có thể chạm tới thuộc tính dunder qua cú pháp trường ("{0.__class__}").
    "format", "format_map",
}  # fmt: skip
MEMORY_LIMIT_BYTES = 256 * 1024 * 1024

# Chạy trong tiến trình con: không kiểm lại gì (tiến trình cha đã kiểm) nhưng chỉ cho code dùng builtins an toàn.
_WORKER = r"""
import builtins, json, sys

class Bounded:
    def __init__(self, limit):
        self.left = limit
    def write(self, text):
        self.left -= len(text)
        if self.left < 0:
            raise RuntimeError("output too long")
        return sys.__stdout__.write(text)
    def flush(self):
        sys.__stdout__.flush()

safe = {name: getattr(builtins, name) for name in json.loads(sys.argv[1])}
code = sys.stdin.read()
sys.stdout = Bounded(int(sys.argv[2]))
try:
    exec(compile(code, "<agent>", "exec"), {"__builtins__": safe}, None)
except BaseException as exc:
    print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(1)
"""


def _limit_memory():  # pragma: no cover - POSIX only (production containers)
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))


class SandboxError(ValueError):
    """Code bị từ chối trước khi chạy (không được phép) hoặc lỗi khi chạy."""


def check_code(code: str) -> None:
    if len(code) > MAX_CODE_CHARS:
        raise SandboxError(f"Code is longer than {MAX_CODE_CHARS} characters")
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise SandboxError(f"SyntaxError: {exc.msg} (line {exc.lineno})") from None
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise SandboxError(f"{type(node).__name__} is not allowed; use plain calculations only")
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise SandboxError("Decorators are not allowed")
        name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
        if name is not None and (name.startswith("_") or name in FORBIDDEN_NAMES):
            raise SandboxError(f"'{name}' is not allowed")
        if isinstance(node, ast.FunctionDef) and (node.name.startswith("_") or node.name in FORBIDDEN_NAMES):
            raise SandboxError(f"Function name '{node.name}' is not allowed")
        if isinstance(node, ast.arg) and node.arg.startswith("_"):
            raise SandboxError(f"Argument name '{node.arg}' is not allowed")


def run_python(code: str, *, timeout: float = TIMEOUT_SECONDS) -> dict:
    """Chạy code đã kiểm; trả về {"status": "ok", "output"} hoặc {"status": "error", "error"}. Không bao giờ raise."""
    try:
        check_code(code)
    except SandboxError as exc:
        return {"status": "error", "error": str(exc)}
    # Windows cần SYSTEMROOT để khởi động Python; ngoài ra không truyền gì khác từ môi trường của server.
    env = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", "")} if os.name == "nt" else {}
    try:
        done = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _WORKER, json.dumps(SAFE_BUILTINS), str(MAX_OUTPUT_CHARS)],
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            preexec_fn=_limit_memory if os.name == "posix" else None,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"Timed out after {timeout:g} s; simplify the calculation"}
    output = done.stdout[:MAX_OUTPUT_CHARS]
    if done.returncode != 0:
        return {"status": "error", "error": done.stderr.strip()[-500:] or "Execution failed", "output": output}
    return {"status": "ok", "output": output or "(no output: print the result)"}
