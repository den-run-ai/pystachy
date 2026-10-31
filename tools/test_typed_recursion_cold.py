"""Delayed depth publication preserves entry failures and terminal callbacks."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Ins, Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.optimizations import recursion_cold
from src.pystachy_compiler.syntax import Node

ROOT = Path(__file__).resolve().parent.parent


def compiled(source, opt=""):
    found = {}
    lower = Gen.lower

    def capture(g, fn):
        g.verify(fn, False)
        found[fn.f.name] = deepcopy(fn)
        lower(g, fn)

    with patch.object(Gen, "lower", capture), patch.dict(os.environ, {"PYSTACHY_OPT": opt}):
        Gen().program(Loader([str(ROOT / "lib")]).program("cold_contract.py", source))
    return found


def successors(fn, block):
    end = block.code[-1]
    out = list(end.b)
    if end.op == "check":
        out.append(fn.cold[end.x or end.s])
    return out


SOURCE = '''
seen: list[int] = [0]
def callback(n: int) -> None:
    print(n)
def candidate(n: int) -> int:
    seen[0] += 1
    if n < 0:
        callback(1 if n < -5 else 2)
        while n < -2:
            callback(n)
            n += 1
        raise ValueError("negative")
    if n == 0:
        callback(3)
        raise ValueError("zero")
    return n + 1
print(candidate(4))
'''


class ColdRecursionTests(unittest.TestCase):
    def test_every_callback_path_publishes_once_and_returns_publish_never(self):
        fn = compiled(SOURCE)["candidate"]
        self.assertEqual((fn.blocks[0].code[0].op, fn.blocks[0].code[0].s),
                         ("rt", "recursion.check"))
        self.assertFalse(any(i.op == "rt" and i.s == "recursion.restore"
                             for b in fn.blocks for i in b.code))
        blocks = {b.label: b for b in fn.blocks}
        todo = [("entry", 0)]
        visited = set()
        calls = returns = publications = 0
        while todo:
            label, active = todo.pop()
            if (label, active) in visited:
                continue
            visited.add((label, active))
            block = blocks[label]
            for op in block.code:
                if op.op == "rt" and op.s == "recursion.enter":
                    self.assertEqual(active, 0, "depth published twice on one path")
                    active = 1
                    publications += 1
                if op.op == "call" and op.s == "@f.callback":
                    self.assertEqual(active, 1, "callback observes an omitted frame")
                    calls += 1
                if op.op in ("ret", "ret.none"):
                    self.assertEqual(active, 0, "normal path acquired unbalanced depth")
                    returns += 1
            todo.extend((target, active) for target in successors(fn, block))
        self.assertGreaterEqual(calls, 2)
        self.assertGreaterEqual(publications, 2)
        self.assertGreater(returns, 0)

    def test_returning_observers_handlers_and_terminal_entries_stay_guarded(self):
        functions = compiled('''
def callback() -> None:
    print("callback")
def returning(n: int) -> int:
    if n < 0:
        callback()
    return n
def handled(n: int) -> int:
    if n < 0:
        try:
            callback()
        finally:
            print("cleanup")
        raise ValueError("bad")
    return n
def looped(n: int) -> int:
    while n > 0:
        callback()
        n -= 1
    return n
def always(n: int) -> int:
    callback()
    raise ValueError("bad")
print(returning(1), handled(1), looped(1))
try:
    always(1)
except ValueError:
    print("caught")
''')
        for name in ("returning", "handled", "looped", "always"):
            with self.subTest(name=name):
                self.assertEqual(functions[name].blocks[0].code[0].s, "recursion.enter")

    def test_generators_and_termination_hooks_remain_boundaries(self):
        source = '''
from collections.abc import Iterator
def values() -> Iterator[int]:
    yield 1
def candidate(n: int) -> int:
    if n < 0:
        for value in values():
            print(value)
        raise ValueError("bad")
    return n
print(candidate(1))
'''
        self.assertEqual(compiled(source)["candidate"].blocks[0].code[0].s, "recursion.enter")
        self.assertEqual(compiled("import atexit\n" + SOURCE)["candidate"].blocks[0].code[0].s,
                         "recursion.enter")

    def test_disabled_pass_and_recorded_boundary_fixture(self):
        self.assertEqual(compiled(SOURCE, "-recursionleaf")["candidate"].blocks[0].code[0].s,
                         "recursion.enter")
        source = (ROOT / "tests/programs/language/recursion_cold.py").read_text()
        functions = compiled(source)
        for name in ("cold", "cold_limit"):
            self.assertEqual(functions[name].blocks[0].code[0].s, "recursion.check")
        self.assertEqual(functions["one_spare"].blocks[0].code[0].s, "recursion.enter")

    def test_split_edges_repair_phi_predecessors(self):
        # Both predecessors can return normally or enter the same terminal phi.
        # Publishing in that shared target would be safe here, but edge splitting
        # must also preserve each phi's distinct incoming value and predecessor.
        g = Gen()
        fn = IFn(FnInfo("candidate", "@f.candidate", Node("def", "candidate", 1), ""))
        callback = IFn(FnInfo("callback", "@f.callback", Node("def", "callback", 1), ""))
        callback.counted = True
        g.fns = [fn, callback]
        g.fll = {"@f.candidate": 0, "@f.callback": 1}
        fn.counted = True
        fn.rdepth = "%t1"
        fn.n = 20
        enter = Ins("rt", "int", "recursion.enter")
        enter.r = [1]
        base = Ins("scalar.bin", "int", "sub")
        base.r = [2]
        base.a = [Val("%t1", "int"), Val("1", "int")]
        branch = Ins("cbr", "", "")
        branch.a = [Val("true", "bool")]
        branch.b = ["L1", "L2"]
        fn.blocks[0].code = [enter, base, branch]
        for label in ("L1", "L2"):
            b = Blk(label)
            end = Ins("cbr", "", "")
            end.a = [Val("true", "bool")]
            end.b = ["L3", "L4"]
            b.code = [end]
            fn.blocks.append(b)
        terminal = Blk("L3")
        phi = Ins("phi", "int", "")
        phi.r = [3]
        phi.a = [Val("10", "int"), Val("20", "int")]
        phi.b = ["L1", "L2"]
        call = Ins("call", "None", "@f.callback")
        terminal.code = [phi, call, Ins("unreachable", "", "")]
        normal = Blk("L4")
        normal.code = [Ins("ret.none", "", "")]
        fn.blocks.extend([terminal, normal])
        self.assertTrue(recursion_cold(g, fn, "%t2", [16, 0]))
        self.assertNotEqual(phi.b, ["L1", "L2"])
        self.assertEqual([v.v for v in phi.a], ["10", "20"])
        blocks = {b.label: b for b in fn.blocks}
        for original, bridge in zip(("L1", "L2"), phi.b, strict=True):
            self.assertEqual(blocks[original].code[-1].b[0], bridge)
            self.assertEqual(blocks[bridge].code[0].s, "recursion.enter")
            self.assertEqual(blocks[bridge].code[-1].b, ["L3"])


if __name__ == "__main__":
    unittest.main()
