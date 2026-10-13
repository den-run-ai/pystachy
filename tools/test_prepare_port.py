"""Checks of tools/prepare_port.py's edits and filters; neither Pyrefly nor LLVM is required (a fake
pyrefly stands in for it where infer runs).

usage: python3 -m unittest discover -s tools -p test_prepare_port.py
"""
import ast
import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import textwrap
import unittest
from types import SimpleNamespace

import prepare_port as pp


def src(s):
    return textwrap.dedent(s).lstrip("\n")


class EditTests(unittest.TestCase):
    def test_parameters_returns_and_variables(self):
        s = src('''
            def f(a, b=1, *args, **kw):
                x = []
                return a
            ''')
        out, skipped = pp.edit(s, {("f", "param", "a"): "int", ("f", "param", "b"): "int", ("f", "param", "*args"): "str",
                                   ("f", "return", ""): "int", ("f", "var", "x"): "list[int]"})
        self.assertEqual(skipped, [])
        self.assertEqual(out, src('''
            def f(a: int, b: int = 1, *args: str, **kw) -> int:
                x: list[int] = []
                return a
            '''))
        back, _ = pp.edit(out, {("f", "param", "a"): None, ("f", "param", "b"): None, ("f", "param", "*args"): None,
                                ("f", "return", ""): None, ("f", "var", "x"): None})
        self.assertEqual(back, s)

    def test_a_header_over_lines_with_decorators_and_a_return_annotation(self):
        s = src('''
            class C:
                @staticmethod
                def g(
                    a: "C",  # é before the edits
                    b=(1, 2),
                ) -> tuple[int, int]:
                    return b
            ''')
        out, _ = pp.edit(s, {("C.g", "return", ""): "'C'", ("C.g", "param", "b"): "tuple[int, int]"})
        self.assertIn("    b: tuple[int, int] = (1, 2),\n) -> 'C':", out.replace("    ) ->", ") ->"))
        out, _ = pp.edit(s, {("C.g", "return", ""): None, ("C.g", "param", "a"): None})
        self.assertIn('        a,  # é before the edits\n', out)
        self.assertIn("    ):\n", out)

    def test_overloads_are_left_out_and_repeated_defs_numbered(self):
        s = src('''
            from typing import overload
            class C:
                @overload
                def get(self, k: str) -> str: ...
                def get(self, k, d=None):
                    return d
                @property
                def x(self):
                    return 1
                @x.setter
                def x(self, v):
                    pass
            ''')
        sites = pp.sites(s)
        self.assertEqual(sites[("C.get", "param", "k")], None)  # the def, not the stub
        self.assertIn(("C.x#2", "param", "v"), sites)
        out, _ = pp.edit(s, {("C.x#2", "param", "v"): "int", ("C.get", "return", ""): "str | None"})
        self.assertIn("def x(self, v: int):", out)
        self.assertIn("def get(self, k, d=None) -> str | None:", out)

    def test_what_cannot_be_edited_is_reported(self):
        s = "a = b = []\n"
        out, skipped = pp.edit(s, {("", "var", "a"): "list[int]", ("", "var", "nope"): "int"})
        self.assertEqual(out, s)
        self.assertEqual(sorted(w for _, w in skipped), ["a chained assignment", "no such site"])


class SupportTests(unittest.TestCase):
    def check(self, ann, kind="param", fn="f", in_method=False, typevars=()):
        return pp.unsupported(ann, {"Node"}, in_method, kind, fn, typevars)

    def test_supported(self):
        for ann in ("int", "list[str]", "dict[str, list[int]] | None", "Optional[Node]", "'Node'", "tuple[int, str]",
                    "Callable[[int, str], bool]", "Union[str, None]", "str | os.PathLike[str]", "set[tuple[int, int]]"):
            with self.subTest(ann=ann):
                self.assertEqual(self.check(ann), "")
        self.assertEqual(self.check("Self", in_method=True), "")
        self.assertEqual(self.check("Iterator[int]", kind="return", fn="__iter__"), "")
        self.assertEqual(self.check("list[T]", typevars={"T"}), "")
        self.assertEqual(self.check("None", kind="return"), "")
        self.assertEqual(self.check("Final[int]", kind="var"), "")

    def test_unsupported(self):
        for ann, why in (("Any", "Any"), ("int | str", "union"), ("bytes", "bytes"), ("tuple[int, ...]", "run-time length"),
                         ("Callable[..., int]", "Callable[..., R]"), ("Iterator[int]", "iterator"),
                         ("list[Any]", "Any"), ("Literal['a']", "Literal"), ("Callable", "signature"), ("None", "None"),
                         ("Shape", "name Shape"), ("Self", "name Self")):
            with self.subTest(ann=ann):
                self.assertIn(why, self.check(ann))
        self.assertIn("TypeVar", self.check("T", fn="__init__", typevars={"T"}))


class DefTimeTests(unittest.TestCase):
    def test_names_a_def_cannot_evaluate_yet_are_quoted_or_dropped(self):
        bound = {"Node": 10, "Callable": 1}
        own = {"Node", "Later"}
        self.assertEqual(pp.at_def_time("Node | None", 20, bound, own, ""), "Node | None")
        self.assertEqual(pp.at_def_time("Node | None", 12, bound, own, "Node"), "'Node | None'")  # in its own body
        self.assertEqual(pp.at_def_time("list['Later']", 20, bound, own, ""), "'list[Later]'")
        self.assertEqual(pp.at_def_time("Self", 12, bound, own, "Node"), "'Node'")
        self.assertEqual(pp.at_def_time("Callable[[int], str]", 20, bound, own, ""), "Callable[[int], str]")
        self.assertIsNone(pp.at_def_time("Shape", 20, bound, own, ""))  # (another module's: no import is added)


class DecideTests(unittest.TestCase):
    SRC = src('''
        class Box:
            def __init__(self, v):
                self.v = v

            def get(self):
                return self.v

            def size(self):
                return 1


        def total(xs):
            return sum(xs)


        def label(n: int):
            return str(n)
        ''')
    INFERRED = src('''
        class Box:
            def __init__(self, v: int) -> None:
                self.v = v

            def get(self) -> int:
                return self.v

            def size(self) -> int:
                return 1


        def total(xs: list[int]) -> int | float:
            return sum(xs)


        def label(n: int):
            return str(n)
        ''')

    def rows(self, policy):
        keep, rows = pp.decide(self.SRC, self.INFERRED, policy, {"Box"})
        return keep, {tuple(r["site"]): r for r in rows}

    def test_templates_keep_returns_and_leave_parameters(self):
        keep, rows = self.rows("templates")
        self.assertEqual(keep, {("Box.__init__", "return", ""): "None", ("Box.get", "return", ""): "int",
                                ("Box.size", "return", ""): "int"})
        self.assertIn("templates", rows[("total", "param", "xs")]["why"])
        self.assertIn("union", rows[("total", "return", "")]["why"])
        # label() has every parameter annotated and returns a value: Pystachy reads it as -> None
        self.assertTrue(rows[("label", "return", "")]["blocker"])

    def test_signatures_keep_parameters_only_where_the_return_is_supported(self):
        keep, rows = self.rows("signatures")
        self.assertEqual(keep.get(("Box.__init__", "param", "v")), "int")
        self.assertNotIn(("total", "param", "xs"), keep)  # (it would read as -> None: a template instead)
        self.assertIn("stays a template", rows[("total", "param", "xs")]["why"])


class InferTests(unittest.TestCase):
    """infer, end to end, with a fake pyrefly that annotates count() and first() with -> int."""

    FAKE = src(f'''
        #!{sys.executable}
        import os, re, sys
        if sys.argv[1] == "--version":
            print("pyrefly {pp.PYREFLY}")
            sys.exit(0)
        for dp, dn, fn in os.walk("."):
            for f in fn:
                if f.endswith(".py"):
                    p = os.path.join(dp, f)
                    with open(p) as h:
                        s = h.read()
                    with open(p, "w") as h:
                        h.write(re.sub(r"(def (?:count|first)\\(.*?\\)):", r"\\1 -> int:", s))
        ''')
    LIB = src('''
        from typing import Any


        class Counter:
            def __init__(self, start: Any = 0):
                self.n = start

            def count(self, step: Any):
                self.n += step
                return self.n


        def first(xs):
            return xs[0]
        ''')

    def run_infer(self, untype):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        fake = os.path.join(tmp, "pyrefly")
        with open(fake, "w") as f:
            f.write(self.FAKE)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        os.makedirs(os.path.join(tmp, "src", "lib"))
        with open(os.path.join(tmp, "src", "lib", "__init__.py"), "w") as f:
            f.write(self.LIB)
        out = os.path.join(tmp, "out")
        args = SimpleNamespace(src=os.path.join(tmp, "src", "lib"), out=out, policy="templates", passes=2,
                               pyrefly=fake, untype=untype)
        with contextlib.redirect_stdout(io.StringIO()):
            pp.infer(args)
        result = pp.read(os.path.join(out, "lib", "__init__.py"))
        ast.parse(result)
        return result, json.loads(pp.read(os.path.join(out, "report.json"))), pp.read(os.path.join(out, "prepare.patch"))

    def test_suggestions_are_written_into_a_copy(self):
        result, report, patch = self.run_infer(False)
        self.assertIn("def first(xs) -> int:", result)
        self.assertIn("def count(self, step: Any) -> int:", result)  # (Any stays: a blocker)
        self.assertIn("+def first(xs) -> int:", patch)
        rows = report["modules"]["__init__.py"]
        self.assertTrue(any(r.get("blocker") and r["site"] == ["Counter.count", "param", "step"] for r in rows))

    def test_untype_leaves_out_what_pystachy_cannot_type_but_init_parameters(self):
        result, report, _ = self.run_infer(True)
        self.assertIn("def count(self, step) -> int:", result)  # a template now, which Pyrefly typed again
        self.assertIn("def __init__(self, start: Any = 0):", result)  # (it would make Counter a class template)


if __name__ == "__main__":
    unittest.main()
