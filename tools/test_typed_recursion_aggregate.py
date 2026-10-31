"""Recursion versioning must preserve existing tuple allocation elimination."""
import re
import unittest

from test_typed_recursion import compile_source, operations


PAIR = '''
import sys

def leaf(n: int) -> int:
    return n + 1

def pair(n: int) -> tuple[int, int]:
    for i in range(2):
        n = leaf(n)
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


class AggregateRecursionTests(unittest.TestCase):
    def test_guarded_caller_keeps_aggregate_return_with_and_without_region(self):
        # kernel's limit observer prevents it from being versioned. Versioning
        # pair alone used to give it a new non-fresh fast-path return, disabling
        # tupleret and restoring a tuple heap allocation on every loop iteration.
        for opt in ("", "-recursionregion"):
            with self.subTest(opt=opt):
                ir, functions = compile_source(PAIR, opt=opt)
                self.assertNotIn("@rf.f.kernel", functions)
                self.assertRegex(ir, r"call \{i64, i64\} @v\.f\.pair\(")
                kernel = re.search(r"^define internal i64 @f\.kernel\(.*?^}", ir, re.M | re.S)
                self.assertIsNotNone(kernel)
                self.assertNotIn("call ptr @f.pair(", kernel.group(0))
                self.assertFalse(any(op[:2] == ("rt", "recursion.room")
                                     for op in operations(functions["@f.pair"])))

    def test_tuple_callee_can_still_be_cloned_inside_bounded_scalar_caller(self):
        source = PAIR.replace("    if n < 0:\n        sys.setrecursionlimit(1000)\n", "")
        ir, functions = compile_source(source)
        self.assertIn("@rf.f.kernel", functions)
        self.assertIn("@rf.f.pair", functions)
        self.assertRegex(ir, r"call \{i64, i64\} @v\.rf\.f\.pair\(")
        self.assertFalse(any(op[:2] == ("rt", "recursion.room")
                             for op in operations(functions["@f.pair"])))

    def test_disabled_tuple_pass_does_not_restrict_region_selection(self):
        ir, functions = compile_source(PAIR, opt="-tupleret")
        self.assertNotIn("@v.f.pair", ir)
        self.assertIn("@rf.f.pair", functions)
        self.assertTrue(any(op[:2] == ("rt", "recursion.room")
                            for op in operations(functions["@f.pair"])))


if __name__ == "__main__":
    unittest.main()
