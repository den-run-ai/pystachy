"""Native recursion policy: which source functions count, and their typed guards (#988)."""
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
from src.pystachy_compiler.optimizations import recursion_cycles
from src.pystachy_compiler.specs import FXBIT


ROOT = Path(__file__).resolve().parent.parent
GUARDS = FXBIT["R"] | FXBIT["I"]


def compile_source(source, opt="", ext="", recheck=False):
    functions = {}
    lower = Gen.lower
    scope = Gen.recursionscope
    rechecked = {}

    def policy(g):
        counted = scope(g)
        if recheck:
            # The summaries the policy patched, against a complete recomputation of its IR.
            rechecked["patched"] = {f.f.ll: f.fx for f in g.fns}
            g.effects()
            rechecked["recomputed"] = {f.f.ll: f.fx for f in g.fns}
        return counted

    def capture(g, fn):
        g.verify(fn, False)
        functions[fn.f.ll] = {
            "name": fn.f.name,
            "generator": fn.f.gen,
            "counted": fn.counted,
            "rdepth": fn.rdepth,
            "fx": fn.fx,
            "blocks": [(b.label, b.handler,
                        [(i.op, i.s, g.opfx(i, fn.fa)) for i in b.code])
                       for b in fn.blocks],
            "operands": {(b.label, at): ([a.v for a in i.a], list(i.r))
                         for b in fn.blocks for at, i in enumerate(b.code)},
        }
        lower(g, fn)

    with (patch.object(Gen, "lower", capture), patch.object(Gen, "recursionscope", policy),
          patch.dict(os.environ, {"PYSTACHY_OPT": opt})):
        gen = Gen()
        gen.ext = ext
        loader = Loader([str(ROOT / "lib")])
        loader.ext = ext
        ir = gen.program(loader.program("recursion_contract.py", source))
    return (ir, functions, rechecked) if recheck else (ir, functions)


def operations(function):
    return [op for _, _, code in function["blocks"] for op in code]


def guards(function):
    return [name for op, name, _ in operations(function) if op == "rt" and name.startswith("recursion.")]


def named(functions, name):
    found = [fn for fn in functions.values() if fn["name"] == name]
    assert len(found) == 1, (name, [fn["name"] for fn in functions.values()])
    return found[0]


SHAPES = '''
from collections.abc import Callable

def leaf(n: int) -> int:
    return n * 2 + 1

def pure(n: int) -> int:
    return (n & 255) ^ 1

def direct(n: int) -> int:
    if n <= 0:
        return 0
    return direct(n - 1) + leaf(n)

def even(n: int) -> bool:
    if n == 0:
        return True
    return odd(n - 1)

def odd(n: int) -> bool:
    if n == 0:
        return False
    return even(n - 1)

class Walker:
    def step(self, n: int) -> int:
        if n == 0:
            return 0
        return 1 + self.step(n - 1)

    def value(self, n: int) -> int:
        return n

def caller(n: int) -> int:
    return direct(n) + Walker().step(n) + Walker().value(n)

def indirect(f: Callable[[int], int], n: int) -> int:
    return f(n)

identity = lambda n: n
print(caller(3), even(4), indirect(leaf, 2), identity(1), pure(3))
'''


class TypedRecursionTests(unittest.TestCase):
    def test_cycles_and_unknown_calls_count_and_other_functions_do_not(self):
        _, functions = compile_source(SHAPES)
        for name in ("direct", "even", "odd", "step", "indirect"):
            with self.subTest(counted=name):
                fn = named(functions, name)
                self.assertTrue(fn["counted"])
                self.assertEqual(guards(fn)[0], "recursion.enter")
                self.assertEqual(fn["fx"] & GUARDS, GUARDS)
        for name in ("leaf", "pure", "caller", "value", "<lambda>"):
            with self.subTest(uncounted=name):
                fn = named(functions, name)
                self.assertFalse(fn["counted"])
                self.assertEqual(guards(fn), [])
                self.assertEqual(fn["rdepth"], "")
        # An uncounted function keeps its own summary: nothing here may raise or touch runtime state.
        self.assertEqual(named(functions, "pure")["fx"], 0)

    def test_counted_entry_is_first_and_every_return_restores_the_callers_depth(self):
        _, functions = compile_source(SHAPES)
        for name in ("direct", "even", "step"):
            fn = named(functions, name)
            with self.subTest(function=name):
                entries = [(label, handler, at) for label, handler, code in fn["blocks"]
                           for at, (op, symbol, _) in enumerate(code) if (op, symbol) == ("rt", "recursion.enter")]
                self.assertEqual([(label, handler) for label, handler, _ in entries], [("entry", "")])
                label, _, at = entries[0]
                self.assertEqual(at, 0)
                active = "%t" + str(fn["operands"][(label, at)][1][0])
                self.assertEqual(fn["rdepth"], active)
                base = "%t" + str(fn["operands"][(label, 1)][1][0])
                self.assertEqual(fn["operands"][(label, 1)][0], [active, "1"])
                returns = 0
                for block, _, code in fn["blocks"]:
                    for at, (op, _, _) in enumerate(code):
                        if op in ("ret", "ret.none"):
                            returns += 1
                            self.assertEqual(code[at - 1][:2], ("rt", "recursion.restore"))
                            self.assertEqual(fn["operands"][(block, at - 1)][0], [base])
                self.assertGreater(returns, 0)

    def test_handlers_restore_the_entry_or_active_depth(self):
        _, functions = compile_source('''
def plain(n: int) -> int:
    try:
        return 10 // n
    except ZeroDivisionError:
        return -1

def recursive(n: int) -> int:
    try:
        return 10 // n if n < 2 else recursive(n - 1)
    except ZeroDivisionError:
        return -1

print(plain(0), recursive(3))
''')
        plain = named(functions, "plain")
        self.assertFalse(plain["counted"])
        self.assertEqual(guards(plain)[0], "recursion.depth")
        self.assertNotIn("recursion.enter", guards(plain))
        recursive = named(functions, "recursive")
        self.assertTrue(recursive["counted"])
        self.assertEqual(guards(recursive)[0], "recursion.enter")
        for fn in (plain, recursive):
            with self.subTest(function=fn["name"]):
                restores = [fn["operands"][(label, at)][0] for label, _, code in fn["blocks"]
                            for at, op in enumerate(code) if op[:2] == ("rt", "recursion.restore")]
                self.assertIn([fn["rdepth"]], restores)

    def test_patched_summaries_equal_a_full_recomputation(self):
        for source in (SHAPES, (ROOT / "tests/ir/effects.py").read_text(),
                       (ROOT / "tests/programs/language/recursion_guard.py").read_text()):
            _, _, rechecked = compile_source(source, opt="-all", recheck=True)
            self.assertEqual(rechecked["patched"], rechecked["recomputed"])

    def test_policy_does_not_depend_on_optimization_switches(self):
        counted = None
        for opt in ("", "-all", "-dictfuse,-listget"):
            with self.subTest(opt=opt):
                _, functions = compile_source(SHAPES, opt)
                names = sorted(fn["name"] for fn in functions.values() if fn["counted"])
                if counted is None:
                    counted = names
                self.assertEqual(names, counted)

    def test_strongly_connected_components(self):
        self.assertEqual(recursion_cycles([[1], [2], [0], [3, 4], []]), [True, True, True, True, False])
        self.assertEqual(recursion_cycles([[1], [2], []]), [False, False, False])
        self.assertEqual(recursion_cycles([[1, 2], [0], [2], [0]]), [True, True, True, False])
        chain = [[j + 1] for j in range(2999)] + [[0]]
        self.assertEqual(recursion_cycles(chain), [True] * 3000)

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
                        # (after a normal resume, the depth the entry counted from)
                        self.assertTrue(any(i[:2] == ("rt", "recursion.restore") for i in code[at + 1:]))
                        self.assertFalse(any(i[:2] == ("rt", "recursion.leave") for i in code))
        self.assertGreaterEqual(resumes, 2)

    def test_guard_helpers_use_mutable_runtime_state_and_throwing_slow_path(self):
        ir, _ = compile_source("def count(n: int) -> int:\n    return 0 if n == 0 else count(n - 1)\nprint(count(1))\n")
        self.assertIn("@pys_recursion_state = external global [2 x i64]", ir)
        helpers = dict(re.findall(r"^define internal [^@]*(@pys\.recursion\.[a-z]+)\([^\n]*\{\n(.*?)^}",
                                  ir, re.M | re.S))
        self.assertIn("@pys.recursion.enter", helpers)
        self.assertTrue(set(helpers) <= {"@pys.recursion." + name for name in ("enter", "leave", "depth", "restore")})
        for name in helpers:
            declaration = next(line for line in ir.splitlines() if line.startswith("define ") and name + "(" in line)
            # (an entry is left to LLVM's ordinary inliners; the scalar helpers are mandatory)
            self.assertEqual("alwaysinline" in declaration, name != "@pys.recursion.enter")
            self.assertEqual("nounwind" in declaration, name != "@pys.recursion.enter")
        body = helpers["@pys.recursion.enter"]
        self.assertIn("icmp sge i64 %depth, %limit", body)
        self.assertIn("call void @pys_recursion_error() noreturn cold", body)
        self.assertIn("unreachable", body)
        self.assertIn("store i64 %next, ptr @pys_recursion_state", body)
        source_body = ir.split("define internal i64 @f.count(", 1)[1].split("\n}", 1)[0]
        self.assertIn("call i64 @pys.recursion.enter()", source_body)
        self.assertRegex(source_body, r"store i64 %t\d+, ptr @pys_recursion_state, !tbaa !\d+")
        self.assertNotIn("@pys_recursion_enter", source_body)

    def test_programs_without_counted_functions_declare_no_guard(self):
        ir, _ = compile_source("def leaf(n: int) -> int:\n    return n + 1\nprint(leaf(1))\n")
        self.assertNotIn("pys.recursion.enter", ir)
        self.assertNotIn("pys_recursion_error", ir)

    def test_state_tbaa_shares_field_root_and_overflow_edge_is_cold(self):
        ir, _ = compile_source('''
class Box:
    def __init__(self, n: int) -> None:
        self.n = n

    def value(self, n: int) -> int:
        return self.n if n == 0 else self.value(n - 1)

print(Box(2).value(2))
''')
        nodes = dict(re.findall(r"^!(\d+) = (.*)$", ir, re.M))
        root = next(key for key, value in nodes.items() if value == '!{!"pystachy fields"}')
        for name in ("recursion depth", "recursion limit", "int"):
            self.assertTrue(any(value == f'!{{!"{name}", !{root}, i64 0}}'
                                for value in nodes.values()), name)
        helper = ir.split("define internal i64 @pys.recursion.enter()", 1)[1].split("\n}", 1)[0]
        self.assertRegex(helper, r"load i64, ptr @pys_recursion_state, !tbaa !\d+")
        self.assertRegex(helper, r"load i64, ptr %limit.addr, !tbaa !\d+")
        profile = re.search(r"br i1 %full, label %overflow, label %entered, !prof !(\d+)", helper)
        self.assertIsNotNone(profile)
        self.assertEqual(nodes[profile.group(1)], '!{!"branch_weights", i32 1, i32 1048575}')

    def test_runtime_callbacks_count_their_callers(self):
        _, functions = compile_source('''
class Key:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Key) and self.n == other.n

def find(items: list[Key], k: Key) -> bool:
    return k in items

print(find([Key(1), Key(2)], Key(2)))
''')
        # The runtime's search runs Key.__eq__: a call the direct graph does not show, so the
        # function making it counts. The method itself calls nothing it cannot see, so it
        # cannot be entered again while it is active and does not.
        self.assertTrue(named(functions, "find")["counted"])
        self.assertFalse(named(functions, "__eq__")["counted"])

    def test_descriptor_raise_effects_remain_distinct_from_source_entry(self):
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
