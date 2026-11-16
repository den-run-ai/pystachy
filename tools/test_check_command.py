"""`pystachy check`: semantic checking through finalization, unit recovery and its reports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parent.parent

INDEPENDENT = """
def add(a, b):
    return a + b


def bad1(x: int) -> int:
    return x + "one"


def bad2(s: str) -> str:
    return s.nosuch()


def uses() -> int:
    return add(1, "x") * 2


def fine(n: int) -> int:
    return n * 2


print(bad1(1), bad2("a"), uses(), fine(3))
"""

# g(None) exists only because uses() compiled with add(int, str) left out: reporting its
# failure as an error would invent one. other() fails independently.
DEPENDENT = """
def add(a, b):
    return a + b


def g(v):
    return v + 1


def uses() -> int:
    x = add(1, "x")
    print(len(x))
    return g(x)


def other(n: int) -> str:
    return n + "z"


print(uses(), other(2))
"""

# Y's type comes from a body left out; use() never calls add(), but reads Y.
GLOBAL = """
def add(a, b):
    return a + b


Y = add(1, "x")


def use() -> int:
    return Y + 1


print(use())
"""

# A specialization's field typed by a body left out: Holder[int].use() reads it.
LAYOUT = """
def make(n):
    return n + "x"


class Holder:
    def __init__(self, n):
        self.v = make(n)

    def use(self):
        return self.v + 1


def run() -> None:
    h = Holder(1)
    print(h.use())


run()
"""

MODULE = """
x: int = 1
y = x + "a"


def later(n: int) -> int:
    return n + "l"


print(y, later(1))
"""

# The python-int pragma is the module's first line; decisions are reported per file.
DECISIONS = """# pystachy: python-int
class Box:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


class Point:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


def twice(x):
    return x + x


def never(s):
    return s * 2


def big() -> int:
    return 2 ** 70


print(Box(1).get(), Box("a").get(), twice(2), twice("b"), Point(1.0, 2.0).x, big())
"""

# helper() compiles as a program's function, but an extension module may not keep a public
# function that is not @export: only --ext checks that admission, after every body.
EXPORTS = """
from ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


def helper(x: int) -> int:
    return x + 1
"""


class CheckCommandTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        self.env.update(PYSTACHY_HOME=str(ROOT))

    def program(self, source, name="program.py"):
        path = self.directory / name
        path.write_text(textwrap.dedent(source).lstrip("\n"), encoding="utf-8")
        return path

    def run_compiler(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "pystachy.py"), *[str(a) for a in args]],
                              cwd=ROOT, env=self.env, text=True, capture_output=True, timeout=240)

    def check(self, path, *flags):
        return self.run_compiler("check", path, *flags)

    def lines(self, result, path):
        # stderr's lines, with the program's directory left out of its locations
        return [line.replace(str(path.parent) + "/", "") for line in result.stderr.splitlines()]

    def report(self, path, *flags):
        result = self.check(path, "--json", *flags)
        self.assertEqual(result.stderr, "")
        return result, json.loads(result.stdout)

    def test_a_program_that_compiles_checks_silently(self):
        path = self.program("def f(n: int) -> int:\n    return n + 1\n\n\nprint(f(2))\n")
        result = self.check(path)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_the_first_error_is_the_one_compilation_reports(self):
        path = self.program(INDEPENDENT)
        compiled = self.run_compiler("ir", path, "-o", self.directory / "out.ll")
        checked = self.check(path)
        self.assertEqual((compiled.returncode, checked.returncode), (1, 1))
        self.assertEqual(checked.stderr.splitlines()[0], compiled.stderr.strip())

    def test_independent_failures_are_reported_together(self):
        path = self.program(INDEPENDENT)
        result = self.check(path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.lines(result, path), [
            "program.py:6: error: unsupported operand type(s) for +: 'int' and 'str'",
            "program.py:10: error: 'str' has no method 'nosuch'",
            "program.py:2: error: unsupported operand type(s) for +: 'int' and 'str' "
            "(compiling add(int, str) for the call at program.py:14)",
        ])

    def test_a_failure_that_uses_a_result_left_out_is_a_note(self):
        path = self.program(DEPENDENT)
        result = self.check(path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.lines(result, path), [
            "program.py:2: error: unsupported operand type(s) for +: 'int' and 'str' "
            "(compiling add(int, str) for the call at program.py:10)",
            "program.py:5: note: g(None) was not checked: its types may depend on add(int, str), which failed",
            "program.py:16: error: unsupported operand type(s) for +: 'int' and 'str'",
        ])

    def test_results_left_out_reach_globals_and_layouts_only_as_notes(self):
        for source, unit, line in [(GLOBAL, "use()", 8), (LAYOUT, "Holder[None].use()", 9)]:
            path = self.program(source)
            result = self.check(path)
            self.assertEqual(result.returncode, 1)
            out = self.lines(result, path)
            self.assertEqual(len(out), 2, out)
            self.assertIn(": error: unsupported operand type(s) for +: 'int' and 'str'", out[0])
            self.assertTrue(out[1].startswith(f"program.py:{line}: note: {unit} was not checked: its types may depend on "), out)

    def test_module_code_failure_stops_checking(self):
        path = self.program(MODULE)
        result = self.check(path)
        self.assertEqual(result.returncode, 1)
        out = self.lines(result, path)
        self.assertEqual(out[0], "program.py:2: error: unsupported operand type(s) for +: 'int' and 'str'")
        self.assertEqual(len(out), 2, out)
        self.assertIn("note: checking stopped: module code is checked as one unit", out[1])
        _, report = self.report(path)
        self.assertEqual((report["status"], report["errors"]), ("incomplete", 1))
        self.assertNotIn("typing", report)  # (no attempt completed)

    def test_load_failures_stop_before_anything_is_checked(self):
        for source, message in [("def f(:\n    pass\n", "invalid syntax"),
                                ("import no_such_module_here\n", "module 'no_such_module_here' is not supported")]:
            path = self.program(source)
            result = self.check(path)
            self.assertEqual(result.returncode, 1)
            out = self.lines(result, path)
            self.assertIn(message, out[0])
            self.assertEqual(out[1:], ["program.py: note: checking stopped: the program did not load, so nothing was checked"])

    def test_syntax_mode_only_parses(self):
        path = self.program(INDEPENDENT)
        result = self.check(path, "--syntax")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        path = self.program("def f(:\n    pass\n")
        result = self.check(path, "--syntax")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.lines(result, path), ["program.py:1: error: invalid syntax"])

    def test_max_errors_bounds_the_attempts(self):
        path = self.program(INDEPENDENT)
        result = self.check(path, "--max-errors", "2")
        self.assertEqual(result.returncode, 1)
        out = self.lines(result, path)
        self.assertEqual(len(out), 3, out)
        self.assertEqual(out[2], "program.py: note: checking stopped after 2 failed units (--max-errors 2)")
        _, report = self.report(path, "--max-errors", "2")
        self.assertEqual((report["status"], report["attempts"], report["errors"]), ("incomplete", 2, 2))

    def test_invalid_arguments_are_usage_errors(self):
        path = self.program("print(1)\n")
        for flags in [["--bogus"], ["--syntax", "--json"], ["--json", "--syntax"], ["--max-errors"],
                      ["--max-errors", "0"], ["--max-errors", "x"], ["--syntax", "--ext"]]:
            result = self.check(path, *flags)
            self.assertEqual((result.returncode, result.stdout), (2, ""), flags)
            self.assertIn("pystachy check: unexpected argument", result.stderr)

    def test_json_reports_each_failed_unit(self):
        path = self.program(INDEPENDENT)
        result, report = self.report(path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual((report["version"], report["status"], report["errors"], report["attempts"]), (1, "errors", 3, 4))
        self.assertEqual([(d["severity"], d["unit"]["name"], d["unit"]["kind"], d["line"], d["body_left_out"])
                          for d in report["diagnostics"]],
                         [("error", "bad1()", "function", 6, True), ("error", "bad2()", "function", 10, True),
                          ("error", "add(int, str)", "function", 2, True)])
        status = {t["unit"]: t["status"] for t in report["typing"]}
        self.assertEqual(status["bad1()"], "left out")
        self.assertEqual(status["uses()"], "partly checked")
        self.assertEqual(status["fine()"], "checked")

    def test_json_keeps_typing_layout_and_specialization_decisions_apart(self):
        path = self.program(DECISIONS)
        result, report = self.report(path)
        self.assertEqual((result.returncode, report["status"], report["attempts"]), (0, "ok", 1))
        typing = {t["unit"]: t for t in report["typing"]}
        twice = typing["twice(int)"]
        # A promoting module: the parameter is a checked 64-bit int, the result a promoting one.
        self.assertEqual([(p["name"], p["type"], p["representation"], p["storage"]) for p in twice["parameters"]],
                         [("x", "int", "int", "i64")])
        self.assertEqual(twice["result"], {"type": "int", "representation": "int+", "storage": "{i64, ptr}"})
        self.assertTrue(twice["result_inferred"])
        self.assertEqual([p["representation"] for p in typing["Box[str].get()"]["parameters"]], ["Box-2"])
        layouts = {l["layout"]: l for l in report["layouts"]}
        self.assertEqual([(f["name"], f["type"], f["storage"]) for f in layouts["Box-1"]["fields"]], [("v", "int", "i64")])
        self.assertEqual((layouts["Box-2"]["class"], layouts["Box-2"]["shown"]), ("Box", "Box[str]"))
        self.assertEqual([f["storage"] for f in layouts["Point"]["fields"]], ["double", "double"])
        specializations = {(s["template"], s["kind"]): s for s in report["specializations"]}
        self.assertEqual([i["instance"] for i in specializations[("twice", "function")]["instances"]],
                         ["twice(int)", "twice(str)"])
        self.assertEqual([(i["instance"], i["key"]) for i in specializations[("Box", "class")]["instances"]],
                         [("Box[int]", "Box(int)"), ("Box[str]", "Box(str)")])
        self.assertEqual([(p["file"].rsplit("/", 1)[-1], p["int"], p["any"]) for p in report["policies"]],
                         [("program.py", "promoting", "inferred")])
        self.assertEqual([(u["unit"], u["template"]) for u in report["unreached"]], [("never()", True)])

    def test_extension_mode_checks_export_admission(self):
        path = self.program(EXPORTS, "exports.py")
        program = self.check(path)
        self.assertEqual((program.returncode, program.stderr), (0, ""))
        ordinary = self.run_compiler("ext", path, "-o", self.directory / "exports.so")
        checked = self.check(path, "--ext")
        self.assertEqual((ordinary.returncode, checked.returncode), (1, 1))
        out = self.lines(checked, path)
        self.assertEqual(out[0], ordinary.stderr.strip().replace(str(path.parent) + "/", ""))
        self.assertIn("helper() is public in extension module 'exports' but not @export", out[0])
        self.assertEqual(out[1:], ["exports.py: note: checking stopped at this export's admission, "
                                   "after every function was checked: later exports were not checked"])


if __name__ == "__main__":
    unittest.main()
