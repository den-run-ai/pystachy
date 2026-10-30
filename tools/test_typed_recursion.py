"""Native recursion policy survives typed lowering and helper inlining."""
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.driver import runtime_ir
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import FXBIT


ROOT = Path(__file__).resolve().parent.parent


def compile_source(source):
    functions = {}
    lower = Gen.lower

    def capture(g, fn):
        g.verify(fn, False)
        functions[fn.f.ll] = {
            "name": fn.f.name,
            "generator": fn.f.gen,
            "fx": fn.fx,
            "blocks": [(b.label, b.handler,
                        [(i.op, i.s, g.opfx(i, fn.fa)) for i in b.code])
                       for b in fn.blocks],
            "operands": {(b.label, at): ([a.v for a in i.a], list(i.r))
                         for b in fn.blocks for at, i in enumerate(b.code)},
        }
        lower(g, fn)

    with patch.object(Gen, "lower", capture):
        ir = Gen().program(Loader([]).program("recursion_contract.py", source))
    return ir, functions


def operations(function):
    return [op for _, _, code in function["blocks"] for op in code]


class TypedRecursionTests(unittest.TestCase):
    def test_source_entries_count_once_and_normal_returns_release(self):
        _, functions = compile_source('''
def choose(n: int) -> int:
    if n == 0:
        return 1
    return choose(n - 1)

def guarded(n: int) -> int:
    try:
        return choose(n)
    except RecursionError:
        return -1

class Box:
    def value(self, n: int) -> int:
        return n

identity = lambda n: n
print(guarded(2), Box().value(2), identity(1))
''')
        wanted = {"choose", "guarded", "value", "<lambda>"}
        found = set()
        for fn in functions.values():
            if fn["name"] not in wanted:
                continue
            found.add(fn["name"])
            with self.subTest(function=fn["name"]):
                entries = [(label, handler) for label, handler, code in fn["blocks"]
                           for op, name, _ in code if (op, name) == ("rt", "recursion.enter")]
                self.assertEqual(entries, [("entry", "")])
                self.assertEqual(fn["fx"] & (FXBIT["R"] | FXBIT["I"]),
                                 FXBIT["R"] | FXBIT["I"])
                enter_at = next((label, at) for label, _, code in fn["blocks"]
                                for at, op in enumerate(code) if op[:2] == ("rt", "recursion.enter"))
                active = "%t" + str(fn["operands"][enter_at][1][0])
                bases = [fn["operands"][(label, at)][1] for label, _, code in fn["blocks"]
                         for at, op in enumerate(code) if op[:2] == ("scalar.bin", "sub")
                         and fn["operands"][(label, at)][0] == [active, "1"]]
                self.assertEqual(len(bases), 1)
                base = "%t" + str(bases[0][0])
                returns = 0
                for label, _, code in fn["blocks"]:
                    for at, (op, _, _) in enumerate(code):
                        if op in ("ret", "ret.none"):
                            returns += 1
                            self.assertGreater(at, 0)
                            self.assertEqual(code[at - 1][:2], ("rt", "recursion.restore"))
                            self.assertEqual(fn["operands"][(label, at - 1)][0], [base])
                self.assertGreater(returns, 0)
                if fn["name"] == "guarded":
                    self.assertTrue(any(op[:2] == ("rt", "recursion.restore")
                                        and fn["operands"][(label, at)][0] == [active]
                                        for label, _, code in fn["blocks"]
                                        for at, op in enumerate(code)))
        self.assertEqual(found, wanted)
        guarded = functions["@f.guarded"]
        self.assertTrue(any(op[:2] == ("rt", "recursion.restore") for op in operations(guarded)))

    def test_runtime_subset_does_not_consume_source_depth(self):
        ir = runtime_ir("recursion_runtime.py", "def pys_probe(n: int) -> int:\n    return n + 1\n", False)
        self.assertIn("define i64 @pys_probe", ir)
        self.assertNotIn("pys_recursion", ir)
        self.assertNotIn("pys.recursion", ir)

    def test_generator_creation_is_excluded_and_active_resumes_count(self):
        _, functions = compile_source('''
from collections.abc import Iterator

def values() -> Iterator[int]:
    try:
        yield 1
        yield 2
    finally:
        print("done")

g = values()
print(next(g))
g.close()
''')
        bodies = [fn for fn in functions.values() if fn["name"] == "values"]
        self.assertEqual(len(bodies), 1)
        self.assertTrue(bodies[0]["generator"])
        body = operations(bodies[0])
        self.assertFalse(any(op[:2] == ("rt", "recursion.enter") for op in body))
        self.assertTrue(any(op[:2] == ("rt", "recursion.depth") for op in body))
        self.assertTrue(any(op[:2] == ("rt", "recursion.restore") for op in body))
        resumes = 0
        for fn in functions.values():
            for _, _, code in fn["blocks"]:
                for at, (op, _, _) in enumerate(code):
                    if op == "gen.resume":
                        resumes += 1
                        self.assertTrue(any(i[:2] == ("rt", "recursion.enter") for i in code[:at]))
                        self.assertTrue(any(i[:2] == ("rt", "recursion.leave") for i in code[at + 1:]))
        self.assertGreaterEqual(resumes, 2)

    def test_inline_guards_use_mutable_runtime_state_and_throwing_slow_path(self):
        ir, _ = compile_source("def identity(n: int) -> int:\n    return n\nprint(identity(1))\n")
        self.assertIn("@pys_recursion_state = external global [2 x i64]", ir)
        helpers = dict(re.findall(r"^define internal [^@]*(@pys\.recursion\.[a-z]+)\([^\n]*\{\n(.*?)^}",
                                  ir, re.M | re.S))
        self.assertTrue({"@pys.recursion.enter", "@pys.recursion.restore"}.issubset(helpers))
        self.assertNotIn("@pys.recursion.leave", helpers)
        for name in helpers:
            declaration = next(line for line in ir.splitlines() if line.startswith("define ") and name + "(" in line)
            self.assertIn("alwaysinline", declaration)
        entry = next(line for line in ir.splitlines() if line.startswith("define ") and "@pys.recursion.enter(" in line)
        self.assertNotIn("nounwind", entry)
        self.assertIn("call void @pys_recursion_error() noreturn", helpers["@pys.recursion.enter"])
        self.assertIn("unreachable", helpers["@pys.recursion.enter"])
        self.assertIn("load i64, ptr @pys_recursion_state", helpers["@pys.recursion.enter"])
        self.assertIn("store i64", helpers["@pys.recursion.enter"])
        self.assertIn("store i64", helpers["@pys.recursion.restore"])
        source_body = ir.split("define internal i64 @f.identity(", 1)[1].split("\n}", 1)[0]
        self.assertIn("call i64 @pys.recursion.enter()", source_body)
        self.assertIn("call void @pys.recursion.restore(i64", source_body)
        self.assertNotIn("@pys_recursion_enter", source_body)

    def test_descriptor_raise_effects_remain_distinct_from_source_entry(self):
        # Aggregate source summaries now always include R. Keep the recursive
        # descriptor distinction checked at its operation, where it controls EH.
        _, functions = compile_source((ROOT / "tests/ir/recursive_effects.py").read_text())
        for name, operation, raises in (("rec_eq", "eq", True), ("plain_eq", "eq", False),
                                         ("rec_in", "list.find", True), ("plain_in", "list.find", False),
                                         ("rec_count", "list.count", True), ("plain_count", "list.count", False),
                                         ("rec_repr", "repr", True), ("plain_repr", "repr", False),
                                         ("rec_store", "dict.set", False), ("rec_has", "dict.has", False)):
            with self.subTest(function=name):
                effects = [fx for op, symbol, fx in operations(functions["@f." + name])
                           if (op, symbol) == ("rt", operation)]
                self.assertEqual(len(effects), 1)
                self.assertEqual(bool(effects[0] & FXBIT["R"]), raises)


if __name__ == "__main__":
    unittest.main()
