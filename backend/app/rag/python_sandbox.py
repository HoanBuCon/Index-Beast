"""Run small calculation code written by the Agent (22/11/2026: replaces the hard-coded build calculator).

The model reads untrusted web and corpus text, so its code is treated as hostile:
1. Static check: only a calculation subset of Python is accepted (literals, names, arithmetic, comparisons,
   if/for/while, comprehensions, functions, list/dict/set/tuple, f-strings, method calls on values). No import,
   no attribute or name starting with "_", no exec/eval/open/compile/globals/getattr and similar, no classes,
   with, try, global or async.
2. Execution in a separate, isolated Python process (`-I`, no site, empty environment) with restricted builtins,
   a wall-clock timeout and bounded output.

This is a language-level sandbox, not an operating-system one: production should also run the worker in a
container without network or writable filesystem (see docs/adr/006-true-agent.md).
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
    # str.format can reach dunder attributes through its field syntax ("{0.__class__}").
    "format", "format_map",
}  # fmt: skip
MEMORY_LIMIT_BYTES = 256 * 1024 * 1024

# Runs in the child process: re-checks nothing (the parent already did) but gives the code only safe builtins.
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
    """The code was rejected before running (not allowed) or failed while running."""


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
    """Run checked code; returns {"status": "ok", "output"} or {"status": "error", "error"}. Never raises."""
    try:
        check_code(code)
    except SandboxError as exc:
        return {"status": "error", "error": str(exc)}
    # Windows needs SYSTEMROOT to start Python; nothing else from the server environment is passed on.
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
