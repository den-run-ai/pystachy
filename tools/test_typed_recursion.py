"""Native recursion policy survives typed lowering and helper inlining."""
from pathlib import Path
import os
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


def compile_source(source, opt=""):
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

    with patch.object(Gen, "lower", capture), patch.dict(os.environ, {"PYSTACHY_OPT": opt}):
        ir = Gen().program(Loader([str(ROOT / "lib")]).program("recursion_contract.py", source))
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
''', opt="-recursionleaf")
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
        ir, _ = compile_source("def identity(n: int) -> int:\n    return n\nprint(identity(1))\n",
                               opt="-recursionleaf")
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
        self.assertRegex(source_body, r"store i64 %t\d+, ptr @pys_recursion_state, !tbaa !\d+")
        self.assertNotIn("call void @pys.recursion.restore", source_body)
        self.assertNotIn("@pys_recursion_enter", source_body)

    def test_leaf_keeps_entry_failure_without_publishing_depth(self):
        ir, functions = compile_source('''
class Counter:
    def __init__(self, value: int) -> None:
        self.value = value

    def update(self, delta: int) -> int:
        self.value += delta
        return self.value

def allocated(n: int) -> list[int]:
    return [n, n + 1]

print(Counter(1).update(2), allocated(3))
''')
        for fn in functions.values():
            if fn["name"] not in ("__init__", "update", "allocated"):
                continue
            with self.subTest(function=fn["name"]):
                recursion = [name for op, name, _ in operations(fn)
                             if op == "rt" and name.startswith("recursion.")]
                self.assertEqual(recursion, ["recursion.check"])
                self.assertEqual(fn["fx"] & (FXBIT["R"] | FXBIT["I"]),
                                 FXBIT["R"] | FXBIT["I"])
        body = ir.split("define internal void @pys.recursion.check()", 1)[1].split("\n}", 1)[0]
        self.assertIn("icmp sge i64 %depth, %limit", body)
        self.assertIn("@pys_recursion_error() noreturn cold", body)
        self.assertNotIn("store ", body)
        self.assertNotIn("nounwind", body.split("{", 1)[0])

    def test_calls_and_limit_observers_keep_published_depth(self):
        _, functions = compile_source('''
import sys
from collections.abc import Callable

def leaf(n: int) -> int:
    return n + 1

def direct(n: int) -> int:
    return leaf(n)

def indirect(f: Callable[[int], int], n: int) -> int:
    return f(n)

def limit(n: int) -> int:
    sys.setrecursionlimit(n)
    return sys.getrecursionlimit()

def cleanup(n: int) -> int:
    try:
        return n // 2
    finally:
        sys.setrecursionlimit(1000)

print(direct(1), indirect(leaf, 1), limit(1000), cleanup(2))
''')
        for name in ("direct", "indirect", "limit", "cleanup"):
            with self.subTest(function=name):
                code = operations(functions["@f." + name])
                self.assertTrue(any(op[:2] == ("rt", "recursion.enter") for op in code))
                self.assertTrue(any(op[:2] == ("rt", "recursion.restore") for op in code))
                self.assertFalse(any(op[:2] == ("rt", "recursion.check") for op in code))

    def test_dynamic_files_preserve_entire_guarded_ir(self):
        # An unrelated scalar leaf can also change the enclosing native frame's
        # register allocation. Protect the whole program, not just the file owner.
        source = (ROOT / "tests/programs/runtime/rt_list_vacated.py").read_text() + '''
def scalar(n: int) -> int:
    return n + 1
print(scalar(2))
'''
        ir, functions = compile_source(source)
        guarded, _ = compile_source(source, opt="-recursionleaf")
        self.assertIn("@pys_open(", ir)
        self.assertEqual(ir, guarded)
        self.assertTrue(any(op[:2] == ("rt", "recursion.enter")
                            for op in operations(functions["@f.scalar"])))

    def test_weakrefs_preserve_entire_guarded_ir(self):
        source = '''
from _weakref import ref

class Item:
    def __init__(self, value: int) -> None:
        self.value = value

def scalar(n: int) -> int:
    return n + 1

item = Item(1)
weak = ref(item)
print(scalar(2), weak() is item)
'''
        ir, functions = compile_source(source)
        guarded, _ = compile_source(source, opt="-recursionleaf")
        self.assertIn("@pys_weakref_new(", ir)
        self.assertEqual(ir, guarded)
        self.assertTrue(any(op[:2] == ("rt", "recursion.enter")
                            for op in operations(functions["@f.scalar"])))

    def test_standard_streams_do_not_disable_scalar_leaf_elision(self):
        ir, functions = compile_source('''
import sys

def scalar(n: int) -> int:
    return n + 1

print(scalar(2))
sys.stdout.write("done\\n")
''')
        self.assertIn("@pys_std(", ir)
        self.assertNotIn("@pys_open(", ir)
        recursion = [name for op, name, _ in operations(functions["@f.scalar"])
                     if op == "rt" and name.startswith("recursion.")]
        self.assertEqual(recursion, ["recursion.check"])

    def test_state_tbaa_shares_field_root_and_overflow_edge_is_cold(self):
        ir, _ = compile_source('''
class Box:
    def __init__(self, n: int) -> None:
        self.n = n

    def value(self) -> int:
        return self.n

print(Box(2).value())
''')
        nodes = dict(re.findall(r"^!(\d+) = (.*)$", ir, re.M))
        root = next(key for key, value in nodes.items() if value == '!{!"pystachy fields"}')
        for name in ("recursion depth", "recursion limit", "int"):
            self.assertTrue(any(value == f'!{{!"{name}", !{root}, i64 0}}'
                                for value in nodes.values()), name)
        helpers = ir.split("define internal void @pys.recursion.check()", 1)[1].split("\n}", 1)[0]
        self.assertRegex(helpers, r"load i64, ptr @pys_recursion_state, !tbaa !\d+")
        self.assertRegex(helpers, r"load i64, ptr %limit.addr, !tbaa !\d+")
        profile = re.search(r"br i1 %full, label %overflow, label %entered, !prof !(\d+)", helpers)
        self.assertIsNotNone(profile)
        self.assertEqual(nodes[profile.group(1)], '!{!"branch_weights", i32 1, i32 1048575}')

    def test_custom_exception_and_termination_callbacks_keep_depth(self):
        _, functions = compile_source('''
class Error(Exception):
    def __str__(self) -> str:
        return "custom"

def fail(e: Error) -> None:
    raise e

try:
    fail(Error())
except Error:
    pass
''')
        self.assertTrue(any(op[:2] == ("rt", "recursion.enter")
                            for op in operations(functions["@f.fail"])))
        _, functions = compile_source('''
import atexit

def leaf(n: int) -> int:
    return n + 1

def done() -> None:
    print("done")

atexit.register(done)
print(leaf(2))
''')
        self.assertTrue(any(op[:2] == ("rt", "recursion.enter")
                            for op in operations(functions["@f.leaf"])))

    def test_promoting_numeric_queries_preserve_callback_depth(self):
        _, functions = compile_source('''
# pystachy: dynamic-any
# pystachy: python-int
from typing import Any
import sys

class Key:
    def __eq__(self, other: Any) -> bool:
        sys.setrecursionlimit(1000)
        return True

    def __hash__(self) -> int:
        sys.setrecursionlimit(1000)
        return 1

def sequence(items: list[int], query: Any) -> bool:
    return query in items

def mapping(items: dict[int, int], query: Any) -> bool:
    return query in items

query: Any = Key()
print(sequence([1], query), mapping({1: 2}, query))
''')
        for name in ("sequence", "mapping"):
            self.assertTrue(any(op[:2] == ("rt", "recursion.enter")
                                for op in operations(functions["@f." + name])), name)

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
