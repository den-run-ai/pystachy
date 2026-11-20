"""Each typed-IR op the compiler builds records the line of the statement it implements.

Run with python3 -m unittest discover -s tools -p test_typed_ir_locations.py.
"""
from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import typed_ir_text as text  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402
from src.pystachy_compiler.loader import Loader  # noqa: E402

# Each function makes a pass synthesize ops: listguard's tests before a copy of stencil's loop,
# recursionscope's depth restorations before depth's returns, dictfuse's lookup in lookup,
# exception lowering's branch for checked's raise, unionslots' tag and payload slots in total,
# and the callback version's dispatcher in kernel.
PROGRAM = """from collections.abc import Callable


def stencil(a: list[float], b: list[float]) -> None:
    for i in range(1, len(a) - 1):
        b[i] = (a[i - 1] + a[i] + a[i + 1]) / 3.0


def depth(n: int, f: Callable[[int], int]) -> int:
    if n <= 0:
        return f(n)
    return depth(n - 1, f) + 1


def lookup(d: dict[str, int], k: str) -> int:
    if k in d:
        return d[k]
    return -1


def checked(n: int) -> int:
    try:
        if n < 0:
            raise ValueError("negative")
        return n
    except ValueError:
        return 0


def total(xs: list[float]) -> int | float:
    t: int | float = 0
    for x in xs:
        t += x
    return t


def kernel(callback: Callable[[int], int], values: list[int]) -> int:
    s = 0
    for value in values:
        s += callback(value)
    return s


def square(value: int) -> int:
    return value * value


out = [0.0, 0.0, 0.0]
stencil([1.0, 2.0, 3.0], out)
first: list[Callable[[int], int]] = [square]
print(out, depth(3, square), lookup({"a": 1}, "a"), checked(-1), total([1.5]), kernel(first[0], [2, 3]))
"""


def line_of(fragment):
    """The line of PROGRAM that holds fragment."""
    lines = [n for n, line in enumerate(PROGRAM.split("\n"), 1) if fragment in line]
    assert len(lines) == 1, fragment
    return lines[0]


def compiled(source):
    """Each function's record as lowering takes it, with the IR check on."""
    captured = {}
    lower = Gen.lower

    def capture(g, fn):
        captured[fn.f.ll] = text.from_ifn(fn)
        lower(g, fn)

    with patch.object(Gen, "lower", capture), patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}):
        Gen().program(Loader([str(ROOT / "lib")]).program("locations.py", source))
    return captured


def operations(record):
    return [i for b in record["blocks"] for i in b["operations"]]


class StampingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.functions = compiled(PROGRAM)

    def test_every_op_and_slot_has_a_line(self):
        self.assertGreater(len(self.functions), 8)
        for symbol, record in self.functions.items():
            for i in record["slots"] + operations(record):
                with self.subTest(symbol=symbol, op=i["op"], text=i["text"]):
                    self.assertNotEqual(i["line"], 0)

    def test_a_prologue_and_its_slots_take_the_def_line(self):
        record = self.functions["@f.stencil"]
        self.assertEqual({s["line"] for s in record["slots"] if s["text"] in ("a", "b")}, {line_of("def stencil")})
        stores = [i for i in operations(record) if i["op"] == "mem.store" and i["operands"][1]["value"] in ("%a0", "%a1")]
        self.assertEqual({i["line"] for i in stores}, {line_of("def stencil")})

    def test_listguard_tests_take_the_line_of_their_loop(self):
        record = self.functions["@f.stencil"]
        loop = line_of("for i in range(1, len(a) - 1)")
        copied = {i["line"] for i in operations(record) if i["op"] == "list.store"}
        self.assertEqual(copied, {line_of("b[i] =")})  # (the loop's copy keeps its ops' lines)
        # (the tests before the copy branch to a loop's head, as its steps do, but only they
        # compare lengths and nulls there)
        heads = [lp["head"] for lp in record["loops"]]
        tests = [b for b in record["blocks"] if any(i["op"] == "cbr" and set(i["targets"]) & set(heads)
                                                     for i in b["operations"]) and b["label"] not in heads]
        guards = [i for b in tests for i in b["operations"] if i["op"] in ("list.len", "scalar.cmp", "ptr.cmp")]
        self.assertEqual(len(guards), 6)
        self.assertEqual({i["line"] for i in guards}, {loop})

    def test_depth_restorations_take_the_line_of_their_return(self):
        record = self.functions["@f.depth"]
        for b in record["blocks"]:
            for at, i in enumerate(b["operations"]):
                if i["op"] == "rt" and i["text"] == "recursion.restore":
                    self.assertEqual(b["operations"][at + 1]["op"], "ret")
                    self.assertEqual(i["line"], b["operations"][at + 1]["line"])
        restored = [i["line"] for i in operations(record) if i["text"] == "recursion.restore"]
        self.assertEqual(sorted(restored), [line_of("return f(n)"), line_of("return depth(")])
        entry = record["blocks"][0]["operations"]
        self.assertEqual([(i["op"], i["line"]) for i in entry[:2]],
                         [("rt", line_of("def depth")), ("scalar.bin", line_of("def depth"))])

    def test_fused_lookup_and_lowered_raise_take_the_line_of_their_source(self):
        found = [i for i in operations(self.functions["@f.lookup"]) if i["text"] == "dict.find"]
        self.assertEqual([i["line"] for i in found], [line_of("if k in d")])
        record = self.functions["@f.checked"]
        made = [b for b in record["blocks"] if any(i["text"] == "exc.new" for i in b["operations"])]
        self.assertEqual(len(made), 1)
        self.assertEqual({i["line"] for i in made[0]["operations"]}, {line_of("raise ValueError")})
        self.assertFalse(any(i["op"] == "raise" for i in operations(record)))

    def test_split_union_slots_take_the_line_of_the_slot_they_replace(self):
        record = self.functions["@f.total"]
        halves = [s for s in record["slots"] if s["text"] in ("t.tag", "t.pay")]
        self.assertEqual(len(halves), 2)
        self.assertEqual({s["line"] for s in halves}, {line_of("t: int | float = 0")})

    def test_a_callback_dispatcher_takes_the_def_line(self):
        record = self.functions["@f.kernel"]
        guards = [i for i in operations(record) if i["op"] == "ptr.cmp" and any(a["value"].startswith("@cvo.")
                                                                                 for a in i["operands"])]
        versions = [i for i in operations(record) if i["op"] == "call" and ".callback" in i["text"]]
        self.assertTrue(guards and versions)
        self.assertEqual({i["line"] for i in guards + versions}, {line_of("def kernel")})
        self.assertTrue(any(".callback" in symbol for symbol in self.functions))


class VerifierTests(unittest.TestCase):
    CASE = """function @f(n: int) -> None {
  %n.1 = slot name=n : int
entry:
  mem.store(&int %n.1, int %a0)
  br -> L2
L2:
  ret.none
}
"""

    def verify(self, fn):
        errors = StringIO()
        with redirect_stderr(errors):
            try:
                text.gen_for(fn).verify(fn, False)
            except SystemExit:
                return errors.getvalue()
        return ""

    def test_ir_written_without_lines_verifies(self):
        fn = text.to_ifn(text.parse_function(self.CASE))
        self.assertFalse(fn.located)
        self.assertEqual(self.verify(fn), "")

    def test_a_function_the_compiler_built_needs_every_line(self):
        fn = text.to_ifn(text.parse_function(self.CASE))
        fn.located = True
        self.assertIn("bad IR in @f, block entry: slot %n.1 has no source line", self.verify(fn))
        fn.slots[0].line = 4
        self.assertIn("bad IR in @f, block entry: mem.store has no source line", self.verify(fn))
        fn.blocks[0].code[0].line = 4
        fn.blocks[0].code[1].line = 4
        self.assertIn("bad IR in @f, block L2: ret.none has no source line", self.verify(fn))
        fn.blocks[1].code[0].line = 30000005
        self.assertEqual(self.verify(fn), "")

    def test_the_compiler_marks_its_functions(self):
        located = []
        verify = Gen.verify

        def observe(g, fn, eh):
            located.append(fn.located)
            verify(g, fn, eh)

        with patch.object(Gen, "verify", observe):
            compiled("def f(n: int) -> int:\n    return n + 1\n\nprint(f(2))\n")
        self.assertTrue(located)
        self.assertTrue(all(located))

    def test_a_pass_that_drops_a_line_fails_the_ir_check(self):
        # (the negative control: a listguard test without its loop's line)
        guard_loop = sys.modules["src.pystachy_compiler.optimizations"].guard_loop

        def unlocated(g, fn, plan):
            changed = guard_loop(g, fn, plan)
            for b in fn.blocks:
                for i in b.code:
                    if i.op == "list.len":
                        i.line = 0
            return changed

        with patch("src.pystachy_compiler.optimizations.guard_loop", unlocated), \
                redirect_stderr(StringIO()) as errors, self.assertRaises(SystemExit):
            compiled(PROGRAM)
        self.assertIn("list.len has no source line", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
