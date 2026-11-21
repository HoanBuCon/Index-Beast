"""The Agent's calculation sandbox: plain arithmetic runs, anything reaching outside is refused."""

import pytest

from app.rag.python_sandbox import check_code, run_python


def test_a_build_calculation_runs_and_prints_its_result():
    code = (
        "level = 150\n"
        "floors = {'vigor': 10, 'mind': 10, 'endurance': 10, 'strength': 10,\n"
        "          'dexterity': 10, 'intelligence': 10, 'faith': 10, 'arcane': 10}\n"
        "plan = dict(floors, vigor=60, endurance=30, dexterity=40)\n"
        "plan['strength'] = level + 79 - sum(v for k, v in plan.items() if k != 'strength')\n"
        "assert all(10 <= v <= 99 for v in plan.values())\n"
        "print(plan, sum(plan.values()))\n"
    )
    result = run_python(code)
    assert result["status"] == "ok" and result["output"].strip().endswith("229")


@pytest.mark.parametrize(
    "code",
    [
        "import os",
        "from os import system",
        "open('x.txt', 'w')",
        "().__class__.__bases__",
        "'{0.__class__}'.format(1)",
        "eval('1+1')",
        "exec('x=1')",
        "getattr(1, 'real')",
        "class A: pass",
        "with x: pass",
        "__import__('os')",
        "globals()",
        "def _hidden(): pass",
    ],
)
def test_code_that_reaches_outside_plain_calculation_is_refused_before_running(code):
    result = run_python(code)
    assert result["status"] == "error" and "not allowed" in result["error"]


def test_runtime_errors_timeouts_and_floods_are_reported_not_raised():
    assert "ZeroDivisionError" in run_python("print(1 / 0)")["error"]
    assert "AssertionError" in run_python("assert 1 == 2, 'total wrong'")["error"]
    assert "Timed out" in run_python("while True:\n    pass", timeout=1)["error"]
    flood = run_python("while True:\n    print('x' * 100)", timeout=2)
    assert flood["status"] == "error" and len(flood.get("output", "")) <= 4000
    assert run_python("x = 1")["output"].startswith("(no output")


def test_unsafe_builtins_are_absent_even_if_named_indirectly():
    # Names are checked statically; the child process also exposes only the safe builtins.
    with pytest.raises(ValueError):
        check_code("vars()")
    assert "NameError" in run_python("print(hash(1))")["error"]
