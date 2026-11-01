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
            "closed": fn.f.ll in g.rdpass,
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

def through(f: Callable[[int], int], n: int) -> int:
    if n <= 0:
        return f(0)
    return through(f, n - 1) + 1

identity = lambda n: n
print(caller(3), even(4), indirect(leaf, 2), through(leaf, 2), identity(1), pure(3))
'''


class TypedRecursionTests(unittest.TestCase):
    def test_cycles_and_unknown_calls_count_and_other_functions_do_not(self):
        _, functions = compile_source(SHAPES)
        for name in ("direct", "even", "odd", "step", "indirect", "through"):
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
        for name in ("indirect", "through"):
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

    def test_closed_recursion_counts_in_a_register(self):
        ir, functions = compile_source(SHAPES)
        # direct, even and odd, and step call only each other and functions that cannot recur;
        # indirect and through call a function value, which could run anything
        self.assertEqual(sorted(fn["name"] for fn in functions.values() if fn["closed"]),
                         ["direct", "even", "odd", "step"])
        for name in ("direct", "even", "odd", "step"):
            fn = named(functions, name)
            with self.subTest(function=name):
                self.assertTrue(fn["counted"])
                # (the typed entry stays; lowering checks the depth argument and restores nothing)
                self.assertEqual(guards(fn), ["recursion.enter"])
                self.assertEqual(fn["fx"] & GUARDS, GUARDS)
        body = ir.split("define internal i64 @r.f.direct(i64 %a0, i64 %rd) {", 1)[1].split("\n}", 1)[0]
        self.assertRegex(body, r"%t\d+ = call i64 @pys.recursion.check\(i64 %rd\)")
        self.assertRegex(body, r"call i64 @r\.f\.direct\(i64 %t\d+, i64 %t\d+\)")
        self.assertNotIn("@pys_recursion_state", body)
        self.assertNotIn("@f.direct(", body)
        wrapper = ir.split("define internal i64 @f.direct(i64 %a0) {", 1)[1].split("\n}", 1)[0]
        self.assertRegex(wrapper, r"%rd = load i64, ptr @pys_recursion_state, !tbaa !\d+")
        self.assertIn("call i64 @r.f.direct(i64 %a0, i64 %rd)", wrapper)
        self.assertNotIn("store", wrapper)
        even = re.search(r"^define internal \S+ @r\.f\.even\(i64 %a0, i64 %rd\) \{\n(.*?)^}", ir, re.M | re.S)
        self.assertIsNotNone(even)
        self.assertRegex(even.group(1), r"call \S+ @r\.f\.odd\(i64 %t\d+, i64 %t\d+\)")
        # (callers outside a cycle call its symbol, which reads the depth word)
        caller = ir.split("define internal i64 @f.caller(", 1)[1].split("\n}", 1)[0]
        self.assertIn("call i64 @f.direct(", caller)
        self.assertNotIn("@r.", caller)

    def test_closed_recursion_excludes_cycles_that_reach_other_depth_users(self):
        _, functions = compile_source('''
import sys
from collections.abc import Iterator

def inner(n: int) -> int:
    return 0 if n == 0 else inner(n - 1) + 1

def outer(n: int) -> int:
    return 0 if n == 0 else outer(n - 1) + inner(n)

def limited(n: int) -> int:
    if n == 0:
        sys.setrecursionlimit(sys.getrecursionlimit())
        return 0
    return limited(n - 1)

def setter() -> None:
    sys.setrecursionlimit(sys.getrecursionlimit())

def indirectly(n: int) -> int:
    if n == 0:
        setter()
        return 0
    return indirectly(n - 1)

def walk(n: int) -> Iterator[int]:
    yield n
    if n > 0:
        yield from walk(n - 1)

def consume(n: int) -> int:
    if n == 0:
        return 0
    t = consume(n - 1)
    for v in walk(n):
        t += v
    return t

def pair(n: int) -> tuple[int, int]:
    return (0, 0) if n == 0 else pair(n - 1)

print(outer(3), limited(2), indirectly(2), consume(2), pair(2))
''')
        self.assertTrue(named(functions, "inner")["closed"])
        # outer reaches inner, which counts in a cycle of its own; limited and indirectly reach
        # sys.setrecursionlimit, which compares the depth word with the new limit; consume
        # resumes generators whose body can recur; pair's tuple may come back by value
        for name in ("outer", "limited", "indirectly", "consume", "pair"):
            with self.subTest(function=name):
                fn = named(functions, name)
                self.assertTrue(fn["counted"])
                self.assertFalse(fn["closed"])
        self.assertFalse(named(functions, "setter")["counted"])

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
        def components(calls):
            comp = [-1] * len(calls)
            cyclic = recursion_cycles(calls, comp)
            groups = {}
            for j, c in enumerate(comp):
                groups.setdefault(c, []).append(j)
            return cyclic, sorted(groups.values())
        self.assertEqual(components([[1], [2], [0], [3, 4], []]),
                         ([True, True, True, True, False], [[0, 1, 2], [3], [4]]))
        self.assertEqual(components([[1], [2], []]), ([False, False, False], [[0], [1], [2]]))
        self.assertEqual(components([[1, 2], [0], [2], [0]]),
                         ([True, True, True, False], [[0, 1], [2], [3]]))
        # (two cycles joined by a call stay apart)
        self.assertEqual(components([[1], [0, 2], [3], [2]]), ([True] * 4, [[0, 1], [2, 3]]))
        chain = [[j + 1] for j in range(2999)] + [[0]]
        self.assertEqual(components(chain), ([True] * 3000, [list(range(3000))]))

    def test_runtime_subset_does_not_consume_source_depth(self):
        ir = runtime_ir("recursion_runtime.py", "def pys_probe(n: int) -> int:\n    return n + 1\n", False)
        self.assertIn("define i64 @pys_probe", ir)
        self.assertNotIn("pys_recursion", ir)
        self.assertNotIn("pys.recursion", ir)

    def test_generator_creation_is_excluded_and_active_resumes_count(self):
        _, functions = compile_source('''
from collections.abc import Iterator

def values(n: int) -> Iterator[int]:
    try:
        yield n
        if n > 0:
            yield from values(n - 1)
    finally:
        print("done")

g = values(2)
print(next(g))
g.close()
''')
        bodies = [fn for fn in functions.values() if fn["name"] == "values"]
        self.assertEqual(len(bodies), 1)
        self.assertTrue(bodies[0]["generator"])
        body = operations(bodies[0])
        # A body counts nothing itself: its only entries are those of its own resumes (yield from).
        entries = [op for op in body if op[:2] == ("rt", "recursion.enter")]
        own = [op for op in body if op[0] == "gen.resume"]
        self.assertGreater(len(own), 0)
        self.assertEqual(len(entries), len(own))
        self.assertTrue(any(op[:2] == ("rt", "recursion.depth") for op in body))
        self.assertTrue(any(op[:2] == ("rt", "recursion.restore") for op in body))
        resumes = 0
        for fn in functions.values():
            code = operations(fn)
            own = len([op for op in code if op[0] == "gen.resume"])
            if own == 0:
                continue
            resumes += own
            # each resume enters (exception lowering may end its block with that invoke), and the
            # function's own entry counts too where it counts
            entries = len([op for op in code if op[:2] == ("rt", "recursion.enter")])
            self.assertEqual(entries, own + (1 if fn["counted"] else 0), fn["name"])
            # (after a normal resume, the depth the entry counted from; no load-and-decrement)
            self.assertGreaterEqual(len([op for op in code if op[:2] == ("rt", "recursion.restore")]), own)
            self.assertFalse(any(op[:2] == ("rt", "recursion.leave") for op in code))
        self.assertGreaterEqual(resumes, 2)

    def test_resumes_count_only_generator_bodies_that_can_recur(self):
        _, functions = compile_source('''
from collections.abc import Iterator

def squares(n: int) -> Iterator[int]:
    for i in range(n):
        yield i * i

def total(n: int) -> int:
    t = 0
    for v in squares(n):
        t += v
    return t

class Tree:
    def __init__(self, left: "Tree | None", value: str) -> None:
        self.left = left
        self.value = value

def walk(t: Tree) -> Iterator[str]:
    if t.left is not None:
        yield from walk(t.left)
    yield t.value

def names(t: Tree) -> list[str]:
    out: list[str] = []
    for name in walk(t):
        out.append(name)
    return out

print(total(4), names(Tree(Tree(None, "a"), "b")))
''')
        def resumes(fn):
            found = []
            for _, _, code in fn["blocks"]:
                for at, (op, _, _) in enumerate(code):
                    if op == "gen.resume":
                        found.append(any(i[:2] == ("rt", "recursion.enter") for i in code[:at]))
            return found
        # A plain generator's body cannot be entered again while it runs: its resumes do not
        # count, and its consumer, which no longer reaches unseen code, does not either.
        total = named(functions, "total")
        self.assertEqual(resumes(total), [False])
        self.assertFalse(total["counted"])
        self.assertEqual(guards(total), [])
        # walk resumes walk generators: those resumes count, inside the body and outside it.
        self.assertTrue(all(resumes(named(functions, "walk"))))
        self.assertTrue(resumes(named(functions, "walk")))
        self.assertTrue(all(resumes(named(functions, "names"))))
        self.assertTrue(resumes(named(functions, "names")))

    def test_guard_helpers_use_mutable_runtime_state_and_throwing_slow_path(self):
        # (a cycle through a function value keeps the depth word current: closed recursion does not)
        ir, _ = compile_source("from collections.abc import Callable\n"
                               "def count(n: int, f: Callable[[int], int]) -> int:\n"
                               "    return f(n) if n == 0 else count(n - 1, f)\n"
                               "print(count(1, lambda k: k))\n")
        self.assertIn("@pys_recursion_state = external global [2 x i64]", ir)
        helpers = dict(re.findall(r"^define internal [^@]*(@pys\.recursion\.[a-z]+)\([^\n]*\{\n(.*?)^}",
                                  ir, re.M | re.S))
        self.assertIn("@pys.recursion.enter", helpers)
        self.assertTrue(set(helpers) <= {"@pys.recursion." + name for name in ("enter", "leave", "depth", "restore")})
        self.assertRegex(helpers["@pys.recursion.enter"], r"load i64, ptr @pys_recursion_state, !tbaa !\d+")
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

    def test_closed_recursion_helper_checks_without_storing(self):
        ir, _ = compile_source("def count(n: int) -> int:\n    return 0 if n == 0 else count(n - 1)\nprint(count(1))\n")
        helpers = dict(re.findall(r"^define internal [^@]*(@pys\.recursion\.[a-z]+)\([^\n]*\{\n(.*?)^}",
                                  ir, re.M | re.S))
        # (no op calls the entry helper, so the module leaves it out)
        self.assertEqual(set(helpers), {"@pys.recursion.check"})
        declaration = next(line for line in ir.splitlines() if line.startswith("define internal i64 @pys.recursion.check("))
        self.assertNotIn("alwaysinline", declaration)
        body = helpers["@pys.recursion.check"]
        self.assertIn("icmp sge i64 %depth, %limit", body)
        self.assertIn("call void @pys_recursion_error() noreturn cold", body)
        self.assertIn("%next = add i64 %depth, 1", body)
        self.assertNotIn("store", body)
        self.assertNotIn("@pys_recursion_enter", ir.split("define internal i64 @r.f.count(", 1)[1].split("\n}", 1)[0])

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
        # (Box.value is closed recursion: its check reads the limit, its symbol the depth)
        helper = ir.split("define internal i64 @pys.recursion.check(i64 %depth)", 1)[1].split("\n}", 1)[0]
        self.assertRegex(helper, r"load i64, ptr %limit.addr, !tbaa !\d+")
        self.assertRegex(ir, r"%rd = load i64, ptr @pys_recursion_state, !tbaa !\d+")
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
