"""The nullcheck pass removes the null checks that a passed test of the same value makes redundant."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader

SOURCE = '''
class Node:
    def __init__(self, v: int, nxt: "Node | None") -> None:
        self.v = v
        self.nxt = nxt

def repeated(a: Node | None) -> int:
    return a.v + a.v * a.v

def one_branch(a: Node | None, c: bool) -> int:
    t = 0
    if c:
        t = a.v
    return t + a.v

def zero_trips(a: Node | None, n: int) -> int:
    t = 0
    for i in range(n):
        t += a.v + a.v
    return t + a.v

def handled(a: Node | None) -> int:
    x = 0
    try:
        x = a.v
    except AttributeError:
        x = -1
    return x + a.v

def tested(n: Node | None) -> int:
    t = 0
    while n is not None:
        t += n.v + n.v
        n = n.nxt
    return t

def reassigned(a: Node | None, b: Node | None) -> int:
    x = a
    t = x.v
    x = b
    return t + x.v

def written(a: Node | None) -> int:
    def clear() -> None:
        nonlocal a
        a = None
    t = a.v
    clear()
    return t + a.v

def resumed(a: Node | None):
    yield a.v
    yield a.v

n = Node(1, Node(2, None))
print(repeated(n), one_branch(n, True), zero_trips(n, 2), handled(n), tested(n), reassigned(n, n), written(n), list(resumed(n)))
'''


def null_checks(ops):
    # the checks of a ptr.cmp of a value with null, among a function's ops
    tests = {f"%t{i.r[0]}" for i in ops if i.op == "ptr.cmp" and i.s == "==" and "null" in (i.a[0].v, i.a[1].v)}
    return len([i for i in ops if i.op == "check" and i.a[0].v in tests])


def compiled(off=False):
    # each function's ops, as lowering gets them (after the passes), each function verified
    captured = {}
    lower = Gen.lower

    def capture(g, fn):
        g.verify(fn, True)
        captured[fn.f.name] = [i for b in fn.blocks for i in b.code]
        lower(g, fn)

    env = {"PYSTACHY_OPT": "-nullcheck" if off else ""}
    with patch.object(Gen, "lower", capture), patch.dict(os.environ, env):
        Gen().program(Loader([]).program("nullcheck.py", SOURCE))
    return captured


class NullCheckTests(unittest.TestCase):
    def test_a_check_goes_only_where_a_passed_test_of_the_same_value_dominates_it(self):
        off = compiled(True)
        on = compiled()
        # function: checks without the pass, checks with it
        expected = {
            "repeated": (3, 1),  # the first read checks a; the others need not
            "one_branch": (2, 2),  # the read after the if: c may have been false
            "zero_trips": (3, 2),  # the loop's second read goes, the read after the loop stays
            "handled": (2, 2),  # the handler's way to the read after the try checks nothing
            "tested": (3, 0),  # the loop's test of n leads to the reads of n
            "reassigned": (2, 2),  # x holds another value at its second read
            "written": (2, 2),  # clear() may assign a (a cell): the second read checks it again
            "resumed": (2, 1),  # a parameter stays what was passed across a yield
        }
        for name, (before, after) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(null_checks(off[name]), before)
                self.assertEqual(null_checks(on[name]), after)

    def test_a_cold_block_no_check_goes_to_goes_too(self):
        off = compiled(True)
        on = compiled()

        def raises(name, ops):
            return len([i for i in ops[name] if i.op == "raise"])

        # (tested's cold blocks of the AttributeErrors of n.v and n.nxt go, that of its sums'
        # OverflowError stays; repeated's one check left still goes to its cold block)
        self.assertEqual(raises("tested", on), raises("tested", off) - 2)
        self.assertEqual(raises("repeated", on), raises("repeated", off))


if __name__ == "__main__":
    unittest.main()
