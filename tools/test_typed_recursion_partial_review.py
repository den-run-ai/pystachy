"""Independent boundaries for partial recursion guard specialization."""
from pathlib import Path
import unittest

from test_typed_recursion import compile_source, operations


MIXED_PAIR = '''
import sys

def leaf(n: int) -> int:
    return n + 1

def observer(n: int) -> int:
    sys.setrecursionlimit(1000)
    return n

def pair(n: int) -> tuple[int, int]:
    if n < 0:
        value = observer(n)
        return (value, n)
    return (leaf(n), n)

def kernel(n: int) -> int:
    if n < 0:
        sys.setrecursionlimit(1000)
    total = 0
    for i in range(n):
        left, right = pair(i)
        total += left + right
    return total

print(kernel(3))
'''


class PartialRecursionReviewTests(unittest.TestCase):
    def test_partial_tuple_root_preserves_existing_aggregate_return(self):
        for opt in ("", "-recursionregion"):
            with self.subTest(opt=opt):
                ir, functions = compile_source(MIXED_PAIR, opt=opt)
                self.assertRegex(ir, r"call \{i64, i64\} @v\.f\.pair\(")
                self.assertNotIn("@rp.f.pair", functions)
        # This control proves that pair otherwise matches the partial proof.
        _, functions = compile_source(MIXED_PAIR, opt="-tupleret")
        self.assertIn("@rp.f.pair", functions)

    def test_observer_cannot_reenter_a_loop_of_unchecked_children(self):
        _, functions = compile_source('''
import sys

def leaf(n: int) -> int:
    return n + 1

def observer(n: int) -> int:
    sys.setrecursionlimit(1000)
    return n

def mixed_loop(n: int) -> int:
    total = 0
    for i in range(n):
        if i == 2:
            total += observer(i)
        else:
            total += leaf(i)
    return total

print(mixed_loop(4))
''')
        self.assertNotIn("@rp.f.mixed_loop", functions)
        self.assertNotIn("@rf.f.mixed_loop", functions)

    def test_depth_fixture_exercises_partial_root_and_cold_child(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "tests/programs/language/recursion_partial_depth.py").read_text()
        _, functions = compile_source(source)
        self.assertIn("@rp.f.partial", functions)
        self.assertIn("@rp2.f.cold_leaf", functions)
        fast = functions["@rp.f.partial"]
        self.assertIn(("call", "@rp2.f.cold_leaf"),
                      [op[:2] for op in operations(fast)])
        self.assertIn(("call", "@f.tail_observer"),
                      [op[:2] for op in operations(fast)])


if __name__ == "__main__":
    unittest.main()
